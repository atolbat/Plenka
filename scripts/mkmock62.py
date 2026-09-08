#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mock61.py → mock62.py: HTML v62, мост-мок 3.15 (v62)."""
src = open('/home/z/my-project/scripts/mock61.py', encoding='utf-8').read()
src = src.replace("plenka-optimized-61.html", "plenka-optimized-62.html")
src = src.replace("PLENKA native 3.13 (v61, MOCK)", "PLENKA native 3.15 (v62, MOCK)")
src = src.replace("Мок сервера ПЛЁНКА 3.13 (v61): / → v61", "Мок сервера ПЛЁНКА 3.15 (v62): / → v62")
src = src.replace("mock 3.13 on http://127.0.0.1:%d/ (v61)", "mock 3.15 on http://127.0.0.1:%d/ (v62)")
open('/home/z/my-project/scripts/mock62.py', 'w', encoding='utf-8').write(src)
print('mock62.py готов')
