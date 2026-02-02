from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.services.api_client import safe_get, safe_post, handle_api_response
from app.services.data_service import fetch_analytics_data, fetch_patient_from_api
from app.utils import calculate_age

operator_bp = Blueprint('operator', __name__)

@operator_bp.route("/operator/dashboard", methods=["GET"], endpoint="operator_dashboard")
def operator_dashboard():
    if session.get("role") != "operator":
        return redirect(url_for("auth.operator_login"))
    
    q = request.args.get("q", "").strip()
    params = {}
    if session.get("username"):
        params["operator"] = session.get("username")
    if q:
        params["q"] = q
        
    resp = safe_get("/api/search/patients", params=params)
    success, data = handle_api_response(resp)
    patients = data if success and isinstance(data, list) else []
    
    analytics = fetch_analytics_data()
    
    return render_template(
        "operator_dashboard.html",
        patients=patients,
        q=q,
        total_patients=len(patients),
        total_visits=analytics.get("total_visits", 0),
        total_scans=analytics.get("total_scans", 0),
        analytics=analytics,
        hospital_name=session.get("hospital_name"),
        is_admin=session.get("is_admin", False)
    )

@operator_bp.route("/operator/link", methods=["POST"], endpoint="operator_link_patient")
def operator_link_patient():
    payload = {
        "operator_username": session.get("username"),
        "qr_id": request.form.get("qr_id"),
        "external_patient_id": request.form.get("external_patient_id"),
    }
    resp = safe_post("/api/patient/link", json=payload)
    success, message = handle_api_response(resp, "Patient linked to your hospital.")
    if not success:
        flash(message, "danger")
    return redirect(url_for("operator.operator_dashboard"))

@operator_bp.route("/operator/assign", methods=["POST"], endpoint="operator_assign")
def operator_assign():
    qr_id = request.form.get("qr_id")
    payload = {
        "operator_username": session.get("username"),
        "qr_id": qr_id,
        "external_patient_id": f"MAN-ASSIGN-{qr_id}"
    }
    resp = safe_post("/api/patient/link", json=payload)
    success, message = handle_api_response(resp, "Patient assigned to hospital successfully.")
    if success:
        return redirect(url_for("operator.operator_dashboard", q=qr_id))
    flash(message, "danger")
    return redirect(url_for("operator.operator_dashboard"))

@operator_bp.route("/operator/edit/<qr_id>", methods=["GET", "POST"], endpoint="operator_edit")
def operator_edit(qr_id):
    if request.method == "POST":
        payload = {k: v for k, v in request.form.items()}
        resp = safe_post(f"/api/patient/{qr_id}/update", json=payload)
        success, msg = handle_api_response(resp, "Patient updated successfully")
        if success:
            return redirect(url_for("operator.operator_dashboard", q=qr_id))
        flash(msg, "danger")
        
    success, patient = fetch_patient_from_api(qr_id)
    if not success:
        flash("Patient not found", "danger")
        return redirect(url_for("operator.operator_dashboard"))
    
    if patient:
        patient["age"] = calculate_age(patient.get("birthdate"))
    return render_template("operator_edit.html", patient=patient, qr_id=qr_id)

@operator_bp.route("/analytics", endpoint="analytics_dashboard")
def analytics_dashboard():
    if session.get("role") not in ("operator", "doctor"):
         return redirect(url_for("auth.operator_login"))
    data = fetch_analytics_data()
    return render_template("analytics.html", data=data)
