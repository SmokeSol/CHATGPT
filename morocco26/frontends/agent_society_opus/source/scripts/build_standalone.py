# -*- coding: utf-8 -*-
# Assemble the standalone, request-free version of the page.
#
# The output is pure ASCII: the published page must render identically whether
# or not the host declares a charset, so every non-ASCII character is encoded in
# the form its own layer understands (JSON unicode escapes, JS unicode escapes,
# HTML numeric character references).
import io
import json
import os
import re
import sys

W = r"C:\Users\melafrit\Documents\atlas-agentsociety-maroc\web"
OUT = sys.argv[1]


def esc_js(t):
    return ''.join(c if ord(c) < 128 else '\\u%04x' % ord(c) for c in t)


def esc_html(t):
    return t.encode('ascii', 'xmlcharrefreplace').decode('ascii')


html = io.open(os.path.join(W, 'index.html'), encoding='utf-8').read()
css = io.open(os.path.join(W, 'styles.css'), encoding='utf-8').read()
js = io.open(os.path.join(W, 'app.js'), encoding='utf-8').read()

body = html[html.index('<body>') + len('<body>'):html.index('</body>')]
body = body.replace('<script src="app.js"></script>', '')

css_min = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
assert not re.search(r'[^\x00-\x7f]', css_min), 'CSS carries non-ASCII outside comments'


def payload(name):
    d = json.load(io.open(os.path.join(W, 'data', name), encoding='utf-8'))
    t = json.dumps(d, ensure_ascii=True, separators=(',', ':'))
    return t.replace('<', '\\u003c')


TITLE = esc_html('<title>ATLAS // Soci\u00e9t\u00e9 artificielle</title>\n')

parts = [
    TITLE.replace('&lt;', '<').replace('&gt;', '>'),
    '<style>\n', css_min, '\n</style>\n',
    esc_html(body),
    '\n<script type="application/json" id="d-societe">', payload('societe.json'), '</script>\n',
    '<script type="application/json" id="d-portraits">', payload('portraits.json'), '</script>\n',
    '<script type="application/json" id="d-simulateur">', payload('simulateur.json'), '</script>\n',
    '<script>\n', esc_js(js), '\n</script>\n',
]
out = ''.join(parts)
assert not re.search(r'[^\x00-\x7f]', out), 'output is not pure ASCII'
io.open(OUT, 'w', encoding='ascii', newline='\n').write(out)
print('artifact %.2f MB, pure ASCII' % (os.path.getsize(OUT) / 1e6))
