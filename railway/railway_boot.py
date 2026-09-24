import base64
import io
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile

print("BOOT_V3_SOCIAL_AUTH", flush=True)

TARGET = "/tmp/inovapro"
REPO = "renatometalrenato-netizen/InovaPro-AIStudio"
V3_REF = "deploy/mobile-v3-social-auth"

def github_text(path: str, ref: str) -> str:
    encoded_path = urllib.parse.quote(path, safe="/")
    encoded_ref = urllib.parse.quote(ref, safe="")
    url = f"https://api.github.com/repos/{REPO}/contents/{encoded_path}?ref={encoded_ref}"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "InovaPro-Railway"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return base64.b64decode(payload["content"]).decode("utf-8")

bundle_text = github_text("railway/backend_bundle.b64", "main")
raw = base64.b64decode(bundle_text)
os.makedirs(TARGET, exist_ok=True)
with zipfile.ZipFile(io.BytesIO(raw)) as archive:
    archive.extractall(TARGET)

try:
    provider_code = github_text("railway/text_provider_gemini.py", "deploy/mobile-v2-backend")
    provider_path = os.path.join(TARGET, "app", "providers", "text.py")
    os.makedirs(os.path.dirname(provider_path), exist_ok=True)
    with open(provider_path, "w", encoding="utf-8") as fh:
        fh.write(provider_code)
    print("Gemini provider override loaded", flush=True)
except Exception as exc:
    print(f"Provider override unavailable: {exc}", file=sys.stderr)

overlay = {
    "railway/overlay/server.py": "server.py",
    "railway/overlay/requirements-runtime.txt": "requirements-runtime.txt",
    "railway/overlay/app/diagnostic_engine.py": "app/diagnostic_engine.py",
    "railway/overlay/app/routers/__init__.py": "app/routers/__init__.py",
    "railway/overlay/app/routers/diagnostics_router.py": "app/routers/diagnostics_router.py",
    "railway/overlay/app/routers/social_auth_router.py": "app/routers/social_auth_router.py",
    "railway/overlay/app/routers/nova_router.py": "app/routers/nova_router.py",
}

for remote, local in overlay.items():
    data = github_text(remote, V3_REF)
    target = os.path.join(TARGET, local)
    os.makedirs(os.path.dirname(target) or TARGET, exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(data)
    print(f"V3 overlay loaded: {local}", flush=True)

subprocess.check_call([
    sys.executable,
    "-m",
    "pip",
    "install",
    "--no-cache-dir",
    "-r",
    os.path.join(TARGET, "requirements-runtime.txt"),
])

port = os.environ.get("PORT", "8000")
os.chdir(TARGET)
os.execvp(
    sys.executable,
    [
        sys.executable,
        "-m",
        "uvicorn",
        "server:app",
        "--host",
        "0.0.0.0",
        "--port",
        port,
    ],
)
