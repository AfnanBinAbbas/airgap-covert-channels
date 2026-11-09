#!/usr/bin/env python3
"""Live acoustic receiver: record mic, majority-vote repeated frames, decode payload.

Start this FIRST on the listening machine, then run send_live.py on the other.

Noise handling:
  - narrow per-tone matched demod (same as receiver.demod_tones)
  - multi-frame majority vote (sender --repeats 5 recommended)
  - SNR report so you can tell "too noisy" from "mic dead"

Uses parec (PulseAudio), so alsa-utils is not required.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

import numpy as np

LAB = Path(__file__).resolve().parents[1]
ROOT = LAB.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(LAB))

from common.framing import decode_payload  # noqa: E402
from common.modulation import find_preamble  # noqa: E402
from emitter import TONE0_HZ, TONE1_HZ, parse_tones  # noqa: E402
from receiver import FS, SPS, bandpass, demod_tones, estimate_snr_db  # noqa: E402


def record(seconds: float, fs: int = FS, source: str | None = None) -> np.ndarray:
    """Record via parec to a file. A shell timeout avoids pipe-buffer truncation."""
    rec_path = Path(tempfile.mktemp(suffix=".pcm"))
    src_args = f"-d {source}" if source else ""
    cmd = f"timeout {int(seconds) + 4} parec {src_args} --format=s16 --rate={fs} --channels=1 --raw > {rec_path}"
    print(f"[*] recording ~{seconds:.1f}s (source={source or 'default'}) ...")
    p = subprocess.Popen(cmd, shell=True)
    try:
        p.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        p.terminate()
        try:
            p.wait(timeout=3)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=2)
    time.sleep(0.3)
    pcm = np.fromfile(rec_path, dtype=np.int16).astype(np.float64) / 32768.0
    rec_path.unlink(missing_ok=True)
    rms = float(np.sqrt(np.mean(pcm**2))) if pcm.size else 0.0
    peak = float(np.max(np.abs(pcm))) if pcm.size else 0.0
    print(f"    got {pcm.size} samples ({pcm.size/fs:.2f}s) rms={rms:.4f} peak={peak:.4f}")
    return pcm


def demod_at_offset(wave: np.ndarray, offset: int, sps: int = SPS,
                    f0: float = TONE0_HZ, f1: float = TONE1_HZ) -> np.ndarray:
    """Same matched demod as receiver.demod_tones, with a symbol-phase offset."""
    if offset:
        wave = wave[offset:]
    return demod_tones(wave, fs=FS, sps=sps, f0=f0, f1=f1)


def find_preamble_tolerant(bits: np.ndarray, pre: np.ndarray, max_err: int = 5) -> int:
    """Vectorised Hamming-distance preamble search."""
    w = bits.astype(np.uint8)
    p = pre.astype(np.uint8)
    n, m = w.size, p.size
    if n < m:
        return -1
    # sliding XOR popcount via stride tricks
    # build windows: shape (n-m+1, m)
    idx = np.arange(m)
    windows = w[idx + np.arange(n - m + 1)[:, None]]
    dist = np.count_nonzero(windows != p, axis=1)
    i = int(np.argmin(dist))
    return i if int(dist[i]) <= max_err else -1


def decode_frames(wave: np.ndarray, sps: int = SPS, max_frames: int = 30,
                  f0: float = TONE0_HZ, f1: float = TONE1_HZ,
                  stop_after: int = 0) -> list[dict]:
    """Search a few symbol offsets; return decoded frames for majority voting.

    If stop_after > 0, return early once that many frames share one payload.
    """
    pre = np.tile(np.array([1, 0], dtype=np.uint8), 16)
    found = []
    seen = set()
    # 4 phase candidates balances skew tolerance vs CPU
    step = max(1, sps // 4)
    for off in range(0, sps, step):
        bits = demod_at_offset(wave, off, sps, f0=f0, f1=f1)
        if bits.size < pre.size + 32:
            continue
        pos = find_preamble_tolerant(bits, pre, max_err=5)
        if pos < 0:
            pos = find_preamble_tolerant(1 - bits, pre, max_err=5)
            if pos >= 0:
                bits = 1 - bits
            else:
                continue
        cursor = pos
        guard = 0
        while cursor + pre.size + 7 < bits.size and len(found) < max_frames and guard < 12:
            guard += 1
            ok, body, st = decode_payload(bits[cursor + pre.size :], fec=True)
            if not ok:
                break
            key = (body, off // max(step, 1), cursor // max(sps, 1))
            if key not in seen:
                seen.add(key)
                found.append({
                    "ok": True,
                    "payload": body,
                    "phase_offset": off,
                    "bit_pos": cursor,
                    "crc_ok": st.get("crc_ok"),
                })
                if stop_after > 0:
                    # early exit if one payload already has enough votes
                    counts = Counter(f["payload"] for f in found)
                    top, n = counts.most_common(1)[0]
                    if n >= stop_after and sum(counts.values()) <= n + 3:
                        return found
            frame_bytes = int(st.get("frame_len", 16))
            fec_bits = ((frame_bytes * 8 + 3) // 4) * 7
            cursor = cursor + pre.size + max(fec_bits, 32)
            if cursor >= bits.size:
                break
            nxt = find_preamble_tolerant(bits[cursor : cursor + sps * 4], pre, max_err=5)
            if nxt < 0:
                nxt = find_preamble_tolerant(bits[cursor : cursor + sps * 20], pre, max_err=5)
                if nxt < 0:
                    break
            cursor += nxt
    return found


def majority_vote(frames: list[dict]) -> tuple[bytes | None, int, int]:
    """Return (best_payload, votes_for_best, total_frames).

    Prefers fully printable payloads; among equal votes prefers the shorter
    clean string (drops trailing NULs / control bytes that come from silence).
    """
    if not frames:
        return None, 0, 0

    def _clean(body: bytes) -> bytes:
        return body.rstrip(b"\x00")

    def _is_printable(body: bytes) -> bool:
        try:
            body.decode("utf-8")
        except UnicodeDecodeError:
            return False
        return all(32 <= c < 127 for c in body)

    cleaned = [_clean(f["payload"]) for f in frames]
    printable = [b for b in cleaned if _is_printable(b)]
    pool = printable if printable else cleaned
    # count, then break ties by shorter length then by first seen
    counts = Counter(pool)
    best = max(counts.items(), key=lambda kv: (kv[1], -len(kv[0])))
    return best[0], best[1], len(frames)


def main() -> None:
    ap = argparse.ArgumentParser(description="Live acoustic covert-channel receiver")
    ap.add_argument("--seconds", type=float, default=20.0, help="record duration")
    ap.add_argument("--source", help="pulse source name (default: @DEFAULT_SOURCE@)")
    ap.add_argument("--wav", type=Path, help="decode an existing raw float/int16 file")
    ap.add_argument("--sps", type=int, default=SPS)
    ap.add_argument("--tones", default=None, help="tone pair Hz as f0,f1 (must match sender)")
    ap.add_argument("--min-votes", type=int, default=2,
                    help="majority-vote threshold (default 2)")
    args = ap.parse_args()

    f0, f1 = parse_tones(args.tones)
    print(f"[*] expecting tones {f0:.0f}/{f1:.0f} Hz @ {FS} Hz, sps={args.sps}")

    if args.wav and args.wav.exists():
        if args.wav.suffix == ".wav":
            import wave

            with wave.open(str(args.wav), "rb") as w:
                fs_file = w.getframerate()
                raw = w.readframes(w.getnframes())
                sw = w.getsampwidth()
            if sw == 2:
                wavef = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768.0
            else:
                raise SystemExit(f"unsupported wav sampwidth {sw}")
            if fs_file != FS:
                ratio = FS / fs_file
                n_out = int(wavef.size * ratio)
                wavef = np.interp(np.linspace(0, wavef.size - 1, n_out),
                                  np.arange(wavef.size), wavef)
        else:
            wavef = np.fromfile(args.wav, dtype=np.float64)
        print(f"[*] decoding file {args.wav} ({wavef.size} samples)")
    else:
        wavef = record(args.seconds, fs=FS, source=args.source)

    if wavef.size == 0 or np.max(np.abs(wavef)) < 1e-6:
        print("[FAIL] empty or silent capture; check that the mic is unmuted and that VBox audio input is enabled")
        sys.exit(2)

    snr = estimate_snr_db(wavef, fs=FS, f0=f0, f1=f1, sps=args.sps)
    print(f"[*] estimated in-band SNR: {snr:.1f} dB")
    if snr < 6:
        print("[warn] low SNR; move closer, raise sender volume, or reduce room noise")

    # Early-exit once one payload has min_votes (still scan a bit for confidence)
    stop = max(args.min_votes, 3)
    frames = decode_frames(wavef, sps=args.sps, f0=f0, f1=f1, stop_after=stop)
    best, votes, total = majority_vote(frames)

    if not frames or best is None:
        print(f"[FAIL] no frames decoded (SNR={snr:.1f} dB). Silent mic? Wrong tones? Too far?")
        sys.exit(1)

    print(f"[+] {total} raw decode(s); majority vote for best payload:")
    for body, n in Counter(f["payload"] for f in frames).most_common(5):
        mark = " <== BEST" if body == best else ""
        print(f"    {n:3d}x {body!r}{mark}")

    text = best.decode("utf-8", "replace")
    if votes >= args.min_votes or total == 1:
        print(f"[+] recovered: {text!r}  (votes={votes}/{total}, snr={snr:.1f} dB)")
        print("[PASS] live acoustic decode")
        sys.exit(0)
    print(f"[FAIL] majority too weak: {votes}/{total} votes for {best!r} (need >= {args.min_votes})")
    sys.exit(1)


if __name__ == "__main__":
    main()
