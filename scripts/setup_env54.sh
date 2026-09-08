#!/bin/bash
# Восстановление сборочного окружения (SDK + Gradle 8.7) — воркспейс сбрасывался
set -e
SDK=/home/z/android-sdk
GR=/home/z/gradle-8.7

mkdir -p "$SDK/cmdline-tools"
cd /home/z/my-project/scripts

if [ ! -d "$SDK/cmdline-tools/latest" ]; then
  echo ">> распаковываю cmdline-tools из локального cmdtools.zip..."
  unzip -q cmdtools.zip -d "$SDK/cmdline-tools"
  mv "$SDK/cmdline-tools/cmdline-tools" "$SDK/cmdline-tools/latest"
fi

export ANDROID_HOME=$SDK
SDKM="$SDK/cmdline-tools/latest/bin/sdkmanager"

echo ">> принимаю лицензии..."
yes | "$SDKM" --licenses > /dev/null 2>&1 || true

echo ">> ставлю platform-tools, android-34, build-tools 34.0.0..."
yes | "$SDKM" "platform-tools" "platforms;android-34" "build-tools;34.0.0" > /dev/null

if [ ! -x "$GR/bin/gradle" ]; then
  echo ">> скачиваю Gradle 8.7..."
  curl -sS -L -o /home/z/gradle-8.7-bin.zip https://services.gradle.org/distributions/gradle-8.7-bin.zip
  unzip -q /home/z/gradle-8.7-bin.zip -d /home/z/
fi

echo ">> ГОТОВО:"
ls "$SDK" | tr '\n' ' '; echo
"$GR/bin/gradle" --version | head -4
echo OK_DONE
