"""Exclusive U-Boot UART connection with persistent raw transcripts."""
import re
import time
import serial


class Console:
    def __init__(self, transcript):
        self.log = open(transcript, 'w', buffering=1)
        self.port = serial.Serial(port=None, baudrate=2000000, timeout=0.05,
                                  write_timeout=3, exclusive=True)
        self.port.port = '/dev/ttyUSB0'
        self.port.dtr = False
        self.port.rts = False
        self.port.open()

    def receive(self, marker=b'=>', timeout=5):
        data = b''
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            data += self.port.read(4096)
            if (marker == b'=>' and data.rstrip().endswith(marker)) or (marker != b'=>' and marker in data):
                break
        text = data.decode('utf-8', 'replace')
        self.log.write(text + '\n')
        if marker not in data:
            raise RuntimeError('Console timeout: ' + text)
        return text

    def command(self, command, timeout=5):
        self.log.write('\n>>> ' + command + '\n')
        self.port.write((command + '\r').encode())
        self.port.flush()
        text = self.receive(timeout=timeout)
        if any(s in text for s in ('Unknown command', 'Unhandled exception', 'Resetting CPU')):
            raise RuntimeError(text)
        return text

    def read(self, address, width='l'):
        text = self.command(f'md.{width} 0x{address:x} 1')
        match = re.search(rf'(?im)^{address:08x}:\s+([0-9a-f]+)', text)
        if not match:
            raise RuntimeError('Register output not parsed: ' + text)
        return int(match[1], 16)

    def close(self):
        self.port.close()
        self.log.close()
