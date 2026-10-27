#!/usr/bin/env python3
"""Panel for uz-cooling-1d.py results.
Usage: uz-cooling-viz.py results/uz-cooling CASE out.png
Uses CASE_fc0.75_d0.25.json as nominal; every other CASE_fc*_d*.json forms the uncertainty band."""
import glob, json, os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

d, case, out = sys.argv[1:4]
runs = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(d, f'{case}_fc*_d*.json')))]
nom = next(r for r in runs if r['fc'] == 0.75 and r['duct'] == 0.25)
L = nom['log']; t = np.array([r['t'] for r in L]) / 60
g = lambda k, log=L: np.array([r[k] for r in log])

fig, ax = plt.subplots(3, 1, figsize=(10, 11), sharex=True)
band = np.array([g('T_ect', r['log']) for r in runs])
ax[0].fill_between(t, band.min(0), band.max(0), color='tab:red', alpha=0.12,
                   label='ECT band: heat frac 0.65-0.85 × duct 0.20-0.30')
ax[0].plot(t, g('T_ect'), 'tab:red', lw=2, label='ECT (engine outlet, sensor)')
ax[0].plot(t, g('T_metal'), 'tab:brown', lw=1, ls='--', label='metal (head hot-side proxy)')
ax[0].plot(t, g('T_rad_in'), 'tab:orange', lw=1, label='radiator in')
ax[0].plot(t, g('T_rad_out'), 'tab:blue', lw=1, label='radiator out')
ax[0].plot(t, g('T_mix'), 'tab:purple', lw=1, label='pump inlet (stat pellet)')
ax[0].axhline(128, color='k', ls=':', lw=1); ax[0].text(0.2, 129, 'boil 50/50 @1.1 bar', fontsize=8)
ax[0].axhspan(82, 90, color='green', alpha=0.08); ax[0].text(0.2, 83, 'stat 82-90', fontsize=8, color='green')
ax[0].set_ylabel('°C'); ax[0].legend(fontsize=8, loc='lower right'); ax[0].grid(alpha=.3)
ax[0].set_ylim(60, max(140, band.max() + 5))

ax[1].plot(t, g('Q'), 'k', lw=1, label='pump total')
ax[1].plot(t, g('Qr'), 'tab:blue', lw=1.5, label='through radiator')
ax[1].plot(t, g('Qb'), 'tab:orange', lw=1.5, label='through bypass')
ax[1].set_ylabel('L/min'); ax[1].grid(alpha=.3); ax[1].legend(fontsize=8, loc='upper left')
a2 = ax[1].twinx(); a2.plot(t, g('lift') * 100, 'g', lw=1, alpha=.6); a2.set_ylabel('stat lift %', color='g'); a2.set_ylim(0, 110)

n = 100  # 1 lap moving average (1 s samples)
ma = lambda x: np.convolve(x, np.ones(n) / n, mode='same')
ax[2].plot(t, g('q_in'), color='tab:red', lw=.4, alpha=.4)
ax[2].plot(t, ma(g('q_in')), 'tab:red', lw=2, label='heat into coolant (lap avg)')
ax[2].plot(t, ma(g('q_rad')), 'tab:blue', lw=2, label='radiator rejection (lap avg)')
ax[2].set_ylabel('kW'); ax[2].set_xlabel('session time [min]'); ax[2].grid(alpha=.3); ax[2].legend(fontsize=8)

s = nom['summary']
fig.suptitle(f"3UZ-FE NA Miata — case '{case}' — 30°C, 65% WOT, start 70°C\n"
             f"ECT end {s['T_ect_last5min']:.0f}°C (band {band[:, -300:].mean(1).min():.0f}-{band[:, -300:].mean(1).max():.0f}) | "
             f"radiator {s['Qr_mean']:.0f} L/min, bypass {s['Qb_mean']:.0f} L/min "
             f"({100 * s['Qb_mean'] / (s['Qr_mean'] + s['Qb_mean']):.0f}% skips rad)", fontsize=11)
fig.tight_layout(); fig.savefig(out, dpi=110)
print('saved', out)
