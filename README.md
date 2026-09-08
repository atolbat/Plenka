# ПЛЁНКА

Офлайн видео/аудио плеер: single-file HTML-приложение + Android WebView-оболочка
(Kotlin, ноль зависимостей).

## Структура

| Путь | Что это |
|------|---------|
| `download/` | Версии HTML-страницы v32–v40 и v51–v59 + `README.md` (история изменений, актуальная сборка) |
| `upload/plenka-optimized-31.html` | Исходная версия страницы v31 |
| `scripts/` | Сборка страницы (`build*.py`), патчи натива (`patch*.py`), мок-серверы (`mock*.py`), тесты (`check*.js`, `seek*.js`, `repro*.js`), окружение (`setup_*.sh`); `from_chat_*` — восстановленные v49/v50 и стенды v51 |
| `plenka-native/` | Android-проект: `MainActivity` (HTTP-мост к медиатеке), `PlenkaService` (фоновое воспроизведение mediaPlayback), `PlenkaWebView` (обход паузы при сворачивании); ассеты `plenka.html` (v59), `plenka-seek.html`, `plenka-lab.html` |

## Актуальная версия

Страница **v59**, оболочка **3.13** (versionCode 142). Подробности — `download/README.md`.

## Сборка APK

```bash
cd plenka-native && gradle assembleRelease   # Android SDK 34, Gradle 8.7
```

Для подписи релиза положите `plenka.keystore` в `plenka-native/`
(в репозиторий не входит — приватный ключ; путь и пароли заданы в
`app/build.gradle.kts`).

Видео, APK, артефакты сборки и секреты в репозиторий не входят (`.gitignore`).
