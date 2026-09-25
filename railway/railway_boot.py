import base64
import hashlib
import io
import os
import subprocess
import sys
import urllib.request
import zipfile

TARGET = "/tmp/inovapro"
REF = "main"
BASE = f"https://raw.githubusercontent.com/renatometalrenato-netizen/InovaPro-AIStudio/{REF}/railway/v7"
EXPECTED_ZIP_SHA256 = "7ac2e58222d139b018343821d68693aade066ffa49d1c669d8000cb4dcfe8786"
PART_COUNT = 6

def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "InovaPro-Railway/7"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8").strip()

print("BOOT_V7_AUTO_SYNC", flush=True)

payload = "".join(fetch_text(f"{BASE}/backend.part{i}") for i in range(1, PART_COUNT + 1))
raw = base64.b64decode(payload, validate=True)
actual_sha = hashlib.sha256(raw).hexdigest()
if actual_sha != EXPECTED_ZIP_SHA256:
    raise RuntimeError(f"Backend v7 checksum mismatch: {actual_sha}")

os.makedirs(TARGET, exist_ok=True)
with zipfile.ZipFile(io.BytesIO(raw)) as archive:
    archive.testzip()
    archive.extractall(TARGET)

# Small safe overlay so the packaged router namespace exports every v7 router.
routers_init = fetch_text(f"{BASE}/routers_init.py")
routers_init_path = os.path.join(TARGET, "app", "routers", "__init__.py")
with open(routers_init_path, "w", encoding="utf-8") as fh:
    fh.write(routers_init + "\n")
print("V7 routers overlay loaded", flush=True)

# Compatibility bridge: production historically stores the Gemini secret as
# GEMINI_API_KEY, while this backend adapter reads GOOGLE_API_KEY.
if os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

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
