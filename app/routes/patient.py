import os
import io
import csv
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, Response
from werkzeug.utils import secure_filename

from app.services.api_client import safe_get, safe_post, handle_api_response
from app.services.data_service import (
    fetch_patient_from_api, fetch_visits_from_api, 
    fetch_visit_labs_map
)
from app.utils import calculate_age, allowed_lab_file

logger = logging.getLogger("brescan-frontend")
patient_bp = Blueprint('patient', __name__)

@patient_bp.route("/dashboard", endpoint="dashboard")
def dashboard():
    qr_id = session.get("qr_id")
    if not qr_id:
        flash("Please login first", "warning")
        return redirect(url_for("auth.login"))
    
    # We call api directly or use helper? Helper is better.
    # But wait, helper fetch_patient_from_api returns (success, data).
    # And original code did:
    # rp = safe_get(f"/api/patient/{qr_id}")
    # success, patient_data = handle_api_response(rp)
    # The helper wraps exactly this.
    
    success, patient_data = fetch_patient_from_api(qr_id)
    
    if not success:
        flash(patient_data, "danger")
        return redirect(url_for("auth.login"))
    
    patient = patient_data
    patient["age"] = calculate_age(patient.get("birthdate"))
    
    visits = fetch_visits_from_api(qr_id)
    visit_labs = fetch_visit_labs_map(visits)
    
    rl = safe_get(f"/api/registration_labs/{qr_id}")
    labs_success, labs_data = handle_api_response(rl)
    registration_labs = labs_data if labs_success else []
    
    ht = safe_get("/api/health_tip")
    tip_success, tip_data = handle_api_response(ht)
    health_tip = tip_data.get("tip", "Stay healthy!") if tip_success else "Stay healthy!"
    
    pills_total = patient.get("monthly_pills") or 0
    pill_progress = min(100, pills_total * 3) if pills_total else 0
    
    return render_template("dashboard.html",
                           patient=patient,
                           visits=visits,
                           visit_labs=visit_labs,
                           registration_labs=registration_labs,
                           age=patient["age"],
                           pill_progress=pill_progress,
                           health_tip=health_tip,
                           qr_id=qr_id)

@patient_bp.route("/visit/add", methods=["POST"], endpoint="visit_add")
def visit_add():
    # Keep existing logic for backward compatibility (dashboard modal?)
    if session.get("role") not in ("doctor", "operator", "patient"):
        flash("Please log in first", "danger")
        return redirect(url_for("auth.login"))
    
    qr_id = request.form.get("qr_id") or session.get("qr_id")
    if not qr_id:
        flash("No QR ID provided", "danger")
        return redirect(url_for("patient.dashboard"))
    
    payload = {
        "qr_id": qr_id,
        "visit_date": request.form.get("visit_date") or datetime.now().strftime("%Y-%m-%d"),
        "diagnosis": request.form.get("diagnosis", ""),
        "treatment": request.form.get("treatment", ""),
        "medicines": request.form.get("medicines", ""),
        "created_by": session.get("username", "web_user")
    }
    
    r = safe_post("/api/visit", json=payload)
    success, result = handle_api_response(r, "Visit added successfully!")
    
    if not success:
        flash(result, "danger")
    
    if session.get("role") == "doctor":
        return redirect(url_for("doctor.doctor_dashboard"))
    elif session.get("role") == "operator":
        # Check if we should redirect to operator dashboard with specific query
        return redirect(url_for("operator.operator_dashboard", q=qr_id))
    return redirect(url_for("patient.dashboard"))

@patient_bp.route("/visit/new/<qr_id>", methods=["GET", "POST"], endpoint="add_visit")
def add_visit(qr_id):
    if session.get("role") not in ("doctor", "operator"):
        flash("Access denied", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        payload = {
            "qr_id": qr_id,
            "visit_date": request.form.get("visit_date") or datetime.now().strftime("%Y-%m-%d"),
            "diagnosis": request.form.get("diagnosis", ""),
            "treatment": request.form.get("treatment", ""),
            "medicines": request.form.get("medicines", ""),
            "created_by": session.get("username", "web_user")
        }
        
        r = safe_post("/api/visit", json=payload)
        success, result = handle_api_response(r, "Visit added successfully!")
        
        if success:
           # Handle file upload if present
           if "lab_file" in request.files:
               f = request.files["lab_file"]
               if f and f.filename and allowed_lab_file(f.filename):
                   filename = secure_filename(f.filename)
                   tmp_path = os.path.join(current_app.config["TMP_UPLOAD_FOLDER"], filename)
                   f.save(tmp_path)
                   try:
                       with open(tmp_path, "rb") as fh:
                           files = {"lab_file": (filename, fh, "application/octet-stream")}
                           data = {"uploaded_by": session.get("username", "unknown")}
                           r2 = safe_post(f"/api/lab/upload/{qr_id}", files=files, data=data)
                           s2, res2 = handle_api_response(r2) # soft fail on lab
                           if not s2:
                               flash(f"Visit added but lab upload failed: {res2}", "warning")
                           else:
                               flash("Visit and lab report added successfully!", "success")
                   finally:
                       if os.path.exists(tmp_path):
                           os.remove(tmp_path)
                           
           if session.get("role") == "operator":
               return redirect(url_for("operator.operator_dashboard", q=qr_id))
           return redirect(url_for("doctor.doctor_dashboard", qr_id=qr_id))
        else:
           flash(result, "danger")

    success, patient = fetch_patient_from_api(qr_id)
    if not success:
         flash("Patient not found", "danger")
         return redirect(url_for("operator.operator_dashboard"))
         
    return render_template("add_visit.html", patient=patient, qr_id=qr_id)

@patient_bp.route("/lab/upload/<qr_id>", methods=["POST"], endpoint="lab_upload")
def lab_upload(qr_id):
    if "lab_file" not in request.files:
        flash("No file provided", "danger")
        # referrer usage is good
        return redirect(request.referrer or url_for("patient.dashboard"))
    
    f = request.files["lab_file"]
    if f.filename == "":
        flash("No file selected", "danger")
        return redirect(request.referrer or url_for("patient.dashboard"))
    
    if not allowed_lab_file(f.filename):
        flash("File type not allowed", "danger")
        return redirect(request.referrer or url_for("patient.dashboard"))
    
    filename = secure_filename(f.filename)
    tmp_path = os.path.join(current_app.config["TMP_UPLOAD_FOLDER"], filename)
    f.save(tmp_path)
    
    try:
        with open(tmp_path, "rb") as fh:
            files = {"lab_file": (filename, fh, "application/octet-stream")}
            data = {"uploaded_by": session.get("username", "unknown")}
            r = safe_post(f"/api/lab/upload/{qr_id}", files=files, data=data)
            success, result = handle_api_response(r, "Lab file uploaded successfully!")
            if not success:
                flash(result, "danger")
    finally:
        try:
            os.remove(tmp_path)
        except Exception as e:
            logger.error(f"Failed to remove temp file: {e}")
    
    return redirect(url_for("patient.dashboard"))

@patient_bp.route("/access/<qr_id>", endpoint="guest_view")
def guest_view(qr_id):
    role = session.get("role")
    if role == "doctor":
        return redirect(url_for("doctor.doctor_dashboard", qr_id=qr_id))
    elif role == "operator":
        return redirect(url_for("patient.add_visit", qr_id=qr_id)) 
        
    success, patient = fetch_patient_from_api(qr_id)
    if not success:
        flash(patient, "danger")
        return render_template("guest_view.html", error=patient, qr_id=qr_id, patient=None, visits=[])

    patient["age"] = calculate_age(patient.get("birthdate"))
    visits = fetch_visits_from_api(qr_id)
    return render_template("guest_view.html", patient=patient, visits=visits, age=patient["age"], qr_id=qr_id)

@patient_bp.route("/access-options/<qr_id>", endpoint="access_options")
def access_options(qr_id):
    return render_template("access_options.html", qr_id=qr_id)

@patient_bp.route("/visit/export/<qr_id>", endpoint="export_visits")
def export_visits(qr_id):
    visits = fetch_visits_from_api(qr_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Diagnosis", "Treatment", "Medicines", "Created By"])
    for v in visits:
        writer.writerow([v.get("visit_date"), v.get("diagnosis"), v.get("treatment"), v.get("medicines"), v.get("created_by")])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-disposition": f"attachment; filename=visits_{qr_id}.csv"})
