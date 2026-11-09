# Lab 06: TEMPEST Near-Field Cable / Display Emanation

**Class**: recovery of video or keyboard-related information from unintentional EM emanations of VGA, DVI, HDMI, or USB cables and the chassis, which is classic TEMPEST or van Eck work.
**Papers**: van Eck (1985), Wim van Eck TEMPEST, NSA TEMPEST protection guides, and modern *xLED*, *LED-it-go*, *GazeTracker* (camera), and *HaMel*.

## Threat model
- Victim: air-gapped workstation driving a monitor, where cables and unshielded portions radiate pixel-clock-related energy and data-correlated sidebands.
- Attacker: H-field probe and SDR, or a van Eck style receiver, within near-field (cm to m), or far-field with a good antenna for strong leaks.
- Channel: unintentional wideband or narrowband EM, which often needs synchronisation to the pixel clock.

## What runs here (analysis and methodology; no live RF required)
1. `methodology.md` covers probe placement, frequency search, and sync strategy.
2. `simulate_leak.py` synthesises a "leaky VGA" capture that combines a pixel clock harmonic with OOK data sidebands.
3. `analyze_leak.py` detects the clock harmonic, demodulates sidebands, and recovers pattern bits, which is lab-level rather than full video.

## Live hardware path
1. Place an H-field probe, such as a loop of RG58 or a commercial probe, on a coiled cable or near a chassis vent.
2. Scan for strong narrowband carriers near known pixel clocks, for example 25.175 MHz VGA or HDMI TMDS multiples.
3. Record IQ, find the horizontal-sync-related comb, and correlate with a known test pattern if you are authorised to do so.
4. Full image recovery needs phase-locked sampling to the pixel clock, which is advanced work; this lab stops at **pattern-bit recovery** as proof of leak.

## Detection / mitigation (blue team)
- Fiber video links, TEMPEST-rated shields, distance, white-noise generators, inspection of cable runs, and disabling unused video outputs on high-side air-gapped hosts.

## Legal
TEMPEST interception of systems that you do not own or authorise is illegal in most jurisdictions. Use lab boxes only.
