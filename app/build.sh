#!/bin/sh
# app.html + sim.js -> index.html (full standalone page, Render) and artifact.html (bare body, Claude artifact)
cd "$(dirname "$0")" && python3 -c "
s=open('app.html').read(); j=open('sim.js').read()
assert '</script' not in j
body=s.replace('/*SIM*/', j)
open('artifact.html','w').write(body)
head='''<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">
<meta name=\"description\" content=\"Interactive 1D cooling-loop model for a 3UZ-FE Miata: bypass restrictor, thermostat, radiator, ducting, oil cooler.\">
<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}img{max-width:100%}[hidden]{display:none!important}</style>
'''
i=body.index('<div id=\"app\">')
open('index.html','w').write(head+body[:i]+'</head><body>\n'+body[i:]+'\n</body></html>\n')
" && echo built index.html + artifact.html
