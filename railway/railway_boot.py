import base64
import io
import os
import subprocess
import sys
import urllib.request
import zipfile

BASE = "https://raw.githubusercontent.com/renatometalrenato-netizen/InovaPro-AIStudio/deploy/mobile-v2-backend/railway"
TARGET = "/tmp/inovapro"

payload = urllib.request.urlopen(f"{BASE}/backend_bundle.b64", timeout=30).read().decode("utf-8")
data = base64.b64decode(payload)
os.makedirs(TARGET, exist_ok=True)
with zipfile.ZipFile(io.BytesIO(data)) as archive:
    archive.extractall(TARGET)

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
