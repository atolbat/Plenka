import re
html = open('/home/z/my-project/download/plenka-optimized-36.html', encoding='utf-8').read()
m = re.findall(r'<script>(.*?)</script>', html, re.S)
print('script blocks:', len(m))
js = m[0] if m else ''
open('/tmp/plenka36.js', 'w', encoding='utf-8').write(js)
print('chars:', len(js))
