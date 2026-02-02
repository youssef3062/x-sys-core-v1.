from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.services.api_client import safe_get, safe_post, handle_api_response

admin_bp = Blueprint('admin', __name__)

@admin_bp.route("/admin/logs_view", endpoint="admin_logs_view")
def admin_logs_view():
    resp = safe_get("/api/admin/logs", params={"limit": 50})
    success, data = handle_api_response(resp)
    logs = data if success and isinstance(data, list) else []
    return render_template("admin_logs.html", logs=logs)

@admin_bp.route("/admin/connection-logs", endpoint="admin_connection_logs")
def admin_connection_logs():
    q = request.args.get("q", "")
    status = request.args.get("status", "all")
    limit = request.args.get("limit", 100)
    
    params= {"admin_username": session.get("username"), "q": q, "status": status, "limit": limit}
    resp = safe_get("/api/admin/connection-logs", params=params)
    
    success, data = handle_api_response(resp)
    logs = data.get("logs", []) if success and isinstance(data, dict) else []
    stats = data.get("stats", {}) if success and isinstance(data, dict) else {}
    
    return render_template("admin_connection_logs.html", logs=logs, stats=stats)


@admin_bp.route("/admin/connection-logs/export", endpoint="admin_connection_logs_export")
def admin_connection_logs_export():
    import io
    import csv
    from flask import Response
    
    q = request.args.get("q", "")
    status = request.args.get("status", "all")
    
    params= {"admin_username": session.get("username"), "q": q, "status": status, "limit": "all"}
    resp = safe_get("/api/admin/connection-logs", params=params)
    success, data = handle_api_response(resp)
    logs = data.get("logs", []) if success and isinstance(data, dict) else []
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Timestamp", "Action", "Patient", "QR ID", "Hospital", "Performed By", "Notes"])
    
    for log in logs:
        cw.writerow([
            log.get("timestamp"),
            log.get("action"),
            log.get("patient_name"),
            log.get("qr_id"),
            log.get("hospital_name"),
            log.get("performed_by"),
            log.get("notes")
        ])
    
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=connection_logs.csv"}
    )
@admin_bp.route("/admin/disconnect_patient", methods=["POST"], endpoint="admin_disconnect_patient")
def admin_disconnect_patient():
    patient_id = request.form.get("patient_id")
    hospital_id = request.form.get("hospital_id")
    reason = request.form.get("reason")
    
    if not patient_id or not hospital_id:
        flash("Missing patient or hospital information", "danger")
        return redirect(request.referrer or url_for("admin.admin_connection_logs"))
    
    resp = safe_post("/api/admin/disconnect_patient", data={
        "patient_id": patient_id,
        "hospital_id": hospital_id,
        "reason": reason,
        "admin_username": session.get("username")
    })
    
    success, msg = handle_api_response(resp, "Patient disconnected successfully")
    if not success:
         flash(msg, "danger")
         
    return redirect(request.referrer or url_for("admin.admin_connection_logs"))

@admin_bp.route("/admin/add_qr", methods=["POST"], endpoint="admin_add_qr")
def admin_add_qr():
    qr_id = request.form.get("qr_id")
    if not qr_id:
        flash("QR ID required", "danger")
        return redirect(request.referrer or url_for("common.scanner_gate"))
        
    resp = safe_post("/api/admin/qrs", json={"qr_id": qr_id})
    success, msg = handle_api_response(resp, "QR Code added successfully")
    if success:
         return redirect(url_for("auth.register", qr_id=qr_id))
    flash(msg, "danger")
    return redirect(url_for("common.scanner_gate"))
