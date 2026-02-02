from flask import Blueprint, render_template, request, jsonify, send_from_directory, current_app
from app.services.api_client import safe_get

common_bp = Blueprint('common', __name__)

@common_bp.route("/photos/<path:filename>", endpoint="photos")
def serve_photo(filename):
    return send_from_directory(current_app.config["PHOTOS_DIR"], filename)

@common_bp.route("/labs/<path:filename>", endpoint="labs")
def serve_lab(filename):
    return send_from_directory(current_app.config["LABS_DIR"], filename)

@common_bp.route("/", endpoint="scanner_gate")
def scanner_gate():
    return render_template("scanner_gate.html")

@common_bp.route("/scan_result", methods=["POST"], endpoint="scan_result")
def scan_result():
    data = request.get_json() or {}
    qr_id = data.get("qr_id")
    if not qr_id:
        return jsonify({"error": "qr_id required"}), 400

    r = safe_get(f"/api/patient/{qr_id}")
    if r and r.status_code == 200:
        return jsonify({"action": "access", "qr_id": qr_id})
    else:
        return jsonify({"action": "register", "qr_id": qr_id})
