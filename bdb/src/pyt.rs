// pyt.rs — embedded python drivers + subprocess plumbing.
//
// The drivers reuse the repo's bflb_mcu_tool library (the proven flash/read
// path) without modifying tool sources. bdb streams child output line by
// line so a supervising AI agent can watch progress; a hard timeout reaps
// stuck children (SIGKILL) and reports `timeout=true`.
use std::path::Path;
use std::process::Command;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use crate::core::Ctx;

/// sha256 via coreutils (single line, first token).
pub fn sha256_file(path: &Path) -> Option<String> {
    let out = std::process::Command::new("sha256sum")
        .arg(path)
        .output()
        .ok()?;
    let s = String::from_utf8_lossy(&out.stdout);
    s.split_whitespace().next().map(String::from)
}

pub struct RunOutcome {
    pub exit: Option<i32>,
    pub timeout: bool,
    pub output: String, // full collected output (stdout+stderr merged)
}

/// Run a child, streaming (printing) its output as it arrives while keeping
/// the full text for parsing. `timeout_secs == 0` means unlimited.
pub fn run_streaming(cmd: &mut Command, timeout_secs: u64) -> RunOutcome {
    use std::io::Write;
    use std::io::{BufRead, BufReader};
    use std::process::Stdio;

    cmd.stdout(Stdio::piped()).stderr(Stdio::piped());
    let mut child = match cmd.spawn() {
        Ok(c) => c,
        Err(e) => {
            return RunOutcome {
                exit: Some(240),
                timeout: false,
                output: format!("[bdb] error: spawn failed: {e}\n"),
            }
        }
    };
    type Shared = Mutex<Shared_>;
    struct Shared_ {
        s: String,
        printed: usize,
    }
    let shared: Arc<Shared> = Arc::new(Mutex::new(Shared_ { s: String::new(), printed: 0 }));

    fn drain(sh: &Arc<Shared>, final_mode: bool) {
        let mut g = sh.lock().unwrap();
        // Emit up to the last '\n' (or everything in final_mode).
        let max = if final_mode { g.s.len() } else {
            g.s[g.printed..].rfind('\n').map(|i| g.printed + i + 1).unwrap_or(g.printed)
        };
        if g.printed < max {
            eln!("{}", &g.s[g.printed..max]);
            let _ = std::io::stdout().flush();
            g.printed = max;
        }
    }

    let mut pipes: Vec<Box<dyn std::io::Read + Send>> = Vec::new();
    if let Some(s) = child.stdout.take() {
        pipes.push(Box::new(s));
    }
    if let Some(s) = child.stderr.take() {
        pipes.push(Box::new(s));
    }
    let mut readers = Vec::new();
    for pipe in pipes {
        let sh = shared.clone();
        readers.push(std::thread::spawn(move || {
            let r = BufReader::new(pipe);
            for line in r.lines().flatten() {
                let mut g = sh.lock().unwrap();
                g.s.push_str(&line);
                g.s.push('\n');
            }
        }));
    }

    let start = Instant::now();
    let deadline = (timeout_secs > 0).then(|| start + Duration::from_secs(timeout_secs));
    let mut timeout_hit = false;
    let mut status = None;
    loop {
        match child.try_wait() {
            Ok(Some(st)) => {
                status = Some(st);
                break;
            }
            Ok(None) => {}
            Err(_) => break,
        }
        drain(&shared, false);
        if deadline.is_some_and(|d| Instant::now() >= d) {
            timeout_hit = true;
            let _ = child.kill();
            // Reap even if deadlocked in the child's writer side.
            for _ in 0..20 {
                if child.try_wait().map(|s| s.is_some()).unwrap_or(true) {
                    break;
                }
                std::thread::sleep(Duration::from_millis(100));
            }
            status = child.wait().ok();
            break;
        }
        std::thread::sleep(Duration::from_millis(150));
    }
    for t in readers {
        let _ = t.join();
    }
    drain(&shared, true);
    let output = shared.lock().unwrap().s.clone();
    RunOutcome {
        exit: status.as_ref().and_then(|s| s.code()),
        timeout: timeout_hit,
        output,
    }
}

// ---------------------------------------------------------------------------
// Embedded python drivers
// ---------------------------------------------------------------------------

pub const PY_FLASH: &str = r#"#!/usr/bin/env python3
"""bdb embedded driver: flash low_load (m0+d0) via bflb_mcu_tool library API.

Layout (docs/bootinfo + docs/flash-layout): bootinfo g0 @0x0 (m0, 1636 B),
bootinfo g1 @0x1000 (d0, 352 B); image body g0 (m0) @0x2000 and g1 (d0)
@0x52000. The program step uses XIP base 0x58000000 == flash offset 0x0000.
Tool sources are not modified.
"""

import os
import sys
import traceback

TOOL_ROOT = os.environ["BDB_TOOL_ROOT"]
M0 = os.environ["BDB_M0"]
D0 = os.environ["BDB_D0"]
PORT = os.environ["BDB_PORT_C1"]
BAUD = int(os.environ["BDB_BAUD"])
IMG_ADDR = os.environ.get("BDB_IMG_ADDR", "0x58000000")

sys.path.insert(0, TOOL_ROOT)

from core import bflb_mcu_tool  # noqa: E402
import config as gol  # noqa: E402


class ArgsShim:
    chipname = "bl808"


def ensure_cpu_reset_after_load(loader_cfg, loader_cfg_tmp):
    """Patch the runtime-generated eflash_loader_cfg.ini so the tool issues a
    CPU reset (cmd 0x21) after every flash operation. Vendor ships
    cpu_reset_after_load = false, which leaves the chip wedged inside the
    eflash-loader state after a session; the next plain RESET then fails to
    bring the d0 branch up (reproduced: silent boots after bdb sessions).
    DevCube behaves differently here, which explains the divergence. The .ini
    is a runtime copy of the vendored .conf (tool sources stay untouched)."""
    import os as _os
    import shutil as _shutil
    with open(loader_cfg_tmp, "r", encoding="utf-8") as f:
        txt = f.read()
    if "cpu_reset_after_load = false" in txt:
        txt = txt.replace("cpu_reset_after_load = false", "cpu_reset_after_load = true")
        with open(loader_cfg_tmp, "w", encoding="utf-8") as f:
            f.write(txt)
        print("=== cfg patch: cpu_reset_after_load false->true ===", flush=True)
    else:
        print("=== cfg patch: cpu_reset_after_load already OK ===", flush=True)


def main():
    args = ArgsShim()
    args.firmware = M0
    args.dts = None
    args.port = PORT
    args.baudrate = BAUD
    args.addr = IMG_ADDR
    args.xtal = None
    args.flashclk = None
    args.pllclk = None
    args.bootsrc = "Flash"
    args.erase = False
    args.key = None
    args.iv = None
    args.pk = None
    args.sk = None
    args.pk_str = None
    args.sk_str = None
    args.log = False

    config = bflb_mcu_tool.get_value(args)
    config["img1_group"] = "group0"
    config["img1_addr"] = IMG_ADDR
    config["img2_group"] = "group1"
    config["img2_file"] = D0
    config["img2_addr"] = IMG_ADDR

    chiptype = gol.dict_chip_cmd["bl808"]
    obj = bflb_mcu_tool.BflbMcuTool("bl808", chiptype)
    ensure_cpu_reset_after_load(obj.eflash_loader_cfg, obj.eflash_loader_cfg_tmp)
    print("=== create_img (bl808 mcu groups) ===", flush=True)
    res = obj.create_img("bl808", chiptype, config)
    if res is not True:
        print("create_img failed:", res)
        sys.exit(1)
    print("=== program (low_load m0+d0 -> flash @0x0 area) ===", flush=True)
    obj.program_img_thread(config, act="download")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc(limit=8, file=sys.stdout)
        sys.exit(255)
"#;

pub const PY_READBACK: &str = r#"#!/usr/bin/env python3
"""bdb embedded driver: read flash regions via bflb_mcu_tool library API.

Region list is passed via env: BDB_RB_REGIONS="name,start,end|name2,start2,end2"
(hex addresses). Region payloads are written as rd_<name>.bin. Requires the
chip to sit in flash-mode (ROM handshake); the tool sources are not modified.
"""

import os
import shutil
import sys
import traceback

TOOL_ROOT = os.environ["BDB_TOOL_ROOT"]
OUT_DIR = os.environ["BDB_RB_OUT_DIR"]
FW = os.environ["BDB_FW"]
PORT = os.environ["BDB_PORT_C1"]
BAUD = int(os.environ["BDB_BAUD"])

REGIONS = []
for spec in os.environ["BDB_RB_REGIONS"].split("|"):
    name, start, end = spec.split(",")
    REGIONS.append((name.strip(), start.strip(), end.strip()))

sys.path.insert(0, TOOL_ROOT)

from core import bflb_mcu_tool  # noqa: E402
import config as gol  # noqa: E402


class ArgsShim:
    chipname = "bl808"


def ensure_cpu_reset_after_load(loader_cfg, loader_cfg_tmp):
    """Patch the runtime-generated eflash_loader_cfg.ini so the tool issues a
    CPU reset (cmd 0x21) after every flash operation. Vendor ships
    cpu_reset_after_load = false, which leaves the chip wedged inside the
    eflash-loader state after a session; the next plain RESET then fails to
    bring the d0 branch up (reproduced: silent boots after bdb sessions).
    DevCube behaves differently here, which explains the divergence. The .ini
    is a runtime copy of the vendored .conf (tool sources stay untouched)."""
    import os as _os
    import shutil as _shutil
    with open(loader_cfg_tmp, "r", encoding="utf-8") as f:
        txt = f.read()
    if "cpu_reset_after_load = false" in txt:
        txt = txt.replace("cpu_reset_after_load = false", "cpu_reset_after_load = true")
        with open(loader_cfg_tmp, "w", encoding="utf-8") as f:
            f.write(txt)
        print("=== cfg patch: cpu_reset_after_load false->true ===", flush=True)
    else:
        print("=== cfg patch: cpu_reset_after_load already OK ===", flush=True)


def main():
    args = ArgsShim()
    # get_value() requires an existing firmware path; the read path does not
    # consume its contents.
    args.firmware = FW
    args.dts = None
    args.port = PORT
    args.baudrate = BAUD
    args.addr = "0x00000000"
    args.xtal = None
    args.flashclk = None
    args.pllclk = None
    args.bootsrc = "Flash"
    args.erase = False
    args.key = None
    args.iv = None
    args.pk = None
    args.sk = None
    args.pk_str = None
    args.sk_str = None
    args.log = False

    config = bflb_mcu_tool.get_value(args)
    config["dl_verify"] = "False"

    chiptype = gol.dict_chip_cmd["bl808"]
    obj = bflb_mcu_tool.BflbMcuTool("bl808", chiptype)
    ensure_cpu_reset_after_load(obj.eflash_loader_cfg, obj.eflash_loader_cfg_tmp)

    os.makedirs(OUT_DIR, exist_ok=True)
    os.chdir(OUT_DIR)
    for name, start, end in REGIONS:
        config["start_addr"] = start
        config["end_addr"] = end
        print("=== read {} {}..{} ===".format(name, start, end), flush=True)
        ret = obj.read_flash_thread(config)
        if isinstance(ret, str):
            print("read failed:", ret)
            sys.exit(1)
        shutil.move(
            os.path.join(TOOL_ROOT, "flash.bin"),
            os.path.join(OUT_DIR, "rd_{}.bin".format(name)),
        )

    for name, _s, _e in REGIONS:
        data = open(os.path.join(OUT_DIR, "rd_{}.bin".format(name)), "rb").read()
        print("[dump] {} size={} head={}".format(name, len(data), data[:16].hex()))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc(limit=8, file=sys.stdout)
        sys.exit(255)
"#;

fn write_driver(ctx: &Ctx, tag: &str, body: &str) -> Option<std::path::PathBuf> {
    let p = ctx.work_dir().join(format!("drv_{tag}.py"));
    std::fs::write(&p, body).ok()?;
    Some(p)
}

/// Run the embedded low_load flash driver (m0+d0, 4 logical regions).
pub fn run_flash_low_load(ctx: &Ctx) -> RunOutcome {
    let m0 = ctx.vendor_m0();
    let d0 = ctx.vendor_d0();
    let missing: Vec<String> = [m0.as_path(), d0.as_path()]
        .into_iter()
        .filter(|p| !p.exists())
        .map(|p| p.display().to_string())
        .collect();
    if !missing.is_empty() {
        return RunOutcome {
            exit: Some(4),
            timeout: false,
            output: format!("[bdb] error: vendor low_load inputs missing: {}\n", missing.join(", ")),
        };
    }
    let Some(script) = write_driver(ctx, "flash", PY_FLASH) else {
        return RunOutcome {
            exit: Some(4),
            timeout: false,
            output: "[bdb] error: cannot write embedded flash driver\n".into(),
        };
    };
    let mut cmd = Command::new(ctx.venv_python());
    cmd.arg(script)
        .current_dir(&ctx.repo)
        .env("BDB_TOOL_ROOT", ctx.mcu_tool())
        .env("BDB_M0", ctx.vendor_m0())
        .env("BDB_D0", ctx.vendor_d0())
        .env("BDB_PORT_C1", &ctx.port_c1)
        .env("BDB_BAUD", &ctx.baud);
    run_streaming(&mut cmd, 0)
}

/// Run the embedded readback driver for given regions (name, start, end hex).
pub fn run_readback(ctx: &Ctx, regions: &[(String, String, String)]) -> RunOutcome {
    if !Path::new(&ctx.fw_whole_img()).exists() {
        return RunOutcome {
            exit: Some(4),
            timeout: false,
            output: format!("[bdb] error: dummy firmware missing: {}\n", ctx.fw_whole_img().display()),
        };
    }
    let list = regions
        .iter()
        .map(|(n, s, e)| format!("{n},{s},{e}"))
        .collect::<Vec<_>>()
        .join("|");
    let tag = format!("rb_{}", crate::core::now_secs());
    let out_dir = ctx.work_dir().join(&tag);
    let Some(script) = write_driver(ctx, "readback", PY_READBACK) else {
        return RunOutcome {
            exit: Some(4),
            timeout: false,
            output: "[bdb] error: cannot write embedded readback driver\n".into(),
        };
    };
    let mut cmd = Command::new(ctx.venv_python());
    cmd.arg(script)
        .current_dir(&ctx.repo)
        .env("BDB_TOOL_ROOT", ctx.mcu_tool())
        .env("BDB_RB_OUT_DIR", &out_dir)
        .env("BDB_FW", ctx.fw_whole_img())
        .env("BDB_PORT_C1", &ctx.port_c1)
        .env("BDB_BAUD", &ctx.baud)
        .env("BDB_RB_REGIONS", &list);
    let mut res = run_streaming(&mut cmd, 0);
    res.output.push_str(&format!(
        "\n[bdb] readback-output-dir={}\n",
        out_dir.display()
    ));
    res
}
