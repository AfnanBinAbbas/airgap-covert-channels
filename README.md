# Air-Gap Covert Channel Lab Suite

Reproduction labs for published air-gap attack research. The techniques covered include RF, EM and acoustic covert channels, keyboard emanations, memory-bus leakage, and TEMPEST-class near-field work.

**Scope**: authorised lab use only, which means your own machines and your own RF or analog test range. These are educational proofs of concept for peer-reviewed techniques, such as the Ben-Gurion AirHopper, GSMem, Fansmitter and Keysweeper work, together with classic TEMPEST. They must not be used against third parties.

## Lab map

| Lab | Technique class | Channel | Hardware needed | Runs offline? |
|---|---|---|---|---|
| 01 | Fansmitter-class fan/acoustic exfil | Audio (speaker to mic) | Speakers + mic (or loopback) | Yes (sim) |
| 02 | GSMem-class memory-bus RF exfil | RF (DDR/HDMI harmonic) | RTL-SDR + antenna (or sim) | Yes (sim) |
| 03 | Keysweeper-class keyboard EM keylog | RF/EM near-field | RTL-SDR + loop/probe (or sim) | Yes (sim) |
| 04 | AirHopper-class GPU/display FM | FM subcarrier (88–108 MHz) | RTL-SDR + antenna (or sim) | Yes (sim) |
| 05 | Shared SDR receiver stack | All RF labs | RTL-SDR / HackRF | Capture needs HW |
| 06 | TEMPEST near-field cable emanation | EM near-field | H-field probe + SDR | Analysis-only sim |

Every lab provides an **emitter**, which runs on the victim or air-gapped box in the simulation (or acts as the conceptual malware), and a **receiver or demodulator** on the attacker side. Simulation mode uses a synthetic noisy channel so that you can verify the bit error rate end-to-end with no hardware at all.

## Quick start (no hardware)

```bash
cd airgap-covert-channels
pip3 install -r requirements.txt   # numpy and scipy are already present

# Run all sims end-to-end
python3 labs/01-acoustic-fan-channel/run_sim.py
python3 labs/02-rf-mem-bus/run_sim.py
python3 labs/03-keyboard-emanations/run_sim.py
python3 labs/04-gpu-display-fm/run_sim.py
```

Results are written to `results/`, which contains JSON bit error rates and decoded payloads.

## Hardware shopping list (to go live)

| Item | Purpose | Approx |
|---|---|---|
| RTL-SDR v3/v4 (RTL2832U + R820T2) | RX for labs 02–05 | $25–35 |
| Small whip or telescopic antenna | FM/GSM-band RX | $10 |
| Near-field H-field probe (or loop of coax) | Lab 06 + keyboard EM | $20 DIY |
| USB sound card, small speaker and electret mic | Lab 01 live | $15 |
| Optional: HackRF One | TX tests, wider band | $300+ |

Install the SDR stack when the hardware arrives:

```bash
sudo apt update
sudo apt install -y rtl-sdr hackrf gnuradio gr-osmosdr gqrx-sdr sox python3-rtlsdr
```

## Directory layout

```
airgap-covert-channels/
  common/           shared framing, modulation, channel sim, metrics
  labs/0N-*/        emitter + receiver + run_sim.py per technique
  tools/            capture helpers (rtl_sdr wrappers, recording)
  recordings/       IQ / audio captures (when live)
  results/          BER, decoded payloads, plots
```

## Blue-team notes (each lab also documents detection)

- Acoustic: fan RPM control is anomalous, so acoustic anomaly sensors near servers are useful.
- RF mem-bus: use shielded rooms, TEMPEST-rated chassis, and RF sniffing near air-gapped hosts.
- Keyboard EM: use Faraday keyboard enclosures, and detect unusual RX near user desks.
- AirHopper FM: monitor the FM band for spectrum activity near sensitive buildings.
- TEMPEST: use cable shielding, distance, and white-noise generators (NSA-style).

## References (start here)

- Guri et al., *AirHopper* (FM/GPU), *GSMem* (memory bus), *Fansmitter* (disk/fan),
  *BitWhisper* (thermal), *KeySweeper* (keyboard RF), *SATAN* (satellite),
  *MAGNETO* / *CONTROVERSY* (memory-bus RF), *TEMPEST* (van Eck / pollin).
- The full paper list is in each lab's own `README.md`.
