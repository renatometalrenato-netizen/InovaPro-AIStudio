import base64
import io
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile

TARGET = "/tmp/inovapro"

def github_text(path: str, ref: str) -> str:
    encoded_path = urllib.parse.quote(path, safe="/")
    encoded_ref = urllib.parse.quote(ref, safe="")
    url = f"https://api.github.com/repos/renatometalrenato-netizen/InovaPro-AIStudio/contents/{encoded_path}?ref={encoded_ref}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "InovaPro-Railway"})
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

subprocess.check_call([
    sys.executable, "-m", "pip", "install", "--no-cache-dir",
    "-r", os.path.join(TARGET, "requirements-runtime.txt")
])

port = os.environ.get("PORT", "8000")
os.chdir(TARGET)
os.execvp(sys.executable, [
    sys.executable, "-m", "uvicorn", "server:app",
    "--host", "0.0.0.0", "--port", port
])
