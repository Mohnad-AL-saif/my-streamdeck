from flask import Blueprint, request, jsonify
from utils.helpers import load_config
import obsws_python as obs, time

obs_bp = Blueprint("obs", __name__)

def obs_client():
    cfg = load_config()
    ws_cfg = cfg.get("obs_ws", {}) or {}
    host = ws_cfg.get("host", "127.0.0.1")
    port = int(ws_cfg.get("port", 4455))
    password = ws_cfg.get("password", "")
    return obs.ReqClient(host=host, port=port, password=password, timeout=3.0)

@obs_bp.route("/obs/run", methods=["POST"])
def run_obs():
    data = request.get_json(force=True)
    op = data.get("op")

    client = obs_client()

    if op == "start_stream":
        client.start_stream()
    elif op == "stop_stream":
        client.stop_stream()
    elif op == "toggle_mute":
        source = data.get("source", "Mic/Aux")
        res = client.get_input_mute(source)
        client.set_input_mute(source, not res.input_muted)
    else:
        return jsonify({"status": "error", "message": "Unknown OBS op"}), 400

    return jsonify({"status": "success"})
