from flask import Blueprint, request, jsonify
import os, platform
from utils.helpers import load_config, run_shell

vmware_bp = Blueprint("vmware", __name__)

# -------- Helpers --------
def _existing(p: str | None) -> str | None:
    return p if p and os.path.exists(p) else None

def _vmrun_path() -> str | None:
    """Try to resolve vmrun.exe path on Windows, or 'vmrun' on Linux."""
    cfg = load_config().get("vmware", {})
    path = cfg.get("vmrun_path_win") if platform.system() == "Windows" else cfg.get("vmrun_path_linux")
    if _existing(path):
        return path

    # Try PATH
    cmd = "where vmrun" if platform.system() == "Windows" else "which vmrun"
    ok, out = run_shell(cmd)
    if ok:
        for line in (out or "").splitlines():
            line = line.strip().strip('"')
            if platform.system() == "Windows":
                if line.lower().endswith("vmrun.exe") and os.path.exists(line):
                    return line
            else:
                if os.path.exists(line):
                    return line

    # Common Windows locations
    if platform.system() == "Windows":
        candidates = [
            r"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe",
            r"C:\Program Files\VMware\VMware Workstation\vmrun.exe",
        ]
        pf  = os.environ.get("ProgramFiles")
        pfx = os.environ.get("ProgramFiles(x86)")
        if pf:
            candidates.append(os.path.join(pf, "VMware", "VMware Workstation", "vmrun.exe"))
        if pfx:
            candidates.append(os.path.join(pfx, "VMware", "VMware Workstation", "vmrun.exe"))
        for c in candidates:
            if os.path.exists(c):
                return c
    return None

# -------- Route --------
@vmware_bp.route("/vmware/run", methods=["POST"])
def run_vmware():
    d = request.get_json(force=True) or {}
    vmx = d.get("vmx")
    op  = (d.get("op") or "start").strip()

    vmrun = _vmrun_path()
    if not vmrun:
        return jsonify({
            "status": "error",
            "message": "vmrun.exe غير موجود. عدّل vmrun_path_win في config.json أو أضِفه للـ PATH. مثال: C:\\Program Files (x86)\\VMware\\VMware Workstation\\vmrun.exe"
        }), 500

    # -------- Commands that don't require VMX --------
    if op == "vmrun_version":
        ok, msg = run_shell(f"\"{vmrun}\" -v")
        return jsonify({"status": "success" if ok else "error", "message": msg}), (200 if ok else 500)

    # -------- Validate VMX for all other ops --------
    if not vmx or not os.path.exists(vmx):
        return jsonify({"status": "error", "message": "ملف VMX غير موجود"}), 400

    # -------- guest_key: send keystrokes inside guest (xdotool) --------
    if op == "guest_key":
        user = d.get("guest_user") or d.get("user")
        pw   = d.get("guest_pass") or d.get("pass")
        keys = (d.get("keys") or "").strip()
        if not (user and pw and keys):
            return jsonify({"status": "error", "message": "يلزم guest_user و guest_pass و keys"}), 400

        prog = d.get("guest_prog") or "/usr/bin/xdotool"
        cmd  = (
            f"\"{vmrun}\" -T ws -gu \"{user}\" -gp \"{pw}\" "
            f"runProgramInGuest \"{vmx}\" -noWait -activeWindow -interactive "
            f"\"/usr/bin/env\" \"DISPLAY=:0\" \"{prog}\" \"key\" \"{keys}\""
        )
        ok, msg = run_shell(cmd)
        return jsonify({"status": "success" if ok else "error", "message": msg}), (200 if ok else 500)

    # -------- guest_shell: run a shell command inside guest (bash -lc) --------
    if op == "guest_shell":
        user  = d.get("guest_user") or d.get("user")
        pw    = d.get("guest_pass") or d.get("pass")
        shell = (d.get("shell") or "").strip()
        if not (user and pw and shell):
            return jsonify({"status": "error", "message": "يلزم guest_user و guest_pass و shell"}), 400

        cmd = (
            f"\"{vmrun}\" -T ws -gu \"{user}\" -gp \"{pw}\" "
            f"runProgramInGuest \"{vmx}\" -noWait -interactive "
            f"\"/bin/bash\" \"-lc\" \"{shell}\""
        )
        ok, msg = run_shell(cmd)
        return jsonify({"status": "success" if ok else "error", "message": msg}), (200 if ok else 500)

    # -------- guest_run: run a program with optional env/args inside guest --------
    if op == "guest_run":
        user    = d.get("guest_user") or d.get("user")
        pw      = d.get("guest_pass") or d.get("pass")
        program = (d.get("program") or "").strip()
        args    = d.get("args") or []
        env     = d.get("env")  or {}
        if not (user and pw and program):
            return jsonify({"status": "error", "message": "يلزم guest_user و guest_pass و program"}), 400

        env_tokens  = " ".join([f"\"{k}={v}\"" for k, v in env.items()])
        args_tokens = " ".join([f"\"{a}\""     for a in args])
        space_between = " " if env_tokens else ""
        cmd = (
            f"\"{vmrun}\" -T ws -gu \"{user}\" -gp \"{pw}\" "
            f"runProgramInGuest \"{vmx}\" -noWait -interactive "
            f"\"/usr/bin/env\" {env_tokens}{space_between}\"{program}\" {args_tokens}"
        ).strip()
        ok, msg = run_shell(cmd)
        return jsonify({"status": "success" if ok else "error", "message": msg}), (200 if ok else 500)

    # -------- guest_type: type text inside guest (xdotool type) --------
    if op == "guest_type":
        user = d.get("guest_user") or d.get("user")
        pw   = d.get("guest_pass") or d.get("pass")
        text = (d.get("text") or "").strip()
        send_enter = bool(d.get("enter", True))  # defaults to pressing Enter after typing
        if not (user and pw and text):
            return jsonify({"status": "error", "message": "يلزم guest_user و guest_pass و text"}), 400

        prog = d.get("guest_prog") or "/usr/bin/xdotool"

        # type text
        cmd1 = (
            f"\"{vmrun}\" -T ws -gu \"{user}\" -gp \"{pw}\" "
            f"runProgramInGuest \"{vmx}\" -noWait -activeWindow -interactive "
            f"\"/usr/bin/env\" \"DISPLAY=:0\" \"{prog}\" \"type\" \"--delay\" \"1\" \"{text}\""
        )
        ok1, msg1 = run_shell(cmd1)
        if not ok1:
            return jsonify({"status": "error", "message": msg1}), 500

        # optional Enter
        if send_enter:
            cmd2 = (
                f"\"{vmrun}\" -T ws -gu \"{user}\" -gp \"{pw}\" "
                f"runProgramInGuest \"{vmx}\" -noWait -activeWindow -interactive "
                f"\"/usr/bin/env\" \"DISPLAY=:0\" \"{prog}\" \"key\" \"Return\""
            )
            ok2, msg2 = run_shell(cmd2)
            if not ok2:
                return jsonify({"status": "error", "message": msg2}), 500

        return jsonify({"status": "success", "message": "typed"})

    # -------- Standard VMware ops --------
    # Supports: start | stop [soft|hard] | reset [soft|hard] | suspend | pause | unpause
    op_parts = op.split()
    cmd = f"\"{vmrun}\" {' '.join(op_parts)} \"{vmx}\" nogui"
    ok, msg = run_shell(cmd)
    return jsonify({"status": "success" if ok else "error", "message": msg}), (200 if ok else 500)
