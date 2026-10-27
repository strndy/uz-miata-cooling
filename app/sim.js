// 1D cooling-loop model, 3UZ-FE in NA Miata. JS port of scripts/uz-cooling-1d.py (same physics, more knobs).
// Loop: pump -> engine -> outlet(ECT) -+-> rad (via inlet-side thermostat) -+-> inlet housing (pellet) -> pump
//                                      +-> bypass 28mm (+restrictor) ------+
//                                      +-> heater core (optional) ---------+
(function (root) {
  const RHO_AIR = 1.16, CP_AIR = 1007, RHO = 1030;
  const HALF_RHO = RHO / 2 * 1e-9;                    // k[kPa/(L/s)^2] = K*HALF_RHO/A^2
  const area = d_mm => Math.PI / 4 * (d_mm / 1000) ** 2;
  const kK = (K, d) => K * HALF_RHO / area(d) ** 2;
  const kOrif = cdA => HALF_RHO / cdA ** 2;
  function kRestrictor(d, D = 28) {                   // sleeve in 28mm bore: contraction + Borda expansion
    if (d >= D) return 0;
    const b2 = (d / D) ** 2;
    return kK(0.5 * (1 - b2) ** 0.75 + (1 - b2) ** 2, d);
  }
  const torqueWot = rpm => 434 - 66 * ((rpm - 3400) / 2200) ** 2;   // 3UZ-FE stock
  const GEAR_TOP = [18, 27, 37, 48, 62];   // m/s at 6200 rpm per gear (fixed gearing)
  let SHIFT = 6500;
  function rpmFromV(v) {
    for (const g of GEAR_TOP) if (v <= 0.98 * g * SHIFT / 6200) return Math.max(1500, 6200 * v / g);
    return SHIFT;
  }
  const LAP = [[12, 22, 5], [6, 28, 4], [20, 18, 7], [8, 25, 5], [10, 30, 4], [9, 20, 10]]; // wot s, corner m/s, off s

  const DEFAULTS = {
    hp: 290, wot: 65, vTrack: 141, tAir: 30, minutes: 20, tStart: 70,   // vTrack = lap average speed km/h
    duct: 50,            // 0 none .. 100 perfect -> face velocity = (0.10 + 0.30*duct/100) * car speed
    core: 42,            // radiator core depth mm (Miata frame face 560x340)
    bypass: 28,          // restrictor bore mm; 28 = open (stock), 0 = blocked
    heater: true,        // heater loop flows (Miata has no heater valve); false = heater deleted
    stat: true, statOpen: 82,
    statDisc: true,      // Toyota UZ thermostat: a disc on its back closes the bypass as the main valve opens
    statLift: 100,       // thermostat condition: % of the 10 mm design lift it still reaches (worn wax / weak spring < 100)
    pulley: 1.0,         // pump speed / crank speed
    glycol: 50, cap: 1.1,
    ww: false,           // Water Wetter (surfactant): ~+8% coolant-side heat transfer
    ocPct: 0, ocThick: 42, ocMount: 'front', ocModel: 'custom',
    ocStat: true, ocOpen: 80,   // oil thermostat (sandwich plate): opens at ocOpen, full at +10
    fc: 0.75, fOil: 0.22, shift: 6500,
  };

  // Lap: six straights. All speeds (corners, top-speed asymptote, start) scale by f; f is solved so the
  // lap average matches vTrack (f = 1 -> ~141 km/h fast circuit, f ~ 0.4 -> ~60 km/h tight track).
  function lapAt(o, dt, f) {
    const th = [], vs = [], rs = [];
    const sw = (o.wot / 100) / 0.65, so = (1 - o.wot / 100) / 0.35;
    const a0 = 5 * (o.hp / 290) ** 0.6, vmax = 65 * f;
    let v = 22 * f, acc = 0;
    for (const [w, vc, off] of LAP) {
      for (let i = 0, n = Math.round(w * sw / dt); i < n; i++) {
        v += dt * a0 * (1 - (v / vmax) ** 2); th.push(1); vs.push(v); rs.push(rpmFromV(v)); acc += v;
      }
      for (let i = 0, n = Math.round(off * so / dt); i < n; i++) {
        v = Math.max(vc * f, v - 9 * dt); th.push(0); vs.push(v); rs.push(rpmFromV(v)); acc += v;
      }
    }
    return { th, vs, rs, avg: acc / vs.length * 3.6 };
  }
  function lapProfile(o, dt) {
    let f = o.vTrack / 141, L = lapAt(o, dt, f);
    for (let k = 0; k < 4 && Math.abs(L.avg - o.vTrack) > 0.5; k++) { f *= o.vTrack / L.avg; L = lapAt(o, dt, f); }
    return L;
  }

  function run(opts) {
    const o = Object.assign({}, DEFAULTS, opts);
    SHIFT = o.shift;
    const dt = 0.02, steps = Math.round(o.minutes * 60 / dt), every = Math.round(1 / dt);
    const CP = 4190 - 11.8 * o.glycol;
    // coolant-side heat transfer vs mix: glycol is more viscous, worse conductor (h ~ -35% at 50/50 vs water).
    // Normalised to 1.0 at 50/50 so the calibration holds; Water Wetter adds ~8%.
    const hMul = (1 - 0.007 * o.glycol) / 0.65 * (o.ww ? 1.08 : 1);
    const T_boil = 100 + 0.12 * o.glycol + 20 * o.cap;
    const P = {
      p0: 150, c_pump: 4.0, k_eng: 4.44,
      k_rad_fixed: 2.4 + kK(3.0, 38) + kK(0.3, 32),
      k_bypass: kK(2.5, 28), k_heater: kK(12, 16),
      cdA_full: 0.6 * Math.PI * 0.034 * 0.010, cdA_jig: 0.6 * area(2),   // ~34 mm valve, 10 mm lift (Toyota spec: >=10 mm at 95C)
      m_metal_cp: 80 * 900, C_oil: 6 * 0.85 * 2100, hA_oil_cool: 800, hA_housing: 15,
      V_eng: 5.5, V_up: 0.8, V_rad: 2.4, V_low: 0.8, V_bp: 0.2, V_mix: 0.3,
      hA_j: 4000, Qj: 3.0, hA_j_min: 800,
      face: 0.56 * 0.34, hA_air_ref: 1700, v_ref: 7, hA_cool_ref: 6000, Qc_ref: 2, hA_cool_min: 1500,
      fan_min: 2.5, q_off: 8000 * o.hp / 290,
      oc_block: 0.75, oc_flow: 15, oc_open: o.ocOpen, oc_full: o.ocOpen + 10,
    };
    const ductF = 0.10 + 0.30 * o.duct / 100;
    const dpt = o.core / 42;
    const kBp = o.bypass <= 0 ? null : P.k_bypass + kRestrictor(o.bypass);
    const kH = o.heater ? P.k_heater : null;
    const statFull = o.statOpen + 8, tau = 15;
    const oc = o.ocPct > 0 ? o.ocMount : 'none';
    const ocFrac = o.ocPct / 100;
    const { th, vs, rs } = lapProfile(o, dt);
    const nlap = th.length;
    const nUp = 6, nRad = 12, nLow = 6, nBp = 3;
    const T0 = o.tStart;
    const up = new Float64Array(nUp).fill(T0), rad = new Float64Array(nRad).fill(T0),
      low = new Float64Array(nLow).fill(T0), bp = new Float64Array(nBp).fill(T0);
    let Teng = T0, Tmix = T0, Tmetal = T0 + 3, Tsense = T0, Toil = T0;
    const adv = (cells, Tin, mdot, V) => {
      if (mdot <= 0) return;
      const a = mdot * CP * dt / (V / 1000 / cells.length * RHO * CP);
      for (let k = cells.length - 1; k > 0; k--) cells[k] += a * (cells[k - 1] - cells[k]);
      cells[0] += a * (Tin - cells[0]);
    };
    const epsX = (NTU, Cr) => Cr < 1e-6 ? 1 - Math.exp(-NTU)
      : 1 - Math.exp((NTU ** 0.22 / Cr) * (Math.exp(-Cr * NTU ** 0.78) - 1));
    const log = { t: [], ect: [], oil: [], metal: [], radIn: [], radOut: [], mix: [], lift: [],
      Qr: [], Qb: [], Qh: [], qIn: [], qRad: [], qOc: [], v: [], tPre: [] };
    let qRad = 0, qOc = 0, Tpre = o.tAir;
    // bypass disc: curtain pi*28mm*gap, gap = 10 mm*(1 - lift) + 0.3 mm leak when seated
    const kDisc = x => (o.stat && o.statDisc) ? kOrif(0.6 * Math.PI * 0.028 * (0.010 * (1 - x) + 0.0003)) : 0;
    const net = (s, kR, kB = kBp) => {   // flow network at pump speed s (=rpm/6000); kR radiator path, kB bypass path
      const sr = 1 / Math.sqrt(kR), sb = kB ? 1 / Math.sqrt(kB) : 0, sh = kH ? 1 / Math.sqrt(kH) : 0;
      const sum = sr + sb + sh, Q = s * Math.sqrt(P.p0 / (P.c_pump + P.k_eng + 1 / sum ** 2));
      return { Q, Qr: Q * sr / sum, Qb: Q * sb / sum, Qh: Q * sh / sum };
    };
    const kStatFull = kOrif(P.cdA_jig + P.cdA_full), kRestr = o.bypass > 0 ? kRestrictor(o.bypass) : 0;
    const iWin = Math.max(0, steps - Math.round(Math.min(300, o.minutes * 15) / dt));
    const H = { n: 0, s: 0, pump: 0, eng: 0, core: 0, hose: 0, stat: 0, bp: 0, restr: 0, disc: 0, heater: 0, Q: 0, Qr: 0, Qb: 0, lift: 0 };
    const xMax = o.statLift / 100;
    for (let i = 0; i < steps; i++) {
      const j = i % nlap, thr = th[j], v = vs[j], rpm = rs[j];
      const s = rpm * o.pulley / 6000;
      let x = 1, kR = P.k_rad_fixed;
      if (o.stat) {
        x = Math.min(xMax, Math.max(0, (Tsense - o.statOpen) / (statFull - o.statOpen)));
        kR += kOrif(P.cdA_jig + x * P.cdA_full);
      }
      const kd = kDisc(x), kB = kBp ? kBp + kd : null;
      const { Q, Qr, Qb, Qh } = net(s, kR, kB);
      if (i >= iWin) {   // pressure-drop bookkeeping over the last 5 min (kPa)
        H.n++; H.s += s; H.Q += Q; H.Qr += Qr; H.Qb += Qb; H.lift += x;
        H.pump += P.p0 * s * s - P.c_pump * Q * Q; H.eng += P.k_eng * Q * Q;
        H.core += 2.4 * Qr * Qr; H.hose += (P.k_rad_fixed - 2.4) * Qr * Qr; H.stat += (kR - P.k_rad_fixed) * Qr * Qr;
        H.bp += P.k_bypass * Qb * Qb; H.restr += kRestr * Qb * Qb; H.disc += kd * Qb * Qb; H.heater += kH ? kH * Qh * Qh : 0;
      }
      const mr = Qr * RHO / 1000, mb = Qb * RHO / 1000, mh = Qh * RHO / 1000, m = Q * RHO / 1000;

      const qIn = thr ? o.fc * torqueWot(rpm) * (o.hp / 290) * rpm * 2 * Math.PI / 60 : P.q_off;
      const hAj = Math.max(P.hA_j_min, P.hA_j * (Q / P.Qj) ** 0.8) * hMul;
      const qmc = hAj * (Tmetal - Teng);
      const qoc_ = P.hA_oil_cool * (Toil - Teng);
      Tmetal += dt * ((1 - o.fOil) * qIn - qmc) / P.m_metal_cp;
      Teng += dt * (qmc + qoc_ + m * CP * (Tmix - Teng)) / (P.V_eng / 1000 * RHO * CP);

      // air side
      const vFace = Math.max(P.fan_min, ductF * v);
      const hAc = Math.max(P.hA_cool_min, P.hA_cool_ref * (Qr / P.Qc_ref) ** 0.8) * dpt * hMul;
      const fr = oc === 'front' ? ocFrac : 0, vb = vFace * P.oc_block;
      qOc = 0; Tpre = o.tAir;
      if (oc !== 'none') {
        const vOc = oc === 'front' ? vb : vFace;
        const Ca = RHO_AIR * P.face * ocFrac * vOc * CP_AIR;
        const xo = o.ocStat ? Math.min(1, Math.max(0.05, (Toil - P.oc_open) / (P.oc_full - P.oc_open))) : 1;
        const Co = xo * P.oc_flow / 60000 * 870 * 2100;
        const vol = (ocFrac / 0.2) * (o.ocThick / 42);
        const hAa = P.hA_air_ref * ocFrac * (vOc / P.v_ref) ** 0.6 * (o.ocThick / 42) ** 0.8;
        const UAo = 1 / (1 / hAa + 1 / (500 * vol * xo ** 0.8));
        const Cmin = Math.min(Ca, Co), Cmax = Math.max(Ca, Co);
        qOc = Math.max(0, epsX(UAo / Cmin, Cmin / Cmax) * Cmin * (Toil - o.tAir));
        if (oc === 'front') Tpre = o.tAir + qOc / Ca;
      }
      Toil += dt * (o.fOil * qIn - qoc_ - qOc) / P.C_oil;
      const streams = [[1 - fr, vFace, o.tAir]];
      if (fr > 0) streams.push([fr, vb, Tpre]);
      const es = streams.map(([af, vv, Ta]) => {
        const hAa = P.hA_air_ref * af * (vv / P.v_ref) ** 0.6 * dpt ** 0.8;
        const UA = 1 / (1 / hAa + 1 / (hAc * af));
        const mac = RHO_AIR * P.face * af * vv / nRad;
        return [1 - Math.exp(-(UA / nRad) / (mac * CP_AIR)), mac, Ta];
      });
      adv(up, Teng, mr, P.V_up);
      adv(rad, up[nUp - 1], mr, P.V_rad);
      const Ccell = P.V_rad / 1000 / nRad * RHO * CP;
      qRad = 0;
      for (let k = 0; k < nRad; k++) {
        let q = 0;
        for (const [e, mac, Ta] of es) q += e * mac * CP_AIR * (rad[k] - Ta);
        rad[k] -= dt * q / Ccell; qRad += q;
      }
      adv(low, rad[nRad - 1], mr, P.V_low);
      if (mb > 0) adv(bp, Teng, mb, P.V_bp);
      const Cmix = P.V_mix / 1000 * RHO * CP;
      Tmix += dt * (mr * CP * (low[nLow - 1] - Tmix) + mb * CP * (bp[nBp - 1] - Tmix) + mh * CP * (Teng - Tmix)
        + P.hA_housing * (Tmetal - Tmix)) / Cmix;
      Tsense += dt * (Tmix - Tsense) / tau;

      if (i % every === 0) {
        const L = log; L.t.push(i * dt / 60); L.ect.push(Teng); L.oil.push(Toil); L.metal.push(Tmetal);
        L.radIn.push(up[nUp - 1]); L.radOut.push(rad[nRad - 1]); L.mix.push(Tmix); L.lift.push(x * 100);
        L.Qr.push(Qr * 60); L.Qb.push(Qb * 60); L.Qh.push(Qh * 60); L.qIn.push(qIn / 1000);
        L.qRad.push(qRad / 1000); L.qOc.push(qOc / 1000); L.v.push(v * 3.6); L.tPre.push(Tpre);
      }
    }
    const n = log.t.length, last = Math.max(1, Math.min(300, Math.floor(n / 4)));
    const avgLast = a => a.slice(n - last).reduce((p, c) => p + c, 0) / last;
    const avgAfter = (a, s0) => { const b = a.slice(Math.min(s0, n - 1)); return b.reduce((p, c) => p + c, 0) / b.length; };
    const boilIdx = log.ect.findIndex(T => T >= T_boil);
    const sum = {
      ectEnd: avgLast(log.ect), ectMax: Math.max(...log.ect), oilEnd: avgLast(log.oil), metalMax: Math.max(...log.metal),
      Qr: avgAfter(log.Qr, 120), Qb: avgAfter(log.Qb, 120), Qh: avgAfter(log.Qh, 120),
      qIn: log.qIn.reduce((p, c) => p + c, 0) / n, qRad: avgLast(log.qRad), qOc: avgLast(log.qOc), tPre: avgLast(log.tPre),
      vAvg: log.v.reduce((p, c) => p + c, 0) / n, vMax: Math.max(...log.v),
      tBoil: boilIdx >= 0 ? log.t[boilIdx] : null, T_boil, ductF,
    };
    // hydraulics summary, last 5 min averages; plus what a fully open thermostat costs at the same pump speed
    const m_ = k => H[k] / H.n, sBar = m_('s');
    const xBar = m_('lift');
    const withStat = net(sBar, P.k_rad_fixed + kOrif(P.cdA_jig + xMax * P.cdA_full), kBp ? kBp + kDisc(xMax) : null),
      noStat = net(sBar, P.k_rad_fixed, kBp);
    sum.hyd = { pump: m_('pump'), eng: m_('eng'), core: m_('core'), hose: m_('hose'), stat: m_('stat'), bp: m_('bp'),
      restr: m_('restr'), disc: m_('disc'), Qb: m_('Qb') * 60, heater: m_('heater'), Q: m_('Q') * 60, Qr: m_('Qr') * 60, lift: m_('lift') * 100, rpm: sBar * 6000 / o.pulley,
      statOpen: { k: kStatFull, kRadPath: P.k_rad_fixed + kStatFull, share: kStatFull / (P.k_rad_fixed + kStatFull),
        dp: kStatFull * withStat.Qr ** 2, QrWith: withStat.Qr * 60, QrWithout: noStat.Qr * 60 } };
    return { opts: o, log, sum };
  }
  root.UZSim = { run, DEFAULTS, kRestrictor };
  if (typeof module !== 'undefined') module.exports = root.UZSim;
})(typeof window !== 'undefined' ? window : globalThis);
