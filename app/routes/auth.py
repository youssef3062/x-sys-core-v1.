from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.services.api_client import safe_post, handle_api_response # fetch_hospitals currently undefined in api_client, I need to add it or move it.

auth_bp = Blueprint('auth', __name__)

# I will assume data_service will exist.
from app.services.data_service import fetch_hospitals

@auth_bp.route("/register", methods=["GET", "POST"], endpoint="register")
def register():
    qr_id = request.args.get("qr_id") or request.form.get("qr_id", "")
    
    if request.method == "POST":
        payload = {
            "qr_id": request.form.get("qr_id", "").strip(),
            "username": request.form.get("username", "").strip(),
            "password": request.form.get("password", "").strip(),
            "name": request.form.get("name", "").strip(),
            "email": request.form.get("email", "").strip(),
            "phone": request.form.get("phone", "").strip(),
            "birthdate": request.form.get("birthdate") or None,
            "gender": request.form.get("gender", ""),
            "chronic_diseases": request.form.get("chronic_diseases", ""),
            "medications": request.form.get("medications", ""),
            "emergency_contact": request.form.get("emergency_contact", ""),
            "other_info": request.form.get("other_info", ""),
            "monthly_pills": int(request.form.get("monthly_pills") or 0),
            "hospital_id": request.form.get("hospital_id"),
            "hospital_patient_id": request.form.get("hospital_patient_id"),
        }
        
        r = safe_post("/api/register", json=payload)
        success, result = handle_api_response(r, "Registration successful! Please login.")
        
        if success:
            return redirect(url_for("auth.login"))
        else:
            flash(result, "danger")
    
    hospitals = fetch_hospitals()
    return render_template("register.html", qr_id=qr_id, hospitals=hospitals)

@auth_bp.route("/login", methods=["GET", "POST"], endpoint="login")
def login():
    qr_id = request.args.get("qr_id")
    if request.method == "POST":
        payload = {
            "username": request.form.get("username", "").strip(),
            "password": request.form.get("password", "").strip()
        }
        r = safe_post("/api/login", json=payload)
        success, result = handle_api_response(r)
        
        if success:
            session.clear()
            session["role"] = "patient"
            session["username"] = payload["username"]
            session["qr_id"] = result.get("qr_id")
            flash("Login successful!", "success")
            return redirect(url_for("patient.dashboard"))
        else:
            flash(result, "danger")
    return render_template("login.html", qr_id=qr_id)

@auth_bp.route("/doctor/register", methods=["GET", "POST"], endpoint="doctor_register")
def doctor_register():
    if request.method == "POST":
        hospital_id = request.form.get("hospital_id")
        if hospital_id == "":
            hospital_id = None
        payload = {
            "full_name": request.form.get("full_name", "").strip(),
            "specialty": request.form.get("specialty", "").strip(),
            "phone": request.form.get("phone", "").strip(),
            "email": request.form.get("email", "").strip(),
            "hospital": request.form.get("hospital", "").strip(),
            "username": request.form.get("username", "").strip(),
            "password": request.form.get("password", "").strip(),
            "hospital_id": hospital_id
        }
        r = safe_post("/api/doctor/register", json=payload)
        success, result = handle_api_response(r, "Doctor registered successfully! Please login.")
        if success:
            return redirect(url_for("auth.doctor_login"))
        else:
            flash(result, "danger")
            
    hospitals = fetch_hospitals()
    return render_template("doctor_register.html", hospitals=hospitals)

@auth_bp.route("/doctor/login", methods=["GET", "POST"], endpoint="doctor_login")
def doctor_login():
    if request.method == "POST":
        payload = {
            "username": request.form.get("username", "").strip(),
            "password": request.form.get("password", "").strip()
        }
        r = safe_post("/api/doctor/login", json=payload)
        # Note: handle_api_response signature is (response, success_message=None).
        success, result = handle_api_response(r)
        if success:
            session.clear()
            session["role"] = "doctor"
            session["username"] = payload["username"]
            session["doctor"] = payload["username"]
            doctor_data = result.get("doctor", {})
            if not doctor_data.get("id"):
                flash("Login error: Doctor ID missing", "danger")
                return render_template("doctor_login.html")
            session["doctor_profile"] = doctor_data
            flash("Doctor login successful!", "success")
            return redirect(url_for("doctor.doctor_dashboard"))
        else:
            flash(result, "danger")
    return render_template("doctor_login.html")

@auth_bp.route("/operator/create", methods=["GET", "POST"], endpoint="create_operator")
def create_operator():
    if request.method == "POST":
        payload = {
            "username": request.form.get("username", "").strip(),
            "password": request.form.get("password", "").strip(),
            "master_key": request.form.get("master_key", "").strip(),
            "hospital_id": request.form.get("hospital_id") or None,
            "is_admin": request.form.get("username", "").lower() == "brescan"
        }
        r = safe_post("/api/operator/register", json=payload)
        success, result = handle_api_response(r, "Operator created successfully! You can now log in.")
        if success:
            return redirect(url_for("auth.operator_login"))
        flash(result, "danger")
    
    hospitals = fetch_hospitals()
    return render_template("create_operator.html", hospitals=hospitals)

@auth_bp.route("/operator/login", methods=["GET", "POST"], endpoint="operator_login")
def operator_login():
    if request.method == "POST":
        payload = {
            "username": request.form.get("username", "").strip(),
            "password": request.form.get("password", "").strip()
        }
        resp = safe_post("/api/operator/login", json=payload)
        success, data = handle_api_response(resp)
        if success:
            session["role"] = "operator"
            session["username"] = data.get("username")
            session["hospital_id"] = data.get("hospital_id")
            session["hospital_name"] = data.get("hospital_name")
            session["is_admin"] = data.get("is_admin")
            session["operator_id"] = data.get("operator_id")
            flash(f"Welcome back, {session['username']}!", "success")
            return redirect(url_for("operator.operator_dashboard"))
        else:
            flash(data, "danger")
    return render_template("login.html")

@auth_bp.route("/logout", endpoint="logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
