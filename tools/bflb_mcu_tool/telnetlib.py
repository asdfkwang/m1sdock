"""Minimal telnetlib shim for Python 3.13+ compatibility.

Python 3.13 removed telnetlib from stdlib. This shim provides the minimal
interface used by bflb_interface_openocd.py (Telnet() instantiation only).
"""

class Telnet:
    """Dummy Telnet class - openocd interface not used in our UART flow."""
    def __init__(self, *args, **kwargs):
        raise RuntimeError("telnetlib.Telnet not available (Python 3.13+); openocd interface disabled")

    def open(self, *args, **kwargs):
        raise RuntimeError("telnetlib not available")

    def close(self):
        pass

    def read_until(self, *args, **kwargs):
        return b""

    def read_all(self):
        return b""

    def write(self, *args, **kwargs):
        pass

__all__ = ["Telnet"]