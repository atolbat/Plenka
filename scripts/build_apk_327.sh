#!/bin/bash
# Локальная сборка PLENKA-native-3.27-local.apk (v74) в песочнице:
# build-tools 34 + platform-34 + kotlinc 2.0.21 из /home/z/plenka-sdk.
# Подпись — СВЕЖИМ локальным ключом plenka-local.keystore (релизный ключ
# пользователя здесь недоступен). Итог: /home/z/my-project/download/PLENKA-native-3.27-local.apk
set -e
SDK=/home/z/plenka-sdk
BT="$SDK/android-14"                       # build-tools 34 (распаковка r34 = android-14)
AJ="$SDK/android-34/android.jar"
KC="$SDK/kotlinc/bin/kotlinc"
PRJ=/home/z/my-project/repos/atolbat_Plenka/plenka-native
W=/home/z/plenka-sdk/apkbuild
OUT=/home/z/my-project/download/PLENKA-native-3.27-local.apk
KS="$SDK/plenka-local.keystore"

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
  --version-code 156 --version-name 3.27 \
  --auto-add-overlay "$W/res.zip"

echo ">> 3/6 kotlinc: исходники (stdlib внутри jar)"
"$KC" "$PRJ"/app/src/main/java/ru/plenka/app/*.kt -classpath "$AJ" -include-runtime -d "$W/app.jar" 2>&1 | grep -v "^warning:" | tail -5 || true
ls -la "$W/app.jar"

echo ">> 4/6 d8: dex"
"$BT/d8" --release --lib "$AJ" --min-api 26 "$W/app.jar" --output "$W/dex"

echo ">> 5/6 classes.dex → apk"
(cd "$W/dex" && zip -q -j "$W/base.apk" classes.dex)

if [ ! -f "$KS" ]; then
  echo ">> генерация локального keystore"
  keytool -genkeypair -keystore "$KS" -alias plenka -keyalg RSA -keysize 2048 \
    -validity 10000 -storepass plenka-local-2026 -keypass plenka-local-2026 \
    -dname "CN=Plenka Local Build,O=Plenka,C=RU" >/dev/null 2>&1
fi

echo ">> 6/6 zipalign + apksigner"
"$BT/zipalign" -f -p 4 "$W/base.apk" "$W/aligned.apk"
"$BT/apksigner" sign --ks "$KS" --ks-pass pass:plenka-local-2026 \
  --ks-key-alias plenka --key-pass pass:plenka-local-2026 \
  --out "$OUT" "$W/aligned.apk"
"$BT/apksigner" verify --print-certs "$OUT" | head -6
echo ">> ГОТОВО: $OUT ($(stat -c%s "$OUT") байт)"
