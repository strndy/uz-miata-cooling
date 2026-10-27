#!/usr/bin/env python3
"""1D transient cooling-loop model: 3UZ-FE V8 in an NA Miata, track session.

Loop (inlet-side thermostat, Toyota UZ layout):
  pump -> engine jacket -> outlet node (ECT sensor) -+-> upper hose -> radiator -> lower hose -> THERMOSTAT -+-> inlet housing (mix, stat pellet) -> pump
                                                     +-> bypass 28mm (+ restrictor) -------------------------+
Heater core: Miata has no heater valve, so it always flows as a second small bypass (--no-heater / case blockedNH = deleted).

Hydraulics: quasi-steady each step. Pump dp = p0*(n/6000)^2 - c*Q^2, branches k*Q^2
(k in kPa/(L/s)^2). Thermal: engine metal node + jacket coolant node + plug-flow
cells for hoses/radiator/bypass. Radiator: air is Cmin (per-cell eps = 1-exp(-NTU)).

Usage: uz-cooling-1d.py CASE [--fc 0.55] [--duct 0.22] [--out dir]
  CASE: stock | r18 | r14 | r10 | blocked | blockedNH (blocked + heater deleted) | delete   (rNN = restrictor bore mm)
        add '+wornNN' (thermostat reaches NN% lift) or '+nodisc' (no bypass disc), e.g. r14+worn60, stock+nodisc
"""
import argparse, json, math, os
import numpy as np

RHO, CP = 1030.0, 3600.0          # 50/50 glycol @ ~90C
RHO_AIR, CP_AIR, T_AIR = 1.16, 1007.0, 30.0
HALF_RHO = RHO / 2 * 1e-9         # k[kPa/(L/s)^2] = K * HALF_RHO / A^2

def k_from_K(K, d_mm):
    A = math.pi / 4 * (d_mm / 1000) ** 2
    return K * HALF_RHO / A ** 2

def k_orifice(cdA):
    return HALF_RHO / cdA ** 2

def k_restrictor(d_mm, D_mm=28.0):
    """Sleeve restrictor in a 28mm bore (l/d~1): entry contraction + Borda expansion."""
    b2 = (d_mm / D_mm) ** 2
    K_o = 0.5 * (1 - b2) ** 0.75 + (1 - b2) ** 2   # ref. orifice velocity
    return k_from_K(K_o, d_mm)

P = dict(
    # pump (stock mechanical, crank-speed): shutoff 150 kPa @6000
    p0=150.0, c_pump=4.0,
    k_eng=4.44,                          # 40 kPa @ 3 L/s through block+heads
    k_rad_core=2.4,                      # 15 kPa @ 2.5 L/s
    k_hoses=k_from_K(3.0, 38),           # upper+lower 38mm, ~3 m + bends
    k_necks=k_from_K(0.3, 32),           # 38->32->38 at Miata rad necks
    k_bypass=k_from_K(2.5, 28),          # 28mm bypass, entry+2 bends+exit
    k_heater=k_from_K(12, 16),           # heater core loop, 16mm hoses (Miata: no valve, always flows)
    stat_open=82.0, stat_full=90.0, stat_tau=15.0,
    hA_housing=15.0,                     # W/K conduction engine->inlet housing/pellet (alu housing bolted to block)
    stat_cdA_full=0.6 * math.pi * 0.034 * 0.010,   # ~34mm valve x 10mm lift curtain (Toyota spec >=10mm @95C)
    stat_cdA_jiggle=0.6 * math.pi / 4 * 0.002 ** 2,
    # thermal masses / volumes
    m_metal_cp=80 * 900,                 # ~80 kg alu-equiv [J/K] (oil is its own node)
    # oil: f_oil of engine heat lands in oil (bearings, pistons, valvetrain); without a cooler it all ends in coolant
    f_oil=0.22, C_oil=6 * 0.85 * 2100, hA_oil_cool=800.0,     # 6 L; oil<->coolant via block/liners W/K
    oc_frac=0.20, oc_block=0.75,         # oil cooler face = 20% of rad face; stacked -> that strip's air x0.75
    oc_flow=15.0, oc_open=80.0, oc_full=90.0,   # L/min via thermostatic sandwich plate
    oc_hA_oil=500.0,                     # oil-side W/K at full flow (viscous, ~19-25 row stacked plate)

    V_eng=5.5, V_up=0.8, V_rad=2.4, V_low=0.8, V_bp=0.2, V_mix=0.3,   # L
    hA_jacket=4000.0, Q_jacket_ref=3.0,  # W/K @ 3 L/s, ~Q^0.8, floor
    hA_jacket_min=800.0,
    # radiator IL Motorsport NA0-5051: 670x415 overall, 42mm core
    rad_face=0.56 * 0.34,                # m^2 core face (tanks/brackets off)
    hA_air_ref=1700.0, v_ref=7.0,        # W/K @ 7 m/s face (~14 m2 louvered fin, h~140, eta 0.85), ~v^0.6
    hA_cool_ref=6000.0, Qc_ref=2.0, hA_cool_min=1500.0,   # 2-row flat tubes ~1.8 m2 inner
    fan_min_face=2.5,                    # m/s face from fans at low speed
    t_air=30.0, core_mm=42.0,            # ambient; core depth (hA_air ~ depth^0.8, coolant side ~ depth)
    p_cap_bar=1.1, T_boil=128.0,         # 50/50 @ 1.1 bar gauge
    q_off=8000.0,                        # W to coolant off-throttle
)

def torque_wot(rpm):  # 3UZ-FE: 434 Nm @3400, 216 kW @5600
    return 434 - 66 * ((rpm - 3400) / 2200) ** 2

GEAR_TOP = [18, 27, 37, 48, 62]   # m/s at 6200 rpm, per gear
SHIFT = 6500                      # shift point rpm

def rpm_from_v(v):
    for g in GEAR_TOP:
        if v <= 0.98 * g * SHIFT / 6200:
            return max(1500.0, 6200 * v / g)
    return float(SHIFT)

# lap: (WOT seconds, corner speed after the braking zone m/s, off-throttle seconds)
LAP = [(12, 22, 5), (6, 28, 4), (20, 18, 7), (8, 25, 5), (10, 30, 4), (9, 20, 10)]  # 65 s WOT / 35 s off

def lap_profile(dt):
    """Returns arrays over one lap: throttle(0/1), speed m/s, rpm."""
    th, vs, rs = [], [], []
    v = 22.0
    for wot, vc, off in LAP:
        for _ in range(int(wot / dt)):
            v += dt * 5.0 * (1 - (v / 65.0) ** 2)
            th.append(1); vs.append(v); rs.append(rpm_from_v(v))
        for _ in range(int(off / dt)):
            v = max(vc, v - 9.0 * dt)
            th.append(0); vs.append(v); rs.append(rpm_from_v(v))
    return np.array(th), np.array(vs), np.array(rs)

def eps_xflow(NTU, Cr):
    if Cr < 1e-6:
        return 1 - math.exp(-NTU)
    return 1 - math.exp((NTU ** 0.22 / Cr) * (math.exp(-Cr * NTU ** 0.78) - 1))

def run(case, fc=0.75, duct=0.25, t_end=1200.0, dt=0.02, overrides=None, oc='none', heater=True):
    p = dict(P, **(overrides or {}))
    # case = tokens joined by '+': stock | rNN (restrictor bore) | blocked | blockedNH (blocked + heater deleted) | delete
    #                               | wornNN (thermostat reaches NN % of its 10 mm lift) | nodisc (thermostat without bypass disc)
    toks = case.split('+')
    base = toks[0]
    has_stat = base != 'delete'
    x_max = 1.0
    disc = True
    for t in toks[1:]:
        if t.startswith('worn'):
            x_max = float(t[4:]) / 100
        elif t == 'nodisc':
            disc = False
        elif t.startswith('r'):
            base = base if base != 'stock' else t
        else:
            raise SystemExit(f'unknown case token {t}')
    if base == 'nodisc':
        disc, base = False, 'stock'
    if base.startswith('worn'):
        x_max, base = float(base[4:]) / 100, 'stock'
    if base == 'stock':
        k_bp = p['k_bypass']
    elif base.startswith('r'):
        k_bp = p['k_bypass'] + k_restrictor(float(base[1:]))
    elif base in ('blocked', 'delete', 'blockedNH'):
        k_bp = None
        if base == 'blockedNH':
            heater = False
    else:
        raise SystemExit(f'unknown case {case}')
    # bypass disc on the back of the thermostat: curtain pi*28mm*gap, gap = 10mm*(1-lift) + 0.3mm leak when seated
    k_disc = (lambda xx: k_orifice(0.6 * math.pi * 0.028 * (0.010 * (1 - xx) + 0.0003))) if (has_stat and disc) else (lambda xx: 0.0)

    th, vs, rs = lap_profile(dt)
    nlap = len(th)
    # cells (plug flow)
    n_up, n_rad, n_low, n_bp = 6, 12, 6, 3
    T0 = 70.0
    up = np.full(n_up, T0); rad = np.full(n_rad, T0); low = np.full(n_low, T0); bp = np.full(n_bp, T0)
    T_eng, T_mix, T_metal, T_sense, T_oil = T0, T0, T0 + 3, T0, T0
    k_rad_fixed = p['k_rad_core'] + p['k_hoses'] + p['k_necks']
    face = p['rad_face']
    log = []
    steps = int(t_end / dt)
    for i in range(steps):
        j = i % nlap
        thr, v, rpm = th[j], vs[j], rs[j]
        s = rpm / 6000.0
        # thermostat lift
        if has_stat:
            x = min(x_max, max(0.0, (T_sense - p['stat_open']) / (p['stat_full'] - p['stat_open'])))
            cdA = p['stat_cdA_jiggle'] + x * p['stat_cdA_full']
            k_r = k_rad_fixed + k_orifice(cdA)
        else:
            x = 1.0
            k_r = k_rad_fixed
        sr = 1 / math.sqrt(k_r)
        sb = 0.0 if k_bp is None else 1 / math.sqrt(k_bp + k_disc(x))
        sh = 1 / math.sqrt(p['k_heater']) if heater else 0.0
        ssum = sr + sb + sh
        k_par = 1 / ssum ** 2
        Q = s * math.sqrt(p['p0'] / (p['c_pump'] + p['k_eng'] + k_par))   # L/s
        Qr, Qb, Qh = Q * sr / ssum, Q * sb / ssum, Q * sh / ssum
        mr, mb, mh, m = Qr * RHO / 1000, Qb * RHO / 1000, Qh * RHO / 1000, Q * RHO / 1000      # kg/s

        # heat input
        q_in = fc * torque_wot(rpm) * rpm * 2 * math.pi / 60 if thr else p['q_off']
        hA_j = max(p['hA_jacket_min'], p['hA_jacket'] * (Q / p['Q_jacket_ref']) ** 0.8)
        q_mc = hA_j * (T_metal - T_eng)
        T_metal += dt * ((1 - p['f_oil']) * q_in - q_mc) / p['m_metal_cp']
        q_oil_cool = p['hA_oil_cool'] * (T_oil - T_eng)
        # engine jacket coolant (well mixed), inflow from mix node
        C_eng = p['V_eng'] / 1000 * RHO * CP
        T_eng += dt * (q_mc + q_oil_cool + m * CP * (T_mix - T_eng)) / C_eng

        # radiator air side
        v_face = max(p['fan_min_face'], duct * v)
        dpt = p['core_mm'] / 42.0
        hA_c = max(p['hA_cool_min'], p['hA_cool_ref'] * (Qr / p['Qc_ref']) ** 0.8) * dpt
        # air streams through the radiator: [clean, behind-oil-cooler]
        fr = p['oc_frac'] if oc == 'front' else 0.0
        vb = v_face * p['oc_block']
        q_oc = 0.0; T_pre = p['t_air']
        if oc in ('front', 'side'):
            v_oc = vb if oc == 'front' else v_face
            C_a = RHO_AIR * face * p['oc_frac'] * v_oc * CP_AIR
            xo = min(1.0, max(0.05, (T_oil - p['oc_open']) / (p['oc_full'] - p['oc_open'])))
            C_o = xo * p['oc_flow'] / 60000 * 870 * 2100
            hAa_oc = p['hA_air_ref'] * p['oc_frac'] * (v_oc / p['v_ref']) ** 0.6
            UA_oc = 1 / (1 / hAa_oc + 1 / (p['oc_hA_oil'] * xo ** 0.8))
            Cmin, Cmax = min(C_a, C_o), max(C_a, C_o)
            q_oc = eps_xflow(UA_oc / Cmin, Cmin / Cmax) * Cmin * (T_oil - p['t_air'])
            if oc == 'front':
                T_pre = p['t_air'] + q_oc / C_a
        streams = [(1 - fr, v_face, p['t_air'])] + ([(fr, vb, T_pre)] if fr > 0 else [])
        eps_s = []
        for af, vv, Ta in streams:
            hA_a = p['hA_air_ref'] * af * (vv / p['v_ref']) ** 0.6 * dpt ** 0.8
            UA = 1 / (1 / hA_a + 1 / (hA_c * af))
            ma_c = RHO_AIR * face * af * vv / n_rad
            eps_s.append((1 - math.exp(-(UA / n_rad) / (ma_c * CP_AIR)), ma_c, Ta))
        T_oil += dt * (p['f_oil'] * q_in - q_oil_cool - q_oc) / p['C_oil']

        # plug-flow advection (upwind) with mass-weighted cells
        def adv(cells, T_in, mdot, V):
            if mdot <= 0:
                return cells
            Cc = V / 1000 / len(cells) * RHO * CP
            a = mdot * CP * dt / Cc
            new = cells.copy()
            new[0] += a * (T_in - cells[0])
            new[1:] += a * (cells[:-1] - cells[1:])
            return new
        up = adv(up, T_eng, mr, p['V_up'])
        rad = adv(rad, up[-1], mr, p['V_rad'])
        q_cells = sum(e * mc * CP_AIR * (rad - Ta) for e, mc, Ta in eps_s)
        rad -= dt * q_cells / (p['V_rad'] / 1000 / n_rad * RHO * CP)
        q_rad = q_cells.sum()
        low = adv(low, rad[-1], mr, p['V_low'])
        if mb > 0:
            bp = adv(bp, T_eng, mb, p['V_bp'])
        # inlet housing mix node (pellet sits here, bathed by bypass)
        C_mix = p['V_mix'] / 1000 * RHO * CP
        T_mix += dt * (mr * CP * (low[-1] - T_mix) + mb * CP * (bp[-1] - T_mix) + mh * CP * (T_eng - T_mix) + p['hA_housing'] * (T_metal - T_mix)) / C_mix
        T_sense += dt * (T_mix - T_sense) / p['stat_tau']

        if i % int(1.0 / dt) == 0:
            log.append(dict(t=i * dt, T_ect=T_eng, T_metal=T_metal, T_rad_in=up[-1], T_rad_out=rad[-1],
                            T_mix=T_mix, T_oil=T_oil, q_oc=q_oc / 1000, T_pre=T_pre, lift=x, Q=Q * 60, Qr=Qr * 60, Qb=Qb * 60, Qh=Qh * 60,
                            q_in=q_in / 1000, q_rad=q_rad / 1000, v=v, rpm=rpm, v_face=v_face))
    return log

def summarize(log):
    t = np.array([r['t'] for r in log]); T = np.array([r['T_ect'] for r in log])
    last = t >= t[-1] - 300
    def tcross(th):
        idx = np.where(T >= th)[0]
        return float(t[idx[0]]) if len(idx) else None
    return dict(
        T_ect_max=float(T.max()), T_ect_last5min=float(T[last].mean()),
        T_metal_max=float(max(r['T_metal'] for r in log)),
        T_oil_last5min=float(np.mean([r['T_oil'] for r, l in zip(log, last) if l])),
        q_oc_last5=float(np.mean([r['q_oc'] for r, l in zip(log, last) if l])),
        T_pre_last5=float(np.mean([r['T_pre'] for r, l in zip(log, last) if l])),
        Qr_mean=float(np.mean([r['Qr'] for r in log if r['t'] > 120])),
        Qb_mean=float(np.mean([r['Qb'] for r in log if r['t'] > 120])),
        q_in_mean=float(np.mean([r['q_in'] for r in log])),
        q_rad_last5=float(np.mean([r['q_rad'] for r, l in zip(log, last) if l])),
        t_100=tcross(100), t_110=tcross(110), t_boil=tcross(P['T_boil']),
    )

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('case')
    ap.add_argument('--fc', type=float, default=0.75, help='coolant heat / brake power at WOT')
    ap.add_argument('--duct', type=float, default=0.25, help='radiator face velocity / car speed')
    ap.add_argument('--t', type=float, default=1200)
    ap.add_argument('--tair', type=float, default=30.0)
    ap.add_argument('--core', type=float, default=42.0, help='radiator core depth mm')
    ap.add_argument('--oc', default='none', choices=['none', 'front', 'side'], help='oil cooler: none | front (covers 20%% of rad) | side (own duct)')
    ap.add_argument('--no-heater', action='store_true', help='heater core deleted (default: heater loop flows, as on a Miata)')
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    log = run(a.case, a.fc, a.duct, a.t, overrides=dict(t_air=a.tair, core_mm=a.core), oc=a.oc, heater=not a.no_heater)
    s = summarize(log)
    print('RESULT', a.case, f"fc={a.fc} duct={a.duct} tair={a.tair} core={a.core} oc={a.oc} heater={not a.no_heater}", json.dumps({k: (round(v, 1) if isinstance(v, float) else v) for k, v in s.items()}))
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        with open(os.path.join(a.out, f'{a.case}_fc{a.fc}_d{a.duct}' + ('' if a.oc == 'none' else f'_oc{a.oc}') + '.json'), 'w') as f:
            json.dump(dict(case=a.case, fc=a.fc, duct=a.duct, oc=a.oc, summary=s, log=log), f)
