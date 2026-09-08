import re
html = open('/home/z/my-project/download/plenka-optimized-35.html', encoding='utf-8').read()
m = re.findall(r'<script>(.*?)</script>', html, re.S)
print('script blocks:', len(m))
open('/tmp/plenka35.js','w',encoding='utf-8').write(m[0] if m else '')
