#!/bin/bash
: "${PLENKA_KS_PASS:?экспортируйте PLENKA_KS_PASS (и опц. PLENKA_KS_ALIAS/PLENKA_KS_PATH) перед сборкой}"
# Сборка PLENKA-native-3.19.apk (v66) командной строкой: aapt2 + kotlinc + d8 + apksigner.
# Пути — из окружения либо относительные от корня репо (3.19: абсолютные пути убраны).
# 3.19: страница v66 (фантомные кадры/гонки: SW-1..4, RC-1..11, KT-2/8/9),
#       оболочка: render-gone, NSC/бэкапы, constant-time токен, fsync-записи, фолбэк порта.
set -e
SDK="${SDK:-/home/z/android-sdk}"
BT="$SDK/build-tools/34.0.0"
AJ="$SDK/platforms/android-34/android.jar"
KC="${KOTLINC:-/home/z/kotlinc/kotlinc/bin/kotlinc}"
PRJ="$(cd "$(dirname "$0")/.." && pwd)/plenka-native"
W="${TMPDIR:-/tmp}/plenka-apkbuild"
OUT="$(cd "$(dirname "$0")/.." && pwd)/download/PLENKA-native-3.19.apk"

rm -rf "$W" && mkdir -p "$W/dex"

echo ">> 1/6 aapt2: ресурсы"
"$BT/aapt2" compile --dir "$PRJ/app/src/main/res" -o "$W/res.zip"

echo ">> 2/6 aapt2: link (manifest+assets+res)"
cp "$PRJ/app/src/main/AndroidManifest.xml" "$W/AndroidManifest.xml"
sed -i 's|<manifest xmlns:android="http://schemas.android.com/apk/res/android">|<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="ru.plenka.app">|' "$W/AndroidManifest.xml"
"$BT/aapt2" link -o "$W/base.apk" -I "$AJ" \
  --manifest "$W/AndroidManifest.xml" \
  -A "$PRJ/app/src/main/assets" \
  --min-sdk-version 26 --target-sdk-version 34 \
  --version-code 148 --version-name 3.19 \
  --auto-add-overlay "$W/res.zip"

echo ">> 3/6 kotlinc: исходники (stdlib внутри jar)"
"$KC" "$PRJ"/app/src/main/java/ru/plenka/app/*.kt -classpath "$AJ" -include-runtime -d "$W/app.jar"

echo ">> 4/6 d8: dex"
"$BT/d8" --release --lib "$AJ" --min-api 26 "$W/app.jar" --output "$W/dex"

echo ">> 5/6 classes.dex → apk"
(cd "$W/dex" && zip -q -j "$W/base.apk" classes.dex)

echo ">> 6/6 zipalign + apksigner"
"$BT/zipalign" -f -p 4 "$W/base.apk" "$W/aligned.apk"
"$BT/apksigner" sign --ks "${PLENKA_KS_PATH:-$PRJ/plenka.keystore}" \
  --ks-pass env:PLENKA_KS_PASS --ks-key-alias "${PLENKA_KS_ALIAS:-plenka}" --key-pass env:PLENKA_KS_PASS \
  --out "$OUT" "$W/aligned.apk"
"$BT/apksigner" verify --print-certs "$OUT" | head -6
echo ">> ГОТОВО: $OUT ($(stat -c%s "$OUT") байт)"
