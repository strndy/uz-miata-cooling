#!/usr/bin/env python3
"""Oil-cooler panel. Usage: uz-cooling-oil-viz.py results/uz-cooling/oil/results.txt out.png"""
import json, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
rows = {}
for l in open(sys.argv[1]):
    h = l.split('{')[0].split(); j = json.loads(l[l.index('{'):])
    kv = dict(x.split('=') for x in h[2:]); rows[(h[1], kv['oc'], kv['fc'], kv['duct'], kv['core'])] = j
C = ['stock', 'stock+worn60', 'delete']; CL = ['new thermostat', 'worn thermostat (60%)', 'delete kit']
OC = ['none', 'front', 'side']; OL = ['no oil cooler', 'oil cooler in front of rad (20%)', 'oil cooler own duct']
col = ['0.55', 'tab:orange', 'tab:green']
fig, ax = plt.subplots(2, 2, figsize=(12, 8.5))
for r, (fc, du, co, ttl) in enumerate([('0.75', '0.25', '42.0', 'IL 42mm rad, duct 0.25 (current)'),
                                       ('0.75', '0.35', '60.0', '60mm rad, duct 0.35 (fixed front end)')]):
    for k, key, lab in [(0, 'T_ect_last5min', 'coolant ECT °C'), (1, 'T_oil_last5min', 'oil °C')]:
        a = ax[r, k]
        for i, oc in enumerate(OC):
            vals = [rows[(c, oc, fc, du, co)][key] for c in C]
            pos = np.arange(3) + (i - 1) * 0.27
            a.bar(pos, vals, 0.27, color=col[i], label=OL[i])
            for p_, v in zip(pos, vals):
                a.text(p_, v + 1, f'{v:.0f}', ha='center', fontsize=8)
            if r == 0 and k == 0:
                lo = [rows[(c, oc, '0.65', du, co)][key] for c in C]; hi = [rows[(c, oc, '0.85', du, co)][key] for c in C]
                a.errorbar(pos, vals, yerr=[np.array(vals) - lo, np.array(hi) - vals], fmt='none', ecolor='k', capsize=3, lw=.8)
        a.axhline(128 if k == 0 else 130, color='k', ls=':', lw=1)
        a.text(2.45, (128 if k == 0 else 130) + 1, 'boil' if k == 0 else 'oil ~130 limit', fontsize=7, ha='right')
        a.set_xticks(range(3), CL); a.set_ylim(80, 175); a.set_ylabel(lab); a.grid(alpha=.3, axis='y')
        a.set_title(f'{lab.split()[0]} — {ttl}', fontsize=10)
ax[0, 0].legend(fontsize=8, loc='upper right')
fig.suptitle('3UZ NA Miata — oil cooler effect (30°C, 65% WOT, 20 min; ~13 kW oil cooler, air behind it ~75°C)', fontsize=11)
fig.tight_layout(); fig.savefig(sys.argv[2], dpi=110); print('saved', sys.argv[2])
