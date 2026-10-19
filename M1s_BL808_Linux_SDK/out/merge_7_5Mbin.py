#!/usr/bin/env python3
"""Compatibility entry point; use the tracked, validated Linux image merger."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).resolve().parents[2] / 'utils/merge_linux_image.py'),
                   run_name='__main__')
