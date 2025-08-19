# app.py
import os
import platform
import time
from pathlib import Path
from routes.vmware_routes import vmware_bp

from flask import Flask, send_from_directory, request, jsonify

# أدوات عامة
from utils.helpers import load_config, run_program, run_shell

# عميل OBS (مطلوب لبعض المسارات)
try:
    import obsws_python as obs
except Exception:
    obs = None

# الروترات المنفصلة (لو حاب تستخدمها بالإضافة للمسار الموحد /run)
from routes.obs_routes import obs_bp

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__, static_folder="static", static_url_path="/static")

# تسجيل الـ Blueprints الاختيارية
app.register_blueprint(vmware_bp)
app.register_blueprint(obs_bp)


# --------- OBS client ---------
def obs_client():
    """يرجع عميل OBS WebSocket مبنيًا على config.json"""
    if obs is None:
        raise RuntimeError("obsws-python غير مثبت")
    cfg = load_config()
    ws = cfg.get("obs_ws", {}) or {}
    return obs.ReqClient(
        host=ws.get("host", "127.0.0.1"),
        port=int(ws.get("port", 4455)),
        password=ws.get("password", ""),
        timeout=3.0,
    )


# --------- صفحات الواجهة ---------
@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/api/pages")
def api_pages():
    cfg = load_config()
    return jsonify({"pages": cfg.get("pages", [])})


# --------- منفذ موحّد لتنفيذ الأزرار من الواجهة ---------
@app.route("/run", methods=["POST"])
def run_action():
    data = request.get_json(force=True)
    t = data.get("type")

    try:
        # 1) تشغيل برنامج/اختصار عادي
        if t == "program":
            ok, msg = run_program(data.get("path", ""), data.get("args", ""))
            return jsonify({"status": "success" if ok else "error", "message": msg}), (
                200 if ok else 400
            )

        # 2) أمر شِل مباشرة
        elif t == "shell":
            ok, msg = run_shell(data.get("command", ""))
            return jsonify({"status": "success" if ok else "error", "message": msg}), (
                200 if ok else 400
            )

        # (للتوافق فقط) — لا ننفذ شيء هنا
        elif t == "shortcut":
            return jsonify({"status": "success", "message": "ignored"}), 200

        # 3) أوامر OBS عبر WebSocket (لا تعتمد على الفوكس)
        elif t == "obs_ws":
            if obs is None:
                return jsonify({"status": "error", "message": "obsws-python غير مثبت"}), 500

            client = obs_client()
            op = (data.get("op") or "").strip()

            if op == "start_stream":
                client.start_stream()
            elif op == "stop_stream":
                client.stop_stream()
            elif op == "start_record":
                client.start_record()
            elif op == "stop_record":
                client.stop_record()
            elif op == "set_scene":
                scene = data.get("scene")
                if not scene:
                    return jsonify({"status": "error", "message": "scene مفقودة"}), 400
                client.set_current_program_scene(scene)
            elif op == "toggle_mute":
                source = data.get("source")
                if not source:
                    return jsonify({"status": "error", "message": "source مفقودة"}), 400
                res = client.get_input_mute(source)   # v1.6 → يرجع dataclass فيه input_muted
                client.set_input_mute(source, not res.input_muted)
            elif op == "screenshot":
                directory = data.get("dir") or str(BASE_DIR)
                source = data.get("source")
                if not source:
                    return jsonify(
                        {"status": "error", "message": "source مفقودة للّقطة"}
                    ), 400
                filename = f"snap_{int(time.time())}.png"
                client.save_source_screenshot(source, "png", str(Path(directory) / filename), 0, 0)
            else:
                return jsonify({"status": "error", "message": f"Unknown op: {op}"}), 400

            return jsonify({"status": "success"})

        # 4) أوامر VMware عبر vmrun
        elif t == "vmware":
            cfg_vm = load_config().get("vmware", {})
            vmrun = (
                cfg_vm.get("vmrun_path_win")
                if platform.system() == "Windows"
                else cfg_vm.get("vmrun_path_linux")
            )
            if not vmrun or not os.path.exists(vmrun):
                return jsonify({"status": "error", "message": "vmrun.exe غير موجود"}), 500

            vmx = data.get("vmx")
            op = data.get("op", "start")
            if not vmx or not os.path.exists(vmx):
                return jsonify({"status": "error", "message": "ملف VMX غير موجود"}), 400

            cmd = f"\"{vmrun}\" {op} \"{vmx}\" nogui"
            ok, msg = run_shell(cmd)
            return jsonify({"status": "success" if ok else "error", "message": msg}), (
                200 if ok else 500
            )

        else:
            return jsonify({"status": "error", "message": f"نوع غير مدعوم: {t}"}), 400

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    # شغّل السيرفر
    app.run(host="0.0.0.0", port=5000, debug=True)
