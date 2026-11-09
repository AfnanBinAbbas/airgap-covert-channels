# Lab 02: RF Memory-Bus Exfiltration (GSMem / MAGNETO-class)

**Class**: covert RF emission from the DDR memory bus, HDMI, or PCIe clocks on an air-gapped host.
**Papers**: Guri et al. *GSMem* (cellular-band memory bus), *MAGNETO* and *CONTROVERSY* (memory-bus RF), and van Eck TEMPEST for displays.

## Threat model
- Victim: air-gapped host where malware stresses memory or toggles patterns so as to bias bus emissions at harmonic frequencies, such as approximately 100 MHz DDR clock harmonics, or GSM 900/1800 if the front-end couples.
- Attacker: RTL-SDR in the FM, GSM, or ISM band within tens of metres, which demodulates OOK or FSK keyed by memory traffic.
- Channel: RF with no network and no acoustic requirement.

## What runs here
1. `emitter.py` converts the payload into a memory-pattern schedule and a synthesized bus-radiation waveform, which uses a narrowband carrier at a harmonic with keying.
2. `channel_sim.py` models path loss, multipath, phase noise, and front-end quantisation.
3. `receiver.py` performs downconversion, matched filtering, symbol sync, and FEC decoding.
4. `run_sim.py` reports BER against SNR.

## Live hardware path
- Victim: run `emitter_live.py`, which allocates or touches pages in an OOK pattern, or applies DDR stress with patterned writes.
- Attacker: capture with `rtl_sdr` at the chosen centre frequency, then run `receiver.py capture.c64`.

```bash
# Example capture. Adjust the frequency to your lab's bus harmonic, and scan first.
rtl_sdr -f 100.2M -s 1.024M -n 2048000 -g 40 capture.bin
```

## Detection (blue team)
- RF monitoring near air-gapped zones, shielded cages, and TEMPEST-rated memory modules or chassis.
