from flask import Flask, render_template, request, jsonify
import subprocess
import pyautogui
import keyboard
import json
import os
from pathlib import Path

app = Flask(__name__)

CONFIG_FILE = 'config.json'

# -----------------------------
# تحميل/حفظ الإعدادات (UTF-8)
# -----------------------------
def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)

def get_vmware_settings():
    cfg = load_config()
    return cfg.get('vmware', {})

# --------------------------------------
# البحث عن جميع ملفات .vmx في المسارات
# --------------------------------------
def find_vmx_files():
    """يمسح search_paths عن ملفات .vmx ويرجع [{name, vmx}]"""
    settings = get_vmware_settings()
    paths = settings.get('search_paths', [])
    results = []
    seen = set()

    for base in paths:
        p = Path(base)
        if not p.exists():
            continue
        for vmx in p.rglob('*.vmx'):
            try:
                name = vmx.parent.name  # اسم المجلد كافتراض
                # نحاول استخراج displayName من ملف .vmx إن وجد
                try:
                    with vmx.open('r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            if line.strip().startswith('displayName'):
                                # displayName = "..."
                                name = line.split('=', 1)[1].strip().strip('"')
                                break
                except Exception:
                    pass
                s = str(vmx)
                if s not in seen:
                    results.append({'name': name, 'vmx': s})
                    seen.add(s)
            except Exception:
                pass
    return results

def get_vmrun_path():
    settings = get_vmware_settings()
    if os.name == 'nt':
        return settings.get('vmrun_path_win') or 'vmrun.exe'
    else:
        return settings.get('vmrun_path_linux') or 'vmrun'

# -----------
# المسارات
# -----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/buttons')
def get_buttons():
    # ترجع كامل config (فيه pages + إعدادات vmware)
    return jsonify(load_config())

@app.route('/vms')
def list_vms():
    return jsonify({'vms': find_vmx_files()})

@app.route('/run', methods=['POST'])
def run_action():
    data = request.json or {}
    action_type = data.get('type')
    value       = data.get('value')        # launch_app / open_file / send_text / hotkey
    value_win   = data.get('value_win')    # shell (Windows)
    value_linux = data.get('value_linux')  # shell (Linux)
    try:
        if action_type == 'launch_app':
            # مثال: "C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe"
            if os.name == 'nt':
                os.startfile(value)  # يتعامل تلقائياً مع المسارات/المسافات
            else:
                subprocess.Popen(value, shell=True)

        elif action_type == 'open_file':
            if os.name == 'nt':
                os.startfile(value)
            else:
                subprocess.Popen(['xdg-open', value], shell=False)

        elif action_type == 'send_text':
            pyautogui.write(value)

        elif action_type == 'hotkey':
            keyboard.send(value)

        elif action_type == 'shell':
            # أوامر نظام عامة
            if os.name == 'nt':
                cmd = value_win or value
                if not cmd:
                    return jsonify({'status': 'error', 'message': 'No command for Windows'}), 400
                subprocess.Popen(['cmd', '/c', cmd], shell=True)
            else:
                cmd = value_linux or value
                if not cmd:
                    return jsonify({'status': 'error', 'message': 'No command for Linux'}), 400
                subprocess.Popen(['bash', '-lc', cmd], shell=False)

        elif action_type == 'vmware':
            # data: {'op': 'start'|'stop', 'vmx': 'C:\\path\\vm.vmx'}
            op  = data.get('op')
            vmx = data.get('vmx')
            if not op or not vmx:
                return jsonify({'status': 'error', 'message': 'Missing op/vmx'}), 400

            vmrun = get_vmrun_path()
            if op == 'start':
                # gui (واجهه) أو nogui (بدون واجهة)
                cmd = [vmrun, 'start', vmx, 'gui']
            elif op == 'stop':
                # soft (لطيف) — غيّر لـ 'hard' لو تبغى إيقاف إجباري
                cmd = [vmrun, 'stop', vmx, 'soft']
            else:
                return jsonify({'status': 'error', 'message': f'Unknown op: {op}'}), 400

            subprocess.Popen(cmd, shell=(os.name == 'nt'))

        else:
            return jsonify({'status': 'error', 'message': f'Unknown action type: {action_type}'}), 400

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

    return jsonify({'status': 'success'})

if __name__ == '__main__':
    # شغّل على الشبكة المحلية للي يبي يفتح من شاشة لمس خارجية
    app.run(host='0.0.0.0', port=5000)
