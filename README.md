# uz-miata-cooling

3UZ-FE (NA, stock) in an NA Miata: does the UZ coolant bypass restrictor work, and what actually fixes track overheating?

- **Calculator:** https://claude.ai/artifact/N1LKTWgZSezZiL6yhgocFd (source `app/`; `app/build.sh` inlines `sim.js` into `index.html`)
- **Model:** `model/uz-cooling-1d.py` — 1D transient loop (pump curve, block, inlet-side thermostat, 28 mm bypass + restrictor, IL Motorsport 42 mm radiator, oil node + oil cooler). `sim.js` is a 1:1 JS port (parity within 0.1 °C).
- **Results + calibration:** `results/uz-cooling-log.md`, panels in `results/panels/`.

## Verdict (30 °C, 65 % WOT, 20 min)
| setup | ECT end |
|---|---|
| stock bypass 28 mm | 135 °C, boils @4.3 min (56 % of flow skips the radiator) |
| 14 mm restrictor | 127 °C |
| 10 mm | 125 °C |
| blocked + thermostat | boils in 81 s — don't |
| delete kit | 122 °C |
| 60 mm rad + sealed duct + 14 mm + oil cooler own duct | ~93 °C |

Restrictor is real (−5…−10 °C) but the radiator air side is the limit. Absolute temps ±20 °C (calibrated on forum track data, no 3UZ logs); deltas are solid.
Adapt Lab restrictor fits 90-97 non-VVTi and 2002+ 3UZ water inlet housing 16032-50110.
