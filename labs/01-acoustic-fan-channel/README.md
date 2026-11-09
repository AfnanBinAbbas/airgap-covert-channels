# Lab 01: Acoustic / Fan Covert Channel (Fansmitter-class)

**Class**: air-gap exfiltration via acoustic emanations from chassis fans or disk actuators.
**Papers**: Guri et al. *Fansmitter* (disk acoustic) and *Fansmitter* fan-RPM variants. The related *BitWhisper* work is thermal rather than acoustic.

## Threat model
- Victim: air-gapped host with no NIC up, where malware can control fan PWM or disk I/O patterns.
- Attacker: a microphone (or smartphone) within acoustic range, which is typically several metres, records and demodulates RPM or frequency-shifted tones.
- Channel: discrete acoustic tones, for example 400–1000 Hz, that are keyed by bit and produced by modulating fan speed or seek patterns.

## What runs here
1. `emitter.py` encodes the payload as a fan-RPM keying schedule, or as direct tone synthesis for the bench.
2. `channel_sim.py` models the speaker-to-mic path with noise, room reverb approximation, and mic AGC.
3. `receiver.py` applies bandpass filtering, envelope detection, and symbol sync, then decodes bits with CRC checking.
4. `run_sim.py` runs an end-to-end BER sweep, which needs no hardware.

## Live hardware path
- Victim: `emitter_live.py` sets the fan curve via `pwmconfig`, `ipmitool`, or `nc` on the lab box, or plays tones on the internal speaker.
- Attacker: record with `arecord -f S16_LE -r 48000 mic.wav`, then run `receiver.py mic.wav`.

## Detection (blue team)
- Unusual constant-tone fan acoustics, and RPM telemetry that is inconsistent with load.
- Acoustic anomaly mics in server rooms, together with a whitelist of legitimate fan harmonics.
