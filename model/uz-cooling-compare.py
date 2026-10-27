#!/usr/bin/env python3
"""Comparison panel for uz-cooling-1d.py runs.
Usage: uz-cooling-compare.py results/uz-cooling out.png"""
import glob, json, os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

d, out = sys.argv[1:3]
CASES = ['stock', 'r18', 'r14', 'r10', 'blocked', 'blockedNH', 'delete']
LABEL = dict(stock='no restrictor', r18='18 mm', r14='14 mm', r10='10 mm',
             blocked='blocked + stat', blockedNH='blocked + stat,\nheater deleted', delete='delete (no stat, blocked)')
COL = dict(stock='k', r18='tab:blue', r14='tab:green', r10='tab:olive', blocked='tab:orange', blockedNH='tab:red', delete='tab:purple')
BOIL = 128.0
load = lambda f: json.load(open(f))

fig = plt.figure(figsize=(12, 12))
gs = fig.add_gridspec(3, 2, height_ratios=[1.2, 1, 1])
a0 = fig.add_subplot(gs[0, :]); a1 = fig.add_subplot(gs[1, 0]); a2 = fig.add_subplot(gs[1, 1]); a3 = fig.add_subplot(gs[2, :])

ends, lo, hi, qr, boil = [], [], [], [], []
for c in CASES:
    runs = [load(f) for f in glob.glob(os.path.join(d, f'{c}_fc*_d*.json'))]
    nom = next(r for r in runs if r['fc'] == 0.75 and r['duct'] == 0.25)
    t = np.array([x['t'] for x in nom['log']]) / 60
    T = np.array([x['T_ect'] for x in nom['log']])
    a0.plot(t, np.minimum(T, 160), color=COL[c], lw=2 if c in ('stock', 'r14', 'delete') else 1.2, label=LABEL[c])
    e = [np.mean([x['T_ect'] for x in r['log'][-300:]]) for r in runs]
    ends.append(nom['summary']['T_ect_last5min']); lo.append(min(e)); hi.append(max(e))
    qr.append(nom['summary']['Qr_mean']); boil.append(nom['summary']['t_boil'])
a0.axhline(BOIL, color='k', ls=':', lw=1); a0.text(0.1, BOIL + 1, 'boil 50/50 @ 1.1 bar → above this = boil-over, values not physical', fontsize=8)
a0.axhspan(82, 90, color='green', alpha=0.08)
a0.set_ylim(60, 160); a0.set_xlim(0, 20); a0.set_ylabel('ECT °C'); a0.set_xlabel('session time [min]')
a0.legend(fontsize=9, ncol=3, loc='lower right'); a0.grid(alpha=.3)
a0.set_title('Same session: fast track (avg 141 km/h), 30°C air, 65% WOT, start 70°C, IL 42mm rad, heater loop flowing (heat 0.75, duct 0.25)', fontsize=10)

x = np.arange(len(CASES))
show = [min(e, 160) for e in ends]
a1.bar(x, show, color=[COL[c] for c in CASES], alpha=.75)
a1.errorbar(x, show, yerr=[np.array(show) - np.minimum(lo, 160), np.minimum(hi, 160) - np.array(show)],
            fmt='none', ecolor='gray', capsize=4)
for i, (e, b) in enumerate(zip(ends, boil)):
    a1.text(i, min(e, 160) + 3, 'BOILS\n%.0fs' % b if e > BOIL else f'{e:.0f}', ha='center', fontsize=8,
            color='tab:red' if e > BOIL or b else 'k')
a1.axhline(BOIL, color='k', ls=':', lw=1)
a1.set_xticks(x, [LABEL[c].replace(' (', '\n(') for c in CASES], fontsize=7, rotation=20)
a1.set_ylim(80, 175); a1.set_ylabel('ECT last 5 min °C'); a1.set_title('End temp (bar = band over heat frac × duct)', fontsize=10)
a1.grid(alpha=.3, axis='y')

a2.bar(x, qr, color=[COL[c] for c in CASES], alpha=.75)
for i, q in enumerate(qr):
    a2.text(i, q + 3, f'{q:.0f}', ha='center', fontsize=8)
a2.set_xticks(x, [LABEL[c].replace(' (', '\n(') for c in CASES], fontsize=7, rotation=20)
a2.set_ylabel('L/min'); a2.set_title('Mean flow through radiator', fontsize=10); a2.grid(alpha=.3, axis='y')

# radiator / duct matrix
grp = ['stock', 'r14', 'delete']; cores = [42, 55, 60]; ducts = [0.25, 0.35]
w = 0.13; k = 0
for ci, core in enumerate(cores):
    for di, du in enumerate(ducts):
        vals = []
        for c in grp:
            f = os.path.join(d, f'rad-c{core}', f'{c}_fc0.75_d{du}.json')
            vals.append(load(f)['summary']['T_ect_last5min'])
        pos = np.arange(len(grp)) + (k - 2.5) * w
        bars = a3.bar(pos, vals, w, label=f'{core}mm core, duct {du}', color=plt.cm.viridis(k / 5))
        for p_, v in zip(pos, vals):
            a3.text(p_, v + 1, f'{v:.0f}', ha='center', fontsize=7)
        k += 1
a3.axhline(BOIL, color='k', ls=':', lw=1); a3.axhspan(82, 90, color='green', alpha=0.08)
a3.set_xticks(np.arange(len(grp)), [LABEL[c] for c in grp]); a3.set_ylim(80, 140)
a3.set_ylabel('ECT last 5 min °C'); a3.legend(fontsize=8, ncol=3); a3.grid(alpha=.3, axis='y')
a3.set_title('Radiator thickness + ducting vs restrictor (duct = rad face velocity / car speed)', fontsize=10)

fig.suptitle('3UZ-FE NA Miata — bypass restrictor study (1D loop model)', fontsize=13)
fig.tight_layout(); fig.savefig(out, dpi=110); print('saved', out)
