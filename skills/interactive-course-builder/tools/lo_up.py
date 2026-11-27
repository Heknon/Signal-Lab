#!/usr/bin/env python3
"""Bring the loopback interface up inside a fresh network namespace (no `ip` command needed).

    unshare -rn bash -c 'python3 <skill>/tools/lo_up.py && python3 scripts/test_lessons.py'
"""
import fcntl
import socket
import struct
import sys

SIOCGIFFLAGS, SIOCSIFFLAGS, IFF_UP = 0x8913, 0x8914, 0x1

try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    flags = struct.unpack("16sH14s", fcntl.ioctl(s, SIOCGIFFLAGS, struct.pack("16sH14s", b"lo", 0, b"")))[1]
    fcntl.ioctl(s, SIOCSIFFLAGS, struct.pack("16sH14s", b"lo", flags | IFF_UP, b""))
except OSError as e:
    sys.exit(f"could not bring lo up: {e}")
