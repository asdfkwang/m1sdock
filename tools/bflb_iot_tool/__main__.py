# -*- coding:utf-8 -*-

import sys
from core import bflb_iot_tool


def run_main():
    bflb_iot_tool.run(sys.argv[1:])


if __name__ == "__main__":
    run_main()
