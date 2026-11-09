# TEMPEST near-field methodology (lab)

## 1. Scope
Use authorised lab hosts only, and log the scope in the engagement workspace.

## 2. Probe
- **H-field**: a 5–10 turn loop, about 2–5 cm in diameter, connected to the SDR with coax via a balun or unun if needed.
- **E-field**: a telescopic whip or a long wire with high impedance.
- Placement: the midpoint of the video cable, a chassis vent, the keyboard cable, or the USB root hub area.

## 3. Frequency search
Pixel clocks are strong anchors:

| Source | Typical fundamental |
|---|---|
| VGA 640×480@60 | 25.175 MHz |
| SVGA 800×600@60 | 40.0 MHz |
| XGA 1024×768@60 | 65.0 MHz |
| HDMI TMDS | 25 MHz × N, which is related to the data rate |

Search harmonics and sidebands, and use `scan_spectrum.py` with `--step 25e3` near candidates.

## 4. Sync strategy for real video recovery, which is advanced
1. Detect the hsync comb spacing, which equals 1 divided by the horizontal period.
2. Mix to baseband, then integrate lines.
3. Trigger on vsync if it is leaked, because it is often weaker.
4. Sample at the pixel rate with a recovered PLL, and map to RGB via colour-space assumptions.
5. This lab does **not** implement full video; we prove data correlation via pattern OOK instead.

## 5. Lab proof-of-leak, which is what we automate
Simulate a carrier at the pixel-clock harmonic, which is amplitude-keyed by a test pattern bitstream.
The receiver then performs energy detection and symbol integration, after which it recovers the pattern bits and CRC.
For live work, replace the simulation with an RTL-SDR capture of a lab monitor that shows a blinking test pattern you control.
