# Live two-machine acoustic test

This is a real speaker-to-air-to-mic channel between **this VM (kali)** and **your other Linux laptop**.
No SDR is required. Setup file transfer is normal, which you can do with USB or scp, and only the *channel under test* is acoustic.

## Noise-robust defaults (use these first)

- **Tones:** 1000 Hz and 2500 Hz, which sit above room rumble and fan hum.
- **Rate:** 50 baud (`sps=960`), so each bit lasts 20 ms and survives mild reverb.
- **Repeats:** sender sends **5 frames**; the receiver takes a **majority vote**.
- **SNR report:** the listener prints estimated in-band SNR so you can tell "too noisy" from "mic dead".
- Fan-style tones (`400,800`) remain available with `--tones 400,800`.

## Checklist from your side

| # | Item | Status |
|---|---|---|
| 1 | **VirtualBox, then Settings, then Audio, then Enable Audio Input** on this kali VM | **DO THIS FIRST**, because the mic was silent at OS level |
| 2 | Confirm the mic after step 1: run the command below. The RMS value should be **greater than 0.001** when you talk | |
| 3 | Boot the other laptop, which is bare Linux with speakers and a mic | |
| 4 | Copy the sender bundle to the other laptop with USB or scp: `live/sender_bundle.tar.gz` | |
| 5 | The other laptop needs `python3`, `numpy`, and `pacat` or `paplay` from pulseaudio-utils | |
| 6 | For **keygrab** mode, run the sender with `sudo`, or add the user to the `input` group on that laptop | |
| 7 | Physically place the laptops **no more than 1 m** apart, in a quiet room, with the other laptop volume at about 70–80% | |

Mic level check:

```bash
timeout 3 parec --format=s16 --rate=48000 --channels=1 --raw > /tmp/m.raw
python3 -c "import numpy as np; d=np.fromfile('/tmp/m.raw',dtype=np.int16); print(float(np.sqrt(np.mean((d/32768.)**2))))"
```

## Run, because order matters

**Terminal A, which is THIS machine and acts as the listener:**
```bash
cd labs/01-acoustic-fan-channel/live
python3 recv_live.py --seconds 35
```
Use `--seconds` longer than the sender run: 5 frames at 50 baud is roughly 40–50 s including gaps.

**Terminal B on the other laptop, which is the sender:**
```bash
tar xzf sender_bundle.tar.gz && cd sender_bundle
# Fixed payload test (5 frames for majority vote):
python3 send_live.py --message "AIRGAP-LIVE-OK" --repeats 5
```

A successful run prints the following on the listener:
```
[+] N raw decode(s); majority vote for best payload:
      5x b'AIRGAP-LIVE-OK' <== BEST
[+] recovered: 'AIRGAP-LIVE-OK'  (votes=5/5, snr=.. dB)
[PASS] live acoustic decode
```

## If the room is noisy

1. Move the laptops to **about 0.5–1 m**.
2. Raise sender volume (watch for distortion).
3. Send more frames: `--repeats 8`.
4. Record longer here: `--seconds 50`.
5. Keep AC and music off if you can.
6. If SNR prints **below ~6 dB**, the room is the limit; DSP cannot invent bits that were never audible.

## Keystroke exfil demo, which you should run after the fixed-message test works

On the **other laptop**, which is the sender, run as root or as a user in the `input` group:
```bash
sudo python3 send_live.py --keygrab
```
Type a few characters on that laptop, and start `recv_live.py --seconds 60` here **first**.

Each key is sent twice so the listener can vote; air time is about 8–10 s per key at 50 baud, which is slow but reliable.

## Local self-checks, which need no second machine

```bash
# The decode chain through real PulseAudio (monitor loopback) has already verified as PASS
# Mic level check:
timeout 3 parec --format=s16 --rate=48000 --channels=1 --raw > /tmp/m.raw
python3 -c "import numpy as np;d=np.fromfile('/tmp/m.raw',dtype=np.int16);print('rms',float(np.sqrt(np.mean((d/32768.)**2))))"
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| listener `rms=0.0000` | VBox audio input is off, or the source is muted, so run `pactl set-source-mute @DEFAULT_SOURCE@ 0` |
| listener `snr` very low but RMS OK | too noisy or too far; move closer and raise sender volume |
| sender: `pacat: command not found` | run `sudo apt install pulseaudio-utils` |
| sender: `no keyboard event device` | run `sudo python3 send_live.py --keygrab`, or run `sudo usermod -aG input $USER` and then re-login |
| decode fails, but SNR is good | ensure **both** sides use the same `--tones` (default 1000,2500) |
| wrong or noisy characters | keep the room quiet, stay within 1 m, add `--repeats 8` |

## Scope

This is an authorised lab that uses your two machines only. The acoustic demo proves the covert *channel*;
it is not literal RAM RF, because that class needs an SDR, as described in the lab 02 README.
