# Lab 05: Shared SDR Receiver Stack (hardware-ready)

Shared capture and demod toolkit for labs 02–04, and for live TEMPEST work in lab 06.
It works offline on recorded IQ, and uses `pyrtlsdr` when a dongle is present.

## Tools

| Script | Purpose |
|---|---|
| `capture.py` | Record IQ from RTL-SDR, or replay a file, then write `recordings/*.c64` with metadata |
| `scan_spectrum.py` | Wideband sweep that peak-picks candidate covert carriers |
| `waterfall.py` | Spectrogram plot of a capture (matplotlib) |
| `demod_ook.py` | Generic OOK/ASK demod for mem-bus or AirHopper-style captures |
| `demod_fm.py` | FM discriminator path for lab 04 live captures |

## Install (when the dongle arrives)

```bash
sudo apt install -y rtl-sdr python3-rtlsdr gnuradio gr-osmosdr gqrx-sdr
pip3 install pyrtlsdr
```

## Typical live flow

```bash
# 1) Scan for energy near expected bus harmonics or the FM band
python3 tools/scan_spectrum.py --freq-start 88e6 --freq-stop 108e6 --step 100e3

# 2) Capture around a hit
python3 tools/capture.py --freq 97.9e6 --rate 1.024e6 --seconds 5 -o recordings/fm_hit.c64

# 3) Demodulate
python3 labs/04-gpu-display-fm/receiver.py recordings/fm_hit.c64   # if wired
# or
python3 tools/demod_fm.py recordings/fm_hit.c64
```

## No hardware?

Generate a synthetic capture and demodulate it:

```bash
python3 tools/capture.py --simulate --mod ask --payload "TEST" -o recordings/sim_ask.c64
python3 tools/demod_ook.py recordings/sim_ask.c64
```
