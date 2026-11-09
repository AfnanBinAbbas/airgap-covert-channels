# Lab 04: GPU / Display FM Covert Channel (AirHopper-class)

**Class**: exfiltration of data from an air-gapped host via FM radio, which uses GPU or display memory-bus emissions that couple into a monitor cable as an antenna, or intentional GPU memory modulation.
**Papers**: Guri et al. *AirHopper* (two-way FM) and *AirHopper* mobile receiver, plus related *LED-it-go*, *xLED* (LED clock), and *GSMem*.

## Threat model
- Victim: air-gapped desktop with GPU, where malware modulates GPU memory or pixel patterns so that the display subsystem radiates at an FM subcarrier (or the monitor cable acts as an antenna).
- Attacker: FM receiver (RTL-SDR, car radio, or phone with SDR) in the 88–108 MHz range, which is typically tens of metres with a good antenna.
- Channel: wideband FM subcarrier, which may be intentional or parasitic.

## What runs here
1. `emitter.py` maps the payload to OOK or FSK on FM deviation, so the baseband message drives the FM modulator.
2. `channel_sim.py` models the FM channel, including AWGN, frequency offset, multipath, and the capture effect.
3. `receiver.py` performs FM demodulation with a discriminator, then makes bit decisions and applies FEC.
4. `run_sim.py` runs a BER sweep and decodes the result.

## Live hardware path
- Victim: patterned fullscreen blits or GPU compute at the keying rate, which is AirHopper-style, or use the HDMI cable as an emitter with careful lab shielding of other bands.
- Attacker: capture with `rtl_sdr -f 97.9M -s 1.024M ...` or gqrx, record audio, then run `receiver.py`.
- Choose a **clear** FM frequency in your country's band, keep power low, and use the lab only.

## Detection (blue team)
- Spectrum monitoring of the FM band near sensitive buildings, GPU and driver attestation, blocking GPU on high-security air-gapped hosts, and cable shields.
