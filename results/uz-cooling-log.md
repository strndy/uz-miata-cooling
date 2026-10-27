# 3UZ-FE NA Miata — coolant bypass restrictor study (1D loop model)

Question: does Adapt Lab's bypass restrictor help? (https://adapt-lab.com/2025/07/27/beat-the-heat-why-every-uz-engine-needs-adapt-labs-coolant-bypass-restrictor/)
Model: scripts/uz-cooling-1d.py (1D transient hydraulic+thermal loop, runs locally in ~2 s), panel: scripts/uz-cooling-viz.py.

Inputs (Jan, 2026-10-27): 3UZ NA stock, stock pump, stock inlet-side stat 82 open / 90 full,
2mm jiggle hole, NO bypass disc. Bypass 28mm. Radiator IL Motorsport NA0-5051 (670x415, 42mm core),
engine 38mm hoses, rad necks 32mm. Heater plumbed, no flow. 30C air, 65% WOT, start 70C stat closed,
50/50, 1.1 bar.
Assumed: coolant heat = 0.55 x brake power at WOT (band 0.45-0.65), 8 kW off-throttle;
rad face velocity = 0.22 x car speed (band 0.16-0.30); generic 100 s lap, 6 straights.
Absolute temps are +-25C (no logs). Deltas between cases are the trustworthy output.

RESULT stock fc=0.55 duct=0.22 ECT_end=118.7 ECT_max=119.9 metal_max=139.5 Qr=93 Qb=117 L/min (56% bypass) q_in=78.4 kW t110=220s band_end=93-155C

## Calibration vs forum data (2026-10-27) — defaults moved to fc=0.70, duct=0.25
Literature: SI full-load coolant heat ~0.7-1.0 kW per kW brake (Heywood-class rule; oil heat lumped in here).
Face velocity: ~25% of car speed ducted race car (gt40s SuperLite), ~40% production car at highway (patent).
Anecdote 1: 250whp turbo Miata, 55mm Koyo, full duct + hood vent, <=21C -> ~110C (230F). Model fits fc 0.65@0.22 / 0.75@0.30.
Anecdote 2: SC Miata (~140 kW), 37mm Koyo, SoCal summer -> 96-102C. Model fits fc 0.65-0.75 @0.30.
Vendor: UZ "under severe stress ... 220F+" (104C); w/ restrictor + 170F stat 183-193F.
=> 0.55 was optimistic. New band fc 0.60-0.80 x duct 0.20-0.30.

RESULT stock fc=0.70 duct=0.25 ECT_end=134 boil@269s band_end=112-164C (boils in 6 of 9 corners)

## Round 1 comparison (2026-10-27) — same session, nominal fc=0.70 duct=0.25, IL 42mm
Model change: +15 W/K conduction engine->inlet housing (pellet) so blocked+stat eventually opens.
RESULT stock   ECT_end=135 Qr=93  Qb=117 boil@267s
RESULT r18     ECT_end=130 Qr=114 Qb=90  boil@359s
RESULT r14     ECT_end=127 Qr=134 Qb=63  touches boil @568s
RESULT r10     ECT_end=125 Qr=153 Qb=35
RESULT blocked ECT_end=n/a (runaway) — stat sees only 2mm-jiggle water cooled by radiator -> opens late -> boil @81s
RESULT delete  ECT_end=122 Qr=185 Qb=0
Radiator/duct matrix (ECT_end): stock 42/0.25=135, 42/0.35=118, 55/0.35=106, 60/0.35=103;
 r14 60/0.35=97; delete 60/0.35=92.
Verdict: article direction CONFIRMED (stock UZ bypass steals 56% of flow; restrictor -5..-10C, delete -13C),
but on a 42mm Miata rad it does not stop boiling. Ducting (0.25->0.35: -17C) and core (42->60: -17C) are the big levers.
Caveat: restrictor gain rides on turbulent coolant-side h ~ Q^0.8 in rad tubes; if tubes are laminar the gain halves.

## Round 2 — oil cooler (2026-10-27)
Model: oil node (6 L), f_oil=0.22 of engine heat into oil, oil<->coolant 800 W/K via block; no-cooler baseline
unchanged (135C) so calibration holds. Cooler: 20% of rad face, stacked (strip air x0.75), 15 L/min via
80-90C sandwich stat, ~13 kW. 'front' preheats that radiator strip to ~75C; 'side' = own duct, clean air.
RESULT oc 42mm/0.25 ECT(oil): stock none 135(162) front 130(140) side 120(130); r14 127(154) 124(135) 114(124);
       delete 122(149) 119(131) 110(121). Deltas hold across fc 0.6-0.8.
RESULT oc 60mm/0.35 ECT(oil): stock 103(130) 101(113) 95(107); r14 97(124) 96(109) 93(105); delete 92(119) 91(105) 85(99)
Verdict: front-mounted cooler = coolant -3..-5C, oil -17..-22C. Own duct = coolant -10..-15C. Without a cooler oil ~150-160C on 42mm rad.
