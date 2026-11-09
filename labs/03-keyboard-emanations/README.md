# Lab 03: Keyboard EM Keylogger (Keysweeper-class)

**Class**: recovery of keystrokes from electromagnetic emanations of keyboard cabling or the controller (PS/2, membrane, and some USB).
**Papers**: Martin and Haystack *Keysweeper*, related *TEMPEST* keyboard attacks, and *KOPIS* (image of keystrokes via EM).

## Threat model
- Victim: a user types on a keyboard attached to an air-gapped or isolated machine, while the attacker has a coil or probe, or a compromised "USB stick" skimmer, nearby.
- Attacker: an SDR or dedicated receiver captures EM transients that are unique per key scancode, including timing and waveform.
- Channel: impulsive EM near-field rather than intentional RF.

## What runs here
1. `emitter.py` provides synthetic per-key EM impulse templates and scancode timing from a QWERTY dictionary.
2. `channel_sim.py` models noise, the impulse response of the cable, and sampling jitter.
3. `keymodel.py` performs per-key feature extraction, such as rise time, peak, and spectral centroid.
4. `classifier.py` applies a template or ML classifier and produces a keystroke string.
5. `run_sim.py` types a secret phrase, recovers it, and reports accuracy.

## Live hardware path
- Probe: a small loop of coax or an H-field probe near the keyboard cable or controller.
- Capture: `rtl_sdr` at a high sample rate at IF after downconversion, or a scope.
- Calibrate: press known keys many times so that you can build templates, then classify unknowns.

## Detection (blue team)
- Faraday-shielded keyboards and cables, detection of unauthorised RF receivers near desks, and behavioural checks for keyboard use on machines with no network but odd RF activity.
