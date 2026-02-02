from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.services.api_client import safe_get, safe_post, handle_api_response
from app.services.data_service import (
    fetch_patient_from_api, fetch_visits_from_api, 
    fetch_visit_labs_map
)
from app.utils import calculate_age

doctor_bp = Blueprint('doctor', __name__)

@doctor_bp.route("/doctor/dashboard", methods=["GET", "POST"], endpoint="doctor_dashboard")
def doctor_dashboard():
    if session.get("role") != "doctor":
        return redirect(url_for("auth.doctor_login"))

    doctor = session.get("doctor_profile")
    qr_id = request.args.get("qr_id") or request.form.get("qr_id")
    
    patient = {}
    visits = []
    visit_labs = {}
    registration_labs = []
    
    if qr_id:
        doctor_id = doctor.get("id")
        params = {"doctor_id": doctor_id}

        resp = safe_get(f"/api/patient/{qr_id}", params=params)
        success, patient_data = handle_api_response(resp)
        
        if success:
            patient.update(patient_data)
            patient["age"] = calculate_age(patient.get("birthdate"))
            visits = fetch_visits_from_api(qr_id)
            visit_labs = fetch_visit_labs_map(visits)
            labs_resp = safe_get(f"/api/registration_labs/{qr_id}")
            if labs_resp and labs_resp.status_code == 200:
                registration_labs = labs_resp.json()
        else:
             error_msg = str(patient_data)
             flash(f"Error: {error_msg}", "danger")
             if "Access denied" in error_msg:
                 return render_template("doctor_dashboard.html", doctor=doctor, patient=None, qr_id=None, access_denied_qr=qr_id, today=datetime.now().strftime("%Y-%m-%d"))
             qr_id = None
             
        if request.method == "POST" and qr_id:
            payload = {
                "qr_id": qr_id,
                "visit_date": request.form.get("visit_date") or datetime.now().strftime("%Y-%m-%d"),
                "diagnosis": request.form.get("diagnosis", ""),
                "treatment": request.form.get("treatment", ""),
                "medicines": request.form.get("medicines", ""),
                "created_by": doctor.get("full_name") or session.get("username"),
            }
            resp = safe_post("/api/visit", json=payload)
            success, message = handle_api_response(resp, "Visit added successfully!")
            if success:
                return redirect(url_for("doctor.doctor_dashboard", qr_id=qr_id))
            flash(message, "danger")

    return render_template("doctor_dashboard.html", doctor=doctor, patient=patient, visits=visits, visit_labs=visit_labs, registration_labs=registration_labs, qr_id=qr_id, today=datetime.now().strftime("%Y-%m-%d"))

@doctor_bp.route("/doctor/emergency-link", methods=["POST"], endpoint="doctor_emergency_link")
def doctor_emergency_link():
    doctor_profile = session.get("doctor_profile", {})
    payload = {
        "doctor_id": doctor_profile.get("id"),
        "qr_id": request.form.get("qr_id"),
        "reason": request.form.get("reason", "Emergency declared by doctor")
    }
    resp = safe_post("/api/doctor/emergency-link", json=payload)
    success, message = handle_api_response(resp, "Patient connected to hospital successfully.")
    if success:
        return redirect(url_for("doctor.doctor_dashboard", qr_id=payload["qr_id"]))
    flash(message, "danger")
    return redirect(url_for("doctor.doctor_dashboard"))
