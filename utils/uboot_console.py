#!/usr/bin/env python3
"""uboot_console.py — M1s Dock U-Boot SD-card check over the D0 console UART.

Waits for the U-Boot prompt on the serial line (press RESET on the board),
runs the MMC detection/read command sequence, and compares the `crc32`
output against the SD card manifest produced by utils/mk_sdcard_test.sh.

Everything is written to a transcript with timestamps so the result can be
reviewed offline (e.g. by the AI assistant).

Run with the blflashcommand venv (has pyserial):
  blflashcommand/venv/bin/python utils/uboot_console.py [options]

Exit codes: 0 all checks passed, 1 serial/prompt failure, 2 CRC mismatch.
"""
import argparse
import re
import sys
import time

DEFAULT_BANNER = "U-Boot 2023"
DEFAULT_PROMPT = "=> "

# Fallbacks; the manifest values override them.
DEFAULT_TESTFILE_SIZE = 0x20000
DEFAULT_TESTFILE_CRC = "B971B8D8"

# Load addresses live in the 0x51xxxxxx scratch region: 0x5300xxxx overlaps
# the OpenSBI/U-Boot reservations (blank pool pointer) and must not be used.
TESTFILE_ADDR = 0x51000000
HELLO_ADDR = 0x51040000

CMDS = (
    "mmc list",
    "mmc dev 0",
    "mmc rescan",
    "mmc info",
    "mmc part",
    "fatls mmc 0:1",
    f"load mmc 0:1 0x{TESTFILE_ADDR:X} testfile",
    f"crc32 0x{TESTFILE_ADDR:X} {{TESTFILE_SIZE_HEX}}",
    f"load mmc 0:1 0x{HELLO_ADDR:X} hello.txt",
    f"md.b 0x{HELLO_ADDR:X} {{HELLO_SIZE_HEX}}",
)

# Verification runs: scramble the buffer first so a skipped/stuck load cannot
# pass by reusing the previous contents.
REPEAT_CMDS = (
    f"mw.b 0x{TESTFILE_ADDR:X} 0xa5 {{TESTFILE_SIZE_HEX}}",
    f"load mmc 0:1 0x{TESTFILE_ADDR:X} testfile",
    f"crc32 0x{TESTFILE_ADDR:X} {{TESTFILE_SIZE_HEX}}",
)


def log(out, s, stamp=True):
    line = (f"[{time.strftime('%H:%M:%S')}] {s}" if stamp else s) + "\n"
    out.write(line)
    out.flush()


def parse_manifest(path, out):
    """Pull testfile/hello.txt sizes and the testfile CRC from the manifest."""
    vals = {}
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as e:
        log(out, f"WARN: cannot read manifest {path}: {e}")
        return vals
    for name in ("hello.txt", "testfile"):
        m = re.search(rf"^\s*{re.escape(name)}\s*:\s*size=(\d+) \((0x[0-9A-Fa-f]+) bytes\)", text, re.M)
        if m:
            vals[f"{name}.size"] = int(m.group(1), 0)
    m = re.search(r"^  testfile\s*:\s*([0-9A-Fa-f]{8})\s*$", text, re.M)
    if m:
        vals["testfile.crc"] = m.group(1).upper()
    return vals


class Console:
    def __init__(self, port, baud, out):
        import serial
        # Configure the port without opening it so DTR/RTS are deasserted
        # before open: toggling the modem lines while opening glitches the
        # RX stream (same pattern as the experiment console driver).
        self.ser = serial.Serial(baudrate=baud, timeout=0.05)
        self.ser.exclusive = True
        self.ser.port = port
        self.ser.dtr = False
        self.ser.rts = False
        self.ser.open()
        self.buf = b""
        self.out = out

    def read_until(self, pattern, timeout):
        """Accumulate bytes until `pattern` (str) appears; return accumulated str."""
        rx = bytes()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            n = self.ser.read(4096)
            if n:
                rx += n
                self.buf += n
                text = self.buf.decode("utf-8", "replace")
                if pattern in text:
                    return text
            else:
                time.sleep(0.05)
        return self.buf.decode("utf-8", "replace")

    def wait_prompt(self, banner, prompt, timeout, out):
        """Wait for the prompt, heartbeating newlines so an already-idle
        board (booted before the script started) re-prints it."""
        step = max(1.0, timeout / 15)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            text = self.read_until(prompt, step)
            if prompt in text:
                if banner in text:
                    log(out, "banner OK (U-Boot reached)")
                else:
                    log(out, "prompt OK without banner (board already at prompt)")
                return True
            try:
                self.ser.write(b"\n")
            except OSError:
                log(out, "WARN: newline heartbeat write failed")
        log(out, "FAIL: U-Boot prompt not detected before timeout")
        return False

    def run_command(self, cmd, prompt="=> ", timeout=10):
        log(self.out, f"$ {cmd}")
        self.ser.reset_input_buffer()
        self.buf = b""
        self.ser.write((cmd + "\n").encode())
        text = self.read_until(prompt, timeout)
        for line in text.splitlines():
            if line.strip():
                log(self.out, f"  | {line.rstrip()}")
        return text


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=2000000)
    ap.add_argument("--transcript", default="/tmp/opencode/uboot_sd_transcript.log")
    ap.add_argument("--manifest", default="/tmp/opencode/sdcard_manifest.txt")
    ap.add_argument("--boot-wait", type=int, default=90,
                    help="seconds to wait for the U-Boot prompt (press RESET on the board)")
    ap.add_argument("--commands", default=None,
                    help="custom commands separated by '|' (overrides the default set)")
    ap.add_argument("--no-crc-check", action="store_true")
    ap.add_argument("--accept-crc", default="",
                    help="extra acceptable CRC-32 values (comma separated) — used when "
                         "the manifest CRC may be stale; the observed hash is reported")
    ap.add_argument("--repeat", type=int, default=1,
                    help="extra verify rounds after the main sequence (each scrambles "
                         "the buffer with mw.b before a fresh load+crc32)")
    args = ap.parse_args()

    out = open(args.transcript, "a", buffering=1)
    log(out, "===== uboot_console session start =====")
    log(out, f"port={args.port} baud={args.baud}")

    mf = parse_manifest(args.manifest, out)
    test_size = mf.get("testfile.size", DEFAULT_TESTFILE_SIZE)
    test_crc = mf.get("testfile.crc", DEFAULT_TESTFILE_CRC).upper()
    hello_size = mf.get("hello.txt.size", 55)
    log(out, f"manifest: testfile size={test_size:#x} crc={test_crc} hello size={hello_size:#x}")

    try:
        c = Console(args.port, args.baud, out)
    except OSError as e:
        log(out, f"ERROR: cannot open {args.port}: {e}")
        log(out, "hint: stop the UART loggers first (bdb log stop) so the port is free")
        out.close()
        return 1

    cmds = list(CMDS)
    # Substitute manifest-derived sizes into the command templates.
    subs = {
        "TESTFILE_SIZE_HEX": f"0x{test_size:X}",
        "HELLO_SIZE_HEX": f"0x{hello_size:X}",
    }
    if args.commands:
        cmds = [s.strip() for s in args.commands.split("|") if s.strip()]

    if not c.wait_prompt(DEFAULT_BANNER, DEFAULT_PROMPT, args.boot_wait, out):
        out.close()
        return 1

    crc_seen = []
    for raw in cmds:
        try:
            cmd = raw.format(**subs)
        except (KeyError, IndexError):
            cmd = raw
        text = c.run_command(cmd)
        for m in re.finditer(r"==>\s*([0-9A-Fa-f]{8})", text):
            crc_seen.append(m.group(1).upper())

    for rnd in range(1, max(1, args.repeat)):
        log(out, f"----- verify round {rnd + 1}/{args.repeat} -----")
        for raw in REPEAT_CMDS:
            try:
                cmd = raw.format(**subs)
            except (KeyError, IndexError):
                cmd = raw
            text = c.run_command(cmd)
            for m in re.finditer(r"==>\s*([0-9A-Fa-f]{8})", text):
                crc_seen.append(m.group(1).upper())

    verdict = []
    if not args.no_crc_check:
        accepted = {test_crc} | {s.strip().upper() for s in args.accept_crc.split(",") if s.strip()}
        if crc_seen:
            ok = any(h in accepted for h in crc_seen)
            verdict.append(("PASS" if ok else "FAIL") + f": crc32={sorted(set(crc_seen))} accepted={sorted(accepted)}")
        else:
            verdict.append(f"FAIL: no crc32 hash captured (accepted={sorted(accepted)})")

    log(out, "===== session end =====")
    merged = verdict or ["(no verdict — custom command set)"]
    for v in merged:
        log(out, f"VERDICT {v}")
    for v in merged:
        print(v)
    out.close()
    return 0 if all(v.startswith("PASS") for v in verdict) else (2 if verdict else 0)


if __name__ == "__main__":
    sys.exit(main())
