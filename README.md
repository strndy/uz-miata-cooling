# uz-miata-cooling

## ▶ Open the calculator: **https://uz-miata-cooling.onrender.com**

Move the sliders (restrictor bore, thermostat, radiator thickness, ducting, air temp, oil cooler size, thickness and mounting, pump speed, power, track profile, coolant mix, cap), press **Plot**, and it simulates a 20-minute track session in ~0.2 s. **Keep to compare** overlays up to 5 runs.

## Why

UZ V8s (1UZ / 2UZ / 3UZ) swapped into small cars overheat on track. Vendors sell a coolant **bypass restrictor**: a sleeve that narrows the 28 mm bypass in the water inlet housing so more coolant goes through the radiator ([Adapt Lab article](https://adapt-lab.com/2025/07/27/beat-the-heat-why-every-uz-engine-needs-adapt-labs-coolant-bypass-restrictor/)). The article explains the mechanism but shows no test data, and no independent before/after logs could be found.

This project tests that claim with physics for one concrete car: **a stock 3UZ-FE in an NA Miata with a 42 mm aluminium radiator, on track at 30 °C.** It asks three questions. Does the restrictor work? What size? And is it the right fix at all compared with ducting, a thicker radiator or an oil cooler?

## How it calculates

A 1D transient thermal-hydraulic model of the whole coolant loop, stepped every 20 ms over a repeating lap.

### Loop layout

```
pump ─► engine block + heads ─► outlet (ECT sensor) ─┬─► upper hose ─► radiator ─► lower hose ─► THERMOSTAT ─┬─► inlet housing ─► pump
                                                     ├─► bypass 28 mm (+ restrictor) ─────────────────────────┤   (wax pellet sits here)
                                                     └─► heater core (optional, valve open) ──────────────────┘
oil sump ◄─► block (heat exchange) ; oil ─► oil cooler (optional, thermostatic plate)
```

The UZ thermostat is on the **inlet side**: the radiator return and the bypass water mix around the wax pellet before the pump.

### 1. Hydraulics (solved every step)

Every branch is a quadratic loss, `Δp = k·Q²` (k in kPa/(L/s)²). Pipe and fitting losses come from loss coefficients, `k = K·ρ/2 / A²`.

- **Pump** (mechanical, crank speed × pulley ratio n): `Δp = 150·(n/6000)² − 4.0·Q²` kPa. Shut-off 150 kPa at 6000 rpm.
- **Engine block + heads:** k = 4.44 (40 kPa at 180 L/min).
- **Radiator path:** core (15 kPa at 150 L/min) + 38 mm hoses (K≈3) + 38→32→38 mm necks (K≈0.3) + thermostat.
- **Thermostat:** an orifice with `Cd·A = 0.6·(A_jiggle + lift·A_full)`, A_full ≈ 34 mm valve × 9 mm lift. Lift goes linearly from 0 at the opening temp to 1 at opening + 8 °C. The pellet temperature lags the inlet-housing water with τ = 15 s, and also gets a little heat by conduction from the block (15 W/K).
- **Bypass:** 28 mm passage, K≈2.5. The **restrictor** is a sleeve of bore d in the 28 mm bore. Its loss is entry contraction + sudden expansion: `K = 0.5(1−β²)^0.75 + (1−β²)²` (on the sleeve velocity), with `β = d/28`.
- **Heater core (optional):** 16 mm hoses + core, K≈12.

The parallel branches share one pressure drop, so flow splits as `Q_i ∝ 1/√k_i`. The pump operating point is where the pump curve meets `k_engine + k_parallel`. Result for the stock layout at 6000 rpm: ~240 L/min total, 44 % through the radiator.

### 2. Heat input

- 3UZ-FE full-throttle torque: `T = 434 − 66·((rpm − 3400)/2200)²` Nm (434 Nm at 3400, 216 kW at 5600), scaled by the power slider.
- Heat into the engine at full throttle = **fc × brake power**, with fc = 0.70 (calibrated, see below). Off throttle: 8 kW.
- 22 % of that heat goes to the oil (bearings, pistons, valvetrain) and the rest to the metal of the block and heads.

### 3. Thermal nodes

| Node | Capacity | Exchanges with |
|---|---|---|
| Engine metal | 80 kg aluminium-equivalent (72 kJ/K) | coolant jacket, `hA = 4000·(Q/3 L/s)^0.8` W/K (floor 800) |
| Oil | 6 L (10.7 kJ/K) | coolant via block, 800 W/K; oil cooler |
| Jacket coolant (ECT sensor) | 5.5 L, well mixed | pump inflow, metal, oil |
| Upper hose / radiator / lower hose / bypass | 0.8 / 2.4 / 0.8 / 0.2 L | plug flow (6 / 12 / 6 / 3 cells, upwind) |
| Inlet housing (pellet) | 0.3 L | mixes radiator return + bypass + heater |

Plug-flow cells give real transport delays. That's what produces the hot and cold slugs when a thermostat cycles or opens late.

### 4. Radiator

- **Core face:** 560 × 340 mm (NA Miata frame, IL Motorsport NA0-5051, 670 × 415 mm overall).
- **Airflow:** face velocity = `(0.10 + 0.30 × ducting%) × car speed`. 0 % means air spills around the core (10 % of car speed); 100 % means a sealed duct with a hood vent (40 %). Minimum 2.5 m/s from the fans.
- **Air side:** `hA_air = 1700·(v/7)^0.6·(depth/42)^0.8` W/K. That's ~14 m² of louvered fin with h≈140 W/m²K and fin efficiency 0.85 at 7 m/s.
- **Coolant side:** `hA_cool = 6000·(Q_rad/2 L/s)^0.8·(depth/42)` W/K (floor 1500).
- **Heat transfer:** the radiator is split into 12 cells along the coolant path. Each cell is a crossflow exchanger with air as the smaller heat-capacity stream: `ε = 1 − exp(−NTU)` and `q = ε·ṁ_air·cp·(T_coolant − T_air)`.

### 5. Oil cooler

- **Size:** face = share of the radiator face. The page shows the matching row count for a 330 mm wide core with 7.2 mm row pitch. Air side scales like the radiator; oil side 500 W/K at 20 % size and 42 mm thickness, scaled by volume.
- **Oil flow:** 15 L/min through a thermostatic sandwich plate that opens between 80 and 90 °C. Heat transfer uses the ε-NTU crossflow formula with both streams unmixed.
- **In front of the radiator:** that strip of radiator gets 75 % of the airflow (two cores in series) at the oil cooler's outlet air temperature.
- **Own duct:** clean ambient air, no penalty on the radiator.

### 6. Track session

- **Lap:** 100 s with six straights. Full-throttle time (65 % by default) accelerates at `a = 5·(1 − (v/65)²)` m/s², scaled with power. Braking at 9 m/s² down to each corner speed (18–30 m/s).
- **Gearing:** five gears, shifting at 6200 rpm. Average speed ~140 km/h.
- **Start:** whole loop at the start temperature, thermostat closed.
- **Boiling point:** `100 + 0.12·glycol% + 20·cap_bar` °C (50/50 at 1.1 bar ≈ 128 °C). Readings above it aren't physical: the coolant would boil over first.

### 7. Calibration

Two numbers carry most of the uncertainty: **fc** (engine heat into the coolant and oil, per kW of power) and **ducting** (radiator face velocity as a share of car speed). They were checked against:

- **Textbook:** a petrol engine at full load rejects ~0.7–1.0 kW to coolant per kW of brake power (Heywood, *Internal Combustion Engine Fundamentals*).
- **Face velocity:** ~25 % of car speed for a ducted race car ([GT40s forum](https://www.gt40s.com/threads/aero-and-radiators.54970/page-2)), ~40 % for a production car at highway speed.
- **250 whp turbo Miata**, 55 mm Koyo, full ducting and hood vent, ≤21 °C air → ~110 °C on track ([MiataTurbo](https://www.miataturbo.net/race-prep-75/what-considered-normal-hot-track-coolant-temp-64266/)). The model gives 98–112 °C with fc 0.65–0.75.
- **Supercharged Miata** (~140 kW), 37 mm Koyo, summer heat → 96–102 °C (same thread). The model gives 94–104 °C.
- **Adapt Lab** (vendor's own numbers, not independent): UZ under hard use 104 °C and up; with the restrictor and a 77 °C (170 °F) thermostat, 84–89 °C. ([article](https://adapt-lab.com/2025/07/27/beat-the-heat-why-every-uz-engine-needs-adapt-labs-coolant-bypass-restrictor/), [product](https://adapt-lab.com/product/coolant-bypass-restrictor/))

Result: fc = 0.70 and ducting 50 % (face velocity 25 % of car speed) as defaults. Every Plot also re-runs with fc ±0.1 and shows the coolant range.

## Results

Default scenario: 3UZ-FE stock (290 hp), stock water pump, stock inlet-side thermostat (82 °C open / 90 °C full, 2 mm jiggle hole, no bypass disc), 28 mm bypass, IL Motorsport 42 mm aluminium radiator in the NA Miata frame, 30 °C air, 65 % full throttle, start at 70 °C with the thermostat closed.

| Setup | Flow through radiator | Coolant at sensor, last 5 min |
|---|---|---|
| Stock bypass (28 mm, no restrictor) | 93 L/min (**56 % of the pump flow skips the radiator**) | 135 °C, boils after ~4.3 min |
| 18 mm restrictor | 114 L/min | 130 °C, boils after ~6 min |
| 14 mm restrictor | 134 L/min | 127 °C, at the boiling point |
| 10 mm restrictor | 153 L/min | 125 °C |
| Bypass blocked, thermostat fitted | 65 L/min | **boils in ~81 s** (thermostat never sees hot water) |
| Delete kit (no thermostat, bypass blocked) | 185 L/min | 122 °C |
| 60 mm radiator + sealed ducting + 14 mm + oil cooler in its own duct | — | ~93 °C |

- **The restrictor works.** The stock UZ bypass has less resistance than the radiator path, so most of the flow skips the radiator. A restrictor is worth 5–10 °C, with diminishing returns below ~14 mm.
- **It doesn't fix a small radiator.** The air side of the radiator is the limit. Ducting (none → sealed) and core thickness (42 → 60 mm) are each worth ~15–17 °C.
- **Never block the bypass with the thermostat still fitted.** The thermostat sits on the pump inlet and reads the bypass water. Block the bypass and it only sees cold radiator water through its 2 mm hole, so it opens far too late.
- **Oil cooler:** stacked in front of the radiator it removes ~13 kW from the oil but pre-heats 20 % of the radiator to ~75 °C, so coolant drops only 3–5 °C. In its own duct, coolant drops 10–15 °C. Without one, oil sits at ~150–160 °C.
- **Fitment:** the Adapt Lab restrictor fits the 1990–97 non-VVTi and 2002+ 3UZ water inlet housing, part **16032-50110**.

**Accuracy:** absolute temperatures are ±20 °C, because the model is calibrated on forum track data, not on a logged 3UZ Miata. **Differences between setups are the reliable output.** If you have a coolant temperature log from a track session, open an issue: one log pins the calibration.

## Limitations

- No measured 3UZ Miata data yet: absolute temperatures are ±20 °C.
- The restrictor gain assumes turbulent coolant flow in the radiator tubes (h ∝ Q^0.8). If the tubes run laminar, the gain roughly halves.
- No boiling, steam or overflow physics. Coolant just keeps heating above the boiling point, which flags failure but isn't a prediction.
- The "head hot side" trace is a lumped proxy, not a local metal temperature.
- Pump curve and block resistance are estimates (no UZ pump data found).
- Fixed radiator face (NA Miata frame). Fan only sets a minimum air speed.

---

## Repo layout

```
app/app.html     calculator UI (React 18 UMD + htm, hand-drawn SVG charts)
app/sim.js       the model in JavaScript (1:1 port of model/uz-cooling-1d.py, parity within 0.1 °C)
app/build.sh     inlines sim.js into app.html -> app/index.html (the deployed page)
model/           Python reference model + panel scripts (numpy, matplotlib)
results/         study log, calibration notes, panels
```

## Run it

```sh
# calculator: edit app/app.html or app/sim.js, then rebuild before committing (Render serves app/index.html as-is)
sh app/build.sh && python3 -m http.server -d app 8000   # http://localhost:8000

# Python model
pip install numpy matplotlib
python3 model/uz-cooling-1d.py stock                  # cases: stock | r18 | r14 | r10 | blocked | delete
python3 model/uz-cooling-1d.py r14 --core 60 --duct 0.35 --oc side --tair 35
```

Deployed on Render as a static site (publish directory `app`, auto-deploy on push to `main`).

## License

MIT, see [LICENSE](LICENSE).
