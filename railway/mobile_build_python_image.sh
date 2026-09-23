#!/usr/bin/env bash
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "== InovaPro Android builder bootstrap =="

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates curl unzip zip git xz-utils \
  openjdk-17-jdk-headless build-essential
rm -rf /var/lib/apt/lists/*

if ! command -v node >/dev/null 2>&1 || [ "$(node -p 'Number(process.versions.node.split(\".\")[0])' 2>/dev/null || echo 0)" -lt 22 ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get update
  apt-get install -y nodejs
  rm -rf /var/lib/apt/lists/*
fi

npm install --global yarn@1.22.22

export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export ANDROID_HOME=/opt/android-sdk
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"

if ! command -v sdkmanager >/dev/null 2>&1; then
  mkdir -p "$ANDROID_HOME/cmdline-tools"
  curl -fsSL https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -o /tmp/cmdline-tools.zip
  unzip -q /tmp/cmdline-tools.zip -d "$ANDROID_HOME/cmdline-tools"
  mv "$ANDROID_HOME/cmdline-tools/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest"
fi

yes | sdkmanager --licenses >/dev/null || true
sdkmanager \
  "platform-tools" \
  "platforms;android-36" \
  "build-tools;36.0.0" \
  "ndk;27.1.12297006" \
  "cmake;3.22.1"

WORK=/tmp/inovapro-mobile-build
APK_DIR=/tmp/inovapro-apk
rm -rf "$WORK" "$APK_DIR"
mkdir -p "$WORK/src" "$APK_DIR"

echo "== Downloading InovaPro source bundle =="
curl -fsSL https://raw.githubusercontent.com/renatometalrenato-netizen/InovaPro-AIStudio/main/mobile_bundle.b64 \
  | base64 -d > "$WORK/inovapro-mobile.zip"
unzip -q "$WORK/inovapro-mobile.zip" -d "$WORK/src"

FRONTEND="$WORK/src/inovapro/frontend"
test -f "$FRONTEND/package.json"
cd "$FRONTEND"

export CI=1
export EXPO_PUBLIC_BACKEND_URL=https://inovapro-api-runtime-production.up.railway.app

echo "== Installing JS dependencies =="
yarn install --frozen-lockfile --ignore-engines

echo "== Running unit tests =="
yarn test:unit

echo "== Expo prebuild =="
npx expo prebuild --platform android --clean

echo "== Android debug APK build =="
cd "$FRONTEND/android"
chmod +x gradlew
./gradlew assembleDebug --no-daemon --stacktrace

APK="$FRONTEND/android/app/build/outputs/apk/debug/app-debug.apk"
test -s "$APK"
cp "$APK" "$APK_DIR/InovaPro-debug.apk"
sha256sum "$APK_DIR/InovaPro-debug.apk"
ls -lh "$APK_DIR/InovaPro-debug.apk"

echo "== APK build complete, starting download server =="
cd "$APK_DIR"
exec python - <<'PY'
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

apk = os.path.join(os.getcwd(), "InovaPro-debug.apk")
port = int(os.environ.get("PORT", "8080"))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({
                "status": "ok",
                "apk": os.path.exists(apk),
                "size": os.path.getsize(apk) if os.path.exists(apk) else 0,
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path in ("/", "/InovaPro-debug.apk"):
            if not os.path.exists(apk):
                self.send_error(503, "APK not ready")
                return
            size = os.path.getsize(apk)
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.android.package-archive")
            self.send_header("Content-Length", str(size))
            self.send_header("Content-Disposition", 'attachment; filename="InovaPro-debug.apk"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            with open(apk, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    self.wfile.write(chunk)
            return

        self.send_error(404)

    def log_message(self, fmt, *args):
        print("HTTP", fmt % args, flush=True)

print(f"APK server listening on 0.0.0.0:{port}", flush=True)
ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
PY
