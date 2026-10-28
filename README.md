# ПЛЁНКА

Офлайн видео/аудио плеер: single-file HTML-приложение + Android WebView-оболочка
(Kotlin, ноль зависимостей).

## Структура

| Путь | Что это |
|------|---------|
| `download/` | Версии HTML-страницы v32–v40 и v51–v65 + `README.md` (история изменений, актуальная сборка) |
| `upload/plenka-optimized-31.html` | Исходная версия страницы v31 |
| `scripts/` | Сборка страницы (`build*.py`), патчи натива (`patch*.py`), мок-серверы (`mock*.py`), тесты (`check*.js`, `seek*.js`, `repro*.js`), окружение (`setup_*.sh`); `from_chat_*` — восстановленные v49/v50 и стенды v51 |
| `plenka-native/` | Android-проект: `MainActivity` (HTTP-мост к медиатеке + inner-класс `PlenkaWebView` — обход паузы при сворачивании), `PlenkaService` (фоновое воспроизведение mediaPlayback); ассеты `plenka.html` (v65), `plenka-seek.html`, `plenka-lab.html` |

## Актуальная версия

Страница **v65**, оболочка **3.18** (versionCode 147). Подробности — `download/README.md`.

**Безопасность (3.18):** локальный мост `127.0.0.1` отвечает данными только с токеном
сессии (`filesDir/srvtoken`, выдаётся странице через `?tok=`) — соседние приложения
медиатеку больше не читают; cleartext разрешён только loopback (network security config);
пароли keystore берутся из окружения `PLENKA_KS_PATH/PLENKA_KS_ALIAS/PLENKA_KS_PASS`
(в git больше не лежат), без env — unsigned-сборка под apksigner.

## Сборка APK

```bash
cd plenka-native && gradle assembleRelease   # Android SDK 34, Gradle 8.7
```

Для подписи релиза положите `plenka.keystore` в `plenka-native/`
(в репозиторий не входит — приватный ключ) и экспортируйте:
`export PLENKA_KS_PASS=…` (опц. `PLENKA_KS_PATH`, `PLENKA_KS_ALIAS`).

Видео, APK, артефакты сборки и секреты в репозиторий не входят (`.gitignore`).
