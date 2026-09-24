#!/usr/bin/env bash
set -euo pipefail

RAW_BASE="https://raw.githubusercontent.com/renatometalrenato-netizen/InovaPro-AIStudio/main"
WORK="/tmp/inovapro-mobile-build"
APK_DIR="/tmp/inovapro-apk"

echo "== InovaPro Android builder =="
node --version
npm --version
java -version
command -v sdkmanager || true

rm -rf "$WORK" "$APK_DIR"
mkdir -p "$WORK" "$APK_DIR"

curl -fsSL "$RAW_BASE/mobile_bundle.b64" | base64 -d > "$WORK/inovapro-mobile.zip"
unzip -q "$WORK/inovapro-mobile.zip" -d "$WORK/src"

FRONTEND="$WORK/src/inovapro/frontend"
test -f "$FRONTEND/package.json"

echo "== Applying InovaPro Mobile v2 patch =="
curl -fsSL "https://raw.githubusercontent.com/renatometalrenato-netizen/InovaPro-AIStudio/deploy/mobile-v2-backend/railway/mobile_v2_patch.b64" | base64 -d > "$WORK/mobile-v2-patch.zip"
unzip -oq "$WORK/mobile-v2-patch.zip" -d "$FRONTEND"
test -f "$FRONTEND/app/diagnostico360.tsx"

cd "$FRONTEND"

export CI=1
export EXPO_PUBLIC_BACKEND_URL="https://inovapro-api-runtime-production.up.railway.app"

if ! command -v yarn >/dev/null 2>&1; then
  npm install --global yarn@1.22.22
fi

echo "== Installing dependencies =="
yarn install --frozen-lockfile --ignore-engines

echo "== Running unit tests =="
yarn test:unit

echo "== Generating Android project =="
npx expo prebuild --platform android --clean

echo "== Building debug APK =="
cd "$FRONTEND/android"
chmod +x gradlew
./gradlew assembleDebug --no-daemon --stacktrace

APK="$FRONTEND/android/app/build/outputs/apk/debug/app-debug.apk"
test -s "$APK"
cp "$APK" "$APK_DIR/InovaPro-debug.apk"
ls -lh "$APK_DIR/InovaPro-debug.apk"

cd "$APK_DIR"
export APK_PORT="${PORT:-8080}"
echo "== APK ready on port $APK_PORT =="
exec node - <<'NODE'
const http = require('http');
const fs = require('fs');
const path = require('path');

const port = Number(process.env.APK_PORT || process.env.PORT || 8080);
const file = path.join(process.cwd(), 'InovaPro-debug.apk');

http.createServer((req, res) => {
  if (req.url === '/health') {
    res.writeHead(200, {'Content-Type':'application/json'});
    return res.end(JSON.stringify({status:'ok', apk:fs.existsSync(file)}));
  }
  if (req.url === '/' || req.url === '/InovaPro-debug.apk') {
    if (!fs.existsSync(file)) {
      res.writeHead(503, {'Content-Type':'text/plain'});
      return res.end('APK not ready');
    }
    const st = fs.statSync(file);
    res.writeHead(200, {
      'Content-Type':'application/vnd.android.package-archive',
      'Content-Length': st.size,
      'Content-Disposition':'attachment; filename="InovaPro-debug.apk"',
      'Cache-Control':'no-store'
    });
    return fs.createReadStream(file).pipe(res);
  }
  res.writeHead(404, {'Content-Type':'text/plain'});
  res.end('Not found');
}).listen(port, '0.0.0.0', () => {
  console.log('APK server listening on', port);
});
NODE
