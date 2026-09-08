import re
html = open('/home/z/my-project/download/plenka-optimized-37.html', encoding='utf-8').read()
m = re.findall(r'<script>(.*?)</script>', html, re.S)
print('script blocks:', len(m))
for i, js in enumerate(m):
    open('/tmp/plenka37_%d.js' % i, 'w', encoding='utf-8').write(js)
    print('block %d chars: %d' % (i, len(js)))
