#!/bin/sh
# Inline sim.js into app.html -> index.html (single-file artifact)
cd "$(dirname "$0")" && python3 -c "
s=open('app.html').read(); j=open('sim.js').read()
assert '</script' not in j
open('index.html','w').write(s.replace('/*SIM*/', j))
" && echo built index.html
