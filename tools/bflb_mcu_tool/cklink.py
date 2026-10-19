"""Stub for cklink - not used in UART flash path."""

class CklinkPort:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("cklink not available (stub)")

def cklink_init(*args, **kwargs):
    raise RuntimeError("cklink not available (stub)")

__all__ = ["CklinkPort", "cklink_init"]
