#!/bin/bash
# Установка Android SDK для сборки APK (PLENKA native)
set -e
SDK=/home/z/android-sdk
mkdir -p "$SDK/cmdline-tools"
cd /home/z/my-project/scripts

if [ ! -d "$SDK/cmdline-tools/latest" ]; then
  echo ">> скачиваю cmdline-tools..."
  curl -sS -o cmdtools.zip https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
  unzip -q cmdtools.zip -d "$SDK/cmdline-tools"
  mv "$SDK/cmdline-tools/cmdline-tools" "$SDK/cmdline-tools/latest"
fi

export ANDROID_HOME=$SDK
SDKM="$SDK/cmdline-tools/latest/bin/sdkmanager"

echo ">> принимаю лицензии..."
yes | "$SDKM" --licenses > /dev/null 2>&1 || true

echo ">> ставлю platform-tools, android-34, build-tools 34.0.0..."
yes | "$SDKM" "platform-tools" "platforms;android-34" "build-tools;34.0.0" > /dev/null

echo ">> ГОТОВО. Содержимое SDK:"
ls "$SDK"
ls "$SDK/build-tools" 2>/dev/null
echo OK_DONE
