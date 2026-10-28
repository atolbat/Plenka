# ПЛЁНКА

Офлайн видео/аудио плеер: single-file HTML-приложение + Android WebView-оболочка
(Kotlin, ноль зависимостей).

## Структура

| Путь | Что это |
|------|---------|
| `download/` | Версии HTML-страницы v32–v40 и v51–v67 + `README.md` (история изменений, актуальная сборка) |
| `upload/plenka-optimized-31.html` | Исходная версия страницы v31 |
| `scripts/` | Сборка страницы (`build*.py`), патчи натива (`patch*.py`), мок-серверы (`mock*.py`), тесты (`check*.js`, `seek*.js`, `repro*.js`), окружение (`setup_*.sh`); `from_chat_*` — восстановленные v49/v50 и стенды v51 |
| `plenka-native/` | Android-проект: `MainActivity` (HTTP-мост к медиатеке + inner-класс `PlenkaWebView` — обход паузы при сворачивании), `PlenkaService` (фоновое воспроизведение mediaPlayback); ассеты `plenka.html` (v67), `plenka-seek.html`, `plenka-lab.html` |

## Актуальная версия

Страница **v67**, оболочка **3.20** (versionCode 149). Подробности — `download/README.md`.

**«Открыть с помощью» (3.20):** манифест принимает ACTION_VIEW для аудио/видео
(content:// и file://) — «ПЛЁНКА» видна в меню «Открыть с помощью» и может быть
назначена видеоплеером/аудиоплеером по умолчанию (Настройки → Приложения →
ПЛЁНКА → По умолчанию). Внешний файл раздаётся по `/x/<seq>` с Range,
не копируется и в библиотеку не пишется — «открыл → посмотрел».

**Безопасность (3.18):** локальный мост `127.0.0.1` отвечает данными только с токеном
сессии (`filesDir/srvtoken`, выдаётся странице через `?tok=`) — соседние приложения
медиатеку больше не читают; cleartext разрешён только loopback (network security config);
пароли keystore берутся из окружения `PLENKA_KS_PATH/PLENKA_KS_ALIAS/PLENKA_KS_PASS`
(в git больше не лежат), без env — unsigned-сборка под apksigner.

**Безопасность/надёжность (3.19):** литералы пароля удалены и из `scripts/` (история git
содержит старый пароль — ключ рекомендуется ротировать: новый keystore вне репо,
`PLENKA_KS_PASS` в окружении); сравнение токена constant-time, Host-гейт по точному имени;
бэкапы Android отключены (`allowBackup=false` — иначе уходят `srvtoken`, PIN-хеш и история);
каждые regSave/srvtoken — tmp+fsync+rename без удаления оригинала при отказе;
`onRenderProcessGone` пересобирает активити вместо падения всего процесса;
фолбэк порта моста (8977–8986) доведён до страницы — `NATV_BASE` берётся из `location.origin`;
данные стендов `/seek` и `/lab` тоже за токеном (стенды принимают `?tok=`).

## Сборка APK

```bash
cd plenka-native && gradle assembleRelease   # Android SDK 34, Gradle 8.7
```

Для подписи релиза положите `plenka.keystore` в `plenka-native/`
(в репозиторий не входит — приватный ключ) и экспортируйте:
`export PLENKA_KS_PASS=…` (опц. `PLENKA_KS_PATH`, `PLENKA_KS_ALIAS`).

Видео, APK, артефакты сборки и секреты в репозиторий не входят (`.gitignore`).
