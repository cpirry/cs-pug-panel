# rcon.py
# Purpose: Source RCON protocol implementation and rcon_command().

import socket
import struct

from .constants import RCON_HOST, RCON_PORT
from .envfile import read_env


class RconError(Exception):
    pass


def read_rcon_password():
    return read_env().get("CS2_RCONPW", "")


def _rcon_packet(pkt_id, pkt_type, body):
    payload = struct.pack("<ii", pkt_id, pkt_type) + body.encode() + b"\x00\x00"
    return struct.pack("<i", len(payload)) + payload


def _rcon_recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise RconError("connection closed by server")
        buf += chunk
    return buf


def _rcon_read_packet(sock):
    size = struct.unpack("<i", _rcon_recv_exact(sock, 4))[0]
    data = _rcon_recv_exact(sock, size)
    pkt_id, pkt_type = struct.unpack("<ii", data[:8])
    body = data[8:-2].decode(errors="replace")
    return pkt_id, pkt_type, body


def rcon_command(command, timeout=5):
    password = read_rcon_password()
    if not password:
        raise RconError("no rcon password configured")
    with socket.create_connection((RCON_HOST, RCON_PORT), timeout=timeout) as sock:
        sock.sendall(_rcon_packet(1, 3, password))
        while True:
            pkt_id, pkt_type, _ = _rcon_read_packet(sock)
            if pkt_type == 2:
                if pkt_id == -1:
                    raise RconError("rcon authentication failed")
                break
        sock.sendall(_rcon_packet(2, 2, command))
        _, _, body = _rcon_read_packet(sock)
        return body
