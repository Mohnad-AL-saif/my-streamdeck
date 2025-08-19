import os, json, platform, subprocess, time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"

def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def run_program(path, args=""):
    try:
        if path.lower().endswith(".lnk") and platform.system() == "Windows":
            os.startfile(path)  # type: ignore
            return True, "started"
        subprocess.Popen([path] + ([args] if args else []), shell=False)
        return True, "started"
    except Exception as e:
        return False, str(e)

def run_shell(cmd):
    try:
        completed = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        ok = completed.returncode == 0
        msg = completed.stdout if ok else (completed.stderr or completed.stdout)
        return ok, msg.strip()
    except Exception as e:
        return False, str(e)
