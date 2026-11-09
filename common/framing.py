"""Bit framing: NRZ helpers, CRC16, Hamming(7,4) FEC for weak covert channels."""

from __future__ import annotations

import numpy as np


def bytes_to_bits(data: bytes) -> np.ndarray:
    """MSB-first bit array from bytes."""
    if not data:
        return np.zeros(0, dtype=np.uint8)
    arr = np.frombuffer(data, dtype=np.uint8)
    bits = np.unpackbits(arr, bitorder="big")
    return bits.astype(np.uint8)


def bits_to_bytes(bits: np.ndarray) -> bytes:
    """Pack MSB-first bits into bytes (pads with zeros to full byte)."""
    bits = np.asarray(bits, dtype=np.uint8).ravel()
    if bits.size == 0:
        return b""
    pad = (-bits.size) % 8
    if pad:
        bits = np.concatenate([bits, np.zeros(pad, dtype=np.uint8)])
    return np.packbits(bits, bitorder="big").tobytes()


def crc16_ccitt(data: bytes, poly: int = 0x1021, init: int = 0xFFFF) -> int:
    crc = init
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ poly) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def add_crc16(payload: bytes) -> bytes:
    c = crc16_ccitt(payload)
    return payload + bytes([(c >> 8) & 0xFF, c & 0xFF])


def check_crc16(frame: bytes) -> tuple[bool, bytes]:
    if len(frame) < 3:
        return False, frame
    body, tail = frame[:-2], frame[-2:]
    expect = crc16_ccitt(body)
    got = (tail[0] << 8) | tail[1]
    return expect == got, body


def hamming74_encode(nibbles: np.ndarray) -> np.ndarray:
    """Encode 4-bit nibbles -> 7-bit Hamming words (SEC). Input uint8 0..15."""
    nibbles = np.asarray(nibbles, dtype=np.uint8) & 0x0F
    # positions 1..7; data in d1..d4 at positions 3,5,6,7
    d = [(nibbles >> i) & 1 for i in (3, 2, 1, 0)]  # d1..d4 MSB first within nibble
    d1, d2, d3, d4 = d
    p1 = d1 ^ d2 ^ d4
    p2 = d1 ^ d3 ^ d4
    p3 = d2 ^ d3 ^ d4
    # pack p1 p2 d1 p3 d2 d3 d4  (bit6..bit0)
    code = (
        (p1.astype(np.uint8) << 6)
        | (p2.astype(np.uint8) << 5)
        | (d1.astype(np.uint8) << 4)
        | (p3.astype(np.uint8) << 3)
        | (d2.astype(np.uint8) << 2)
        | (d3.astype(np.uint8) << 1)
        | d4.astype(np.uint8)
    )
    return code.astype(np.uint8)


def hamming74_decode(codes: np.ndarray) -> np.ndarray:
    """Decode 7-bit Hamming words -> nibbles. Corrects single-bit errors."""
    codes = np.asarray(codes, dtype=np.uint8) & 0x7F
    b = [(codes >> i) & 1 for i in range(7)]  # b6..b0 = p1 p2 d1 p3 d2 d3 d4
    p1, p2, d1, p3, d2, d3, d4 = b
    s1 = p1 ^ d1 ^ d2 ^ d4
    s2 = p2 ^ d1 ^ d3 ^ d4
    s3 = p3 ^ d2 ^ d3 ^ d4
    # error position = s1 + 2*s2 + 4*s3 (standard Hamming)
    syn_to_idx = {0: None, 1: 6, 2: 5, 3: 4, 4: 3, 5: 2, 6: 1, 7: 0}
    corrected = codes.copy()
    if s1.size:
        pos = (s1.astype(np.int32) + (s2.astype(np.int32) << 1) + (s3.astype(np.int32) << 2))
        # vectorized: flip bit where pos in 1..7
        for p in range(1, 8):
            target = syn_to_idx[p]
            mask = pos == p
            if np.any(mask):
                corrected = np.where(mask, corrected ^ (1 << target), corrected)
    c = [(corrected >> i) & 1 for i in range(7)]
    d1, d2, d3, d4 = c[4], c[2], c[1], c[0]
    nibble = (d1 << 3) | (d2 << 2) | (d3 << 1) | d4
    return nibble.astype(np.uint8)


def encode_payload(payload: bytes, fec: bool = True) -> np.ndarray:
    """CRC16 + optional Hamming FEC -> bit stream for transmission."""
    framed = add_crc16(payload)
    bits = bytes_to_bits(framed)
    if not fec:
        return bits
    # pad to nibble (4 bits); framed payload is byte-aligned so pad is rare
    if bits.size % 4:
        bits = np.concatenate([bits, np.zeros(4 - bits.size % 4, dtype=np.uint8)])
    nibbles = (
        ((bits[0::4].astype(np.uint8) << 3)
         | (bits[1::4].astype(np.uint8) << 2)
         | (bits[2::4].astype(np.uint8) << 1)
         | bits[3::4].astype(np.uint8))
    ).astype(np.uint8)
    codes = hamming74_encode(nibbles)
    # unpack 7-bit codes to bits, MSB of each code first
    out = np.zeros(codes.size * 7, dtype=np.uint8)
    for i in range(7):
        out[i::7] = (codes >> (6 - i)) & 1
    return out


def _decode_exact(bits: np.ndarray, fec: bool) -> tuple[bool, bytes, dict]:
    """Decode a bit string assumed to be exactly one frame (no trailing junk)."""
    stats = {"fec": fec, "n_bits": int(np.asarray(bits).size)}
    bits = np.asarray(bits, dtype=np.uint8).ravel()
    if fec:
        if bits.size % 7:
            bits = bits[: bits.size - (bits.size % 7)]
        if bits.size == 0:
            return False, b"", {**stats, "crc_ok": False, "frame_len": 0}
        codes = np.zeros(bits.size // 7, dtype=np.uint8)
        for i in range(7):
            codes |= bits[i::7].astype(np.uint8) << (6 - i)
        nibbles = hamming74_decode(codes)
        bits = np.zeros(nibbles.size * 4, dtype=np.uint8)
        bits[0::4] = (nibbles >> 3) & 1
        bits[1::4] = (nibbles >> 2) & 1
        bits[2::4] = (nibbles >> 1) & 1
        bits[3::4] = nibbles & 1
    raw = bits_to_bytes(bits)
    ok, body = check_crc16(raw)
    stats["crc_ok"] = ok
    stats["frame_len"] = len(raw)
    return ok, body if ok else raw, stats


def decode_payload(bits: np.ndarray, fec: bool = True, max_trim_codewords: int = 96,
                   min_frame_bytes: int = 1) -> tuple[bool, bytes, dict]:
    """Inverse of encode_payload. Tolerates trailing junk/silence bits.

    CRC16(payload || CRC) is 0, so zero-padding after a real frame would make
    a *longer* string also look valid. We therefore take the SHORTEST
    CRC-valid byte prefix of the FEC-decoded stream, which recovers the true
    payload and ignores silence that demodulated as zeros.
    """
    bits = np.asarray(bits, dtype=np.uint8).ravel()
    if not bits.size:
        return False, b"", {"fec": fec, "n_bits": 0, "crc_ok": False}

    def _raw_from_bits(b: np.ndarray) -> bytes:
        if fec:
            if b.size % 7:
                b = b[: b.size - (b.size % 7)]
            if b.size == 0:
                return b""
            codes = np.zeros(b.size // 7, dtype=np.uint8)
            for i in range(7):
                codes |= b[i::7].astype(np.uint8) << (6 - i)
            nibbles = hamming74_decode(codes)
            out = np.zeros(nibbles.size * 4, dtype=np.uint8)
            out[0::4] = (nibbles >> 3) & 1
            out[1::4] = (nibbles >> 2) & 1
            out[2::4] = (nibbles >> 1) & 1
            out[3::4] = nibbles & 1
            return bits_to_bytes(out)
        return bits_to_bytes(b)

    def _shortest_crc(raw: bytes) -> tuple[bool, bytes, dict]:
        stats = {"fec": fec, "n_bits": int(bits.size)}
        # Shortest valid frame first: body >= min_frame_bytes, plus 2-byte CRC
        for end in range(min_frame_bytes + 2, len(raw) + 1):
            ok, body = check_crc16(raw[:end])
            if ok and len(body) >= min_frame_bytes:
                stats.update({"crc_ok": True, "frame_len": end})
                return True, body, stats
        ok, body = check_crc16(raw) if len(raw) >= min_frame_bytes + 2 else (False, raw)
        stats.update({"crc_ok": ok, "frame_len": len(raw)})
        return ok, (body if ok else raw), stats

    raw = _raw_from_bits(bits)
    ok, body, st = _shortest_crc(raw)
    if ok:
        return True, body, st

    if fec:
        n0 = bits.size - (bits.size % 7)
        limit = max(7, n0 - 7 * max_trim_codewords)
        for n in range(n0 - 7, limit - 1, -7):
            raw_i = _raw_from_bits(bits[:n])
            ok_i, body_i, st_i = _shortest_crc(raw_i)
            if ok_i:
                return True, body_i, st_i
    return False, body, st
