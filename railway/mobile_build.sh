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

echo "== Applying InovaPro Mobile v3 social-login overlay =="
FRONTEND="$FRONTEND" python3 - <<'PY'
import base64
import json
import os
import pathlib
import urllib.parse
import urllib.request

repo = "renatometalrenato-netizen/InovaPro-AIStudio"
ref = "deploy/mobile-v3-social-auth"
frontend = pathlib.Path(os.environ["FRONTEND"])
files = {
    "railway/mobile_overlay/frontend/src/auth-context.tsx": "src/auth-context.tsx",
    "railway/mobile_overlay/frontend/app/(auth)/login.tsx": "app/(auth)/login.tsx",
    "railway/mobile_overlay/frontend/app/oauth/callback.tsx": "app/oauth/callback.tsx",
}
for remote, local in files.items():
    url = (
        "https://api.github.com/repos/" + repo + "/contents/" +
        urllib.parse.quote(remote, safe="/") +
        "?ref=" + urllib.parse.quote(ref, safe="")
    )
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "InovaPro-APK-Builder"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    data = base64.b64decode(payload["content"])
    target = frontend / local
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    print("v3 mobile overlay:", local, flush=True)

diag = frontend / "app/diagnostico360.tsx"
text = diag.read_text(encoding="utf-8")
text = text.replace(
    "  answer_options: AnswerOption[];\n};",
    "  answer_options: AnswerOption[];\n  connected_sources?: Array<{ provider: string; display_name?: string | null; connected: boolean }>;\n  note?: string;\n};",
)
text = text.replace(
    'queryFn: () => api<DiagnosticDefinition>("/diagnostics/360/questions"),',
    'queryFn: () => api<DiagnosticDefinition>("/diagnostics/360/smart/questions"),',
)
text = text.replace(
    'mutationFn: () => api<DiagnosticResult>("/diagnostics/360/submit", { method: "POST", body: { answers } }),',
    'mutationFn: () => api<DiagnosticResult>("/diagnostics/360/smart/submit", { method: "POST", body: { answers } }),',
)
text = text.replace(
    "São 21 perguntas objetivas divididas em 7 pilares. A pontuação é calculada por regras fixas — sem IA inventando nota.",
    "A InovaPro usa os dados que você conectou como contexto e pergunta apenas 7 pontos internos que Google e Instagram não conseguem enxergar com segurança. A pontuação continua sendo calculada por regras fixas — sem IA inventando nota.",
)
text = text.replace('<InfoBox value="21" label="perguntas" />', '<InfoBox value="7" label="perguntas essenciais" />')
text = text.replace('<InfoBox value="~5 min" label="para concluir" />', '<InfoBox value="~2 min" label="para concluir" />')
diag.write_text(text, encoding="utf-8")
print("v3 smart diagnostic endpoints patched", flush=True)

api_file = frontend / "src/api.ts"
api_text = api_file.read_text(encoding="utf-8")
api_text = api_text.replace(
    "  onActionPending?: (action: NovaPendingAction) => void;\n",
    "  onActionPending?: (action: NovaPendingAction) => void;\n  onHandoff?: (handoff: { id: string; message: string }) => void;\n",
)
api_text = api_text.replace(
    '        else if (event.type === "action_pending") handlers.onActionPending?.(event.action);\n',
    '        else if (event.type === "action_pending") handlers.onActionPending?.(event.action);\n        else if (event.type === "handoff_ready") handlers.onHandoff?.(event.handoff);\n',
)
api_file.write_text(api_text, encoding="utf-8")
print("v3 Nova handoff contract patched", flush=True)
PY

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
