#!/bin/bash
# Сборка PLENKA-native-3.17.apk (v64) командной строкой: aapt2 + kotlinc + d8 + apksigner.
# Подпись — восстановленный plenka.keystore (та же подпись, что 2.0–3.16 → ставится поверх).
# v64: убрана кнопка/экран «ДИАГ» (невидимая диагностика в logcat осталась);
#      радио-сегменты настроек/очереди/сабов + пресеты эквалайзера → выпадающие списки.
set -e
SDK=/home/z/android-sdk
BT=$SDK/build-tools/34.0.0
AJ=$SDK/platforms/android-34/android.jar
KC=/home/z/kotlinc/kotlinc/bin/kotlinc
PRJ=/home/z/my-project/plenka-native
W=/home/z/my-project/scripts/apkbuild
OUT=/home/z/my-project/download/PLENKA-native-3.17.apk

rm -rf "$W" && mkdir -p "$W/dex"

echo ">> 1/6 aapt2: ресурсы"
"$BT/aapt2" compile --dir "$PRJ/app/src/main/res" -o "$W/res.zip"

echo ">> 2/6 aapt2: link (manifest+assets+res)"
cp "$PRJ/app/src/main/AndroidManifest.xml" "$W/AndroidManifest.xml"
# aapt2 требует package в манифесте; namespace проекта фиксирован
sed -i 's|<manifest xmlns:android="http://schemas.android.com/apk/res/android">|<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="ru.plenka.app">|' "$W/AndroidManifest.xml"
"$BT/aapt2" link -o "$W/base.apk" -I "$AJ" \
  --manifest "$W/AndroidManifest.xml" \
  -A "$PRJ/app/src/main/assets" \
  --min-sdk-version 26 --target-sdk-version 34 \
  --version-code 146 --version-name 3.17 \
  --auto-add-overlay "$W/res.zip"

echo ">> 3/6 kotlinc: исходники (stdlib внутри jar)"
"$KC" "$PRJ"/app/src/main/java/ru/plenka/app/*.kt -classpath "$AJ" -include-runtime -d "$W/app.jar"

echo ">> 4/6 d8: dex"
"$BT/d8" --release --lib "$AJ" --min-api 26 "$W/app.jar" --output "$W/dex"

echo ">> 5/6 classes.dex → apk"
(cd "$W/dex" && zip -q -j "$W/base.apk" classes.dex)

echo ">> 6/6 zipalign + apksigner"
"$BT/zipalign" -f -p 4 "$W/base.apk" "$W/aligned.apk"
"$BT/apksigner" sign --ks "$PRJ/plenka.keystore" \
  --ks-pass pass:plenka2020 --ks-key-alias plenka --key-pass pass:plenka2020 \
  --out "$OUT" "$W/aligned.apk"
"$BT/apksigner" verify --print-certs "$OUT" | head -6
echo ">> ГОТОВО: $OUT ($(stat -c%s "$OUT") байт)"
