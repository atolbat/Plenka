#!/usr/bin/env python3
"""Extract inline <script> blocks from an HTML file and node --check each."""
import re, subprocess, sys, os

def check(path):
    src = open(path, encoding='utf-8').read()
    scripts = re.findall(r'<script\b[^>]*>(.*?)</script>', src, re.S | re.I)
    ok = True
    for i, s in enumerate(scripts):
        if not s.strip():
            continue
        p = '/home/z/my-project/scripts/_chunk%d.js' % i
        with open(p, 'w', encoding='utf-8') as f:
            f.write(s)
        r = subprocess.run(['node', '--check', p], capture_output=True, text=True)
        status = 'OK' if r.returncode == 0 else 'FAIL'
        print('%s script #%d (%d chars): %s' % (os.path.basename(path), i, len(s), status))
        if r.returncode:
            print(r.stderr[:3000])
            ok = False
    return ok

a = check('/home/z/my-project/upload/plenka-optimized-31.html')
b = check('/home/z/my-project/download/plenka-optimized-32.html')
c = check('/home/z/my-project/download/plenka-optimized-33.html')
d = check('/home/z/my-project/download/plenka-optimized-34.html')
print('ORIGINAL:', 'PASS' if a else 'FAIL')
print('V32     :', 'PASS' if b else 'FAIL')
print('V33     :', 'PASS' if c else 'FAIL')
print('V34     :', 'PASS' if d else 'FAIL')
sys.exit(0 if (a and b and c and d) else 1)
