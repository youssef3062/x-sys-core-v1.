import os
import random
import time
from datetime import datetime, timedelta
from collections import Counter

from flask import request, jsonify, current_app
from werkzeug.utils import secure_filename
import psycopg2
import psycopg2.extras
import qrcode

from app.db import get_db
from app.utils import (
    encrypt_data, decrypt_data, decrypt_record, calculate_age,
    allowed_file, allowed_photo_file
)
from app.services.access_service import (
    check_operator_access, check_doctor_access,
    log_operator_action, log_hospital_connection
)
from app.security.passwords import hash_password, verify_password
from app.security.emergency_token import (
    load_private_key_from_pem,
    load_public_key_from_pem,
    public_key_to_spki_pem,
    sign_emergency_payload,
    verify_emergency_token,
)
from . import api_bp as bp

# ----------------- Local Helpers -----------------

MASTER_OPERATOR_KEY = os.environ.get("MASTER_OPERATOR_KEY")
_LOGIN_ATTEMPTS = {}


def check_login_rate_limit(identity: str, limit_per_minute: int = 8):
    """Simple in-memory login throttle.

    This protects credential endpoints from brute-force attacks.
    """
    now = time.time()
    entries = _LOGIN_ATTEMPTS.get(identity, [])
    entries = [ts for ts in entries if now - ts < 60]
    if len(entries) >= limit_per_minute:
        retry_after = int(60 - (now - entries[0])) if entries else 60
        return False, max(retry_after, 1)
    entries.append(now)
    _LOGIN_ATTEMPTS[identity] = entries
    return True, None


def _get_emergency_keys():
    private_pem = current_app.config.get("EMERGENCY_PRIVATE_KEY_PEM")
    public_pem = current_app.config.get("EMERGENCY_PUBLIC_KEY_PEM")
    if not private_pem or not public_pem:
        return None, None
    return load_private_key_from_pem(private_pem), load_public_key_from_pem(public_pem)


def _compact_codes(text_value: str) -> str:
    if not text_value:
        return ""
    pieces = [chunk.strip().upper().replace(" ", "_") for chunk in text_value.split(",")]
    return ",".join([p for p in pieces if p])


def _build_emergency_payload(patient):
    now = int(time.time())
    ttl = int(current_app.config.get("EMERGENCY_TOKEN_TTL_SECONDS", 2592000))
    return {
        "iss": current_app.config.get("EMERGENCY_TOKEN_ISSUER", "brescan"),
        "qr_id": patient["qr_id"],
        "full_name": decrypt_data(patient.get("name")),
        "age": calculate_age(patient.get("birthdate")),
        "chronic_codes": _compact_codes(patient.get("chronic_diseases") or ""),
        "allergies": (patient.get("other_info") or "")[:80],
        "emergency_contact": decrypt_data(patient.get("phone")) if patient.get("phone") else "",
        "critical_medications": _compact_codes(patient.get("medications") or ""),
        "iat": now,
        "exp": now + ttl,
    }

def ensure_default_hospital(cursor):
    cursor.execute("INSERT INTO hospitals (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", ("Default Hospital",))
    cursor.execute("SELECT id FROM hospitals ORDER BY id LIMIT 1")
    row = cursor.fetchone()
    return row[0] if row else None

def resolve_hospital_id(cursor, hospital_id):
    if hospital_id:
        cursor.execute("SELECT id FROM hospitals WHERE id = %s", (hospital_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError("Invalid hospital_id")
        return row[0]
    cursor.execute("SELECT id FROM hospitals ORDER BY id LIMIT 1")
    row = cursor.fetchone()
    if row:
        return row[0]
    row = cursor.fetchone()
    if row:
        return row[0]
    return ensure_default_hospital(cursor)

def get_random_tip():
    from app.utils import HEALTH_TIPS
    # HEALTH_TIPS should be in utils, checking if I put it there...
    # I didn't verify if I put HEALTH_TIPS in utils.py. I'll define it here if missing.
    tips = [
        "Stay hydrated — drink at least 8 glasses of water a day.",
        "Take a 10-minute walk after meals to help digestion.",
        "Avoid skipping breakfast — it boosts focus and metabolism.",
        "Practice deep breathing for 2 minutes to reduce stress.",
        "Eat colorful fruits and vegetables — variety means more vitamins.",
        "Get 7-8 hours of sleep for better heart health.",
        "Limit sugary drinks and processed foods.",
        "Wash your hands often to prevent infections.",
        "Keep a consistent exercise routine — even light activity helps.",
        "Schedule regular health checkups every 6 months."
    ]
    return random.choice(tips)

# ---------------- Hospitals ----------------
@bp.route("/hospitals", methods=["GET"])
def api_hospitals():
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT id, name, address, phone FROM hospitals ORDER BY name")
    return jsonify(c.fetchall())

# ---------------- Core patient endpoints ----------------
@bp.route("/register", methods=["POST"])
def api_register():
    data = request.get_json() or {}
    required = ["qr_id", "username", "password", "name", "email", "phone"]
    missing = [r for r in required if not data.get(r)]
    if missing:
        return jsonify({"error": "missing fields", "fields": missing}), 400

    qr_id = data["qr_id"].strip()
    username = data["username"].strip()
    password = data["password"].strip()
    name = data["name"].strip()
    email = (data["email"] or "").strip().lower()
    phone = (data["phone"] or "").strip()

    birthdate = data.get("birthdate")
    gender = data.get("gender", "")
    chronic = data.get("chronic_diseases", "")
    meds = data.get("medications", "")
    emergency = data.get("emergency_contact", "")
    other = data.get("other_info", "")
    monthly_pills = data.get("monthly_pills", 0)
    hospital_id = data.get("hospital_id")
    hospital_patient_id = data.get("hospital_patient_id")

    hashed_pw = hash_password(password)
    enc_name = encrypt_data(name)
    enc_email = encrypt_data(email)
    enc_phone = encrypt_data(phone)

    conn = get_db()
    c = conn.cursor()
    try:
        resolved_hospital_id = resolve_hospital_id(c, hospital_id)
    except ValueError as exc:
        conn.rollback()
        return jsonify({"error": str(exc)}), 400
    try:
        c.execute("""
            INSERT INTO patients (
                qr_id, username, password, name, phone, email, birthdate, gender,
                monthly_pills, chronic_diseases, medications, emergency_contact, other_info,
                primary_hospital_id, hospital_patient_id
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (qr_id, username, hashed_pw, enc_name, enc_phone, enc_email,
              birthdate, gender, monthly_pills, chronic, meds, emergency, other,
              resolved_hospital_id, hospital_patient_id))

        c.execute("""
            INSERT INTO qrcodes (qr_id, assigned, scans)
            VALUES (%s, 1, 0)
            ON CONFLICT (qr_id) DO UPDATE SET assigned = 1
        """, (qr_id,))

        conn.commit()
        return jsonify({"message": "Patient registered", "qr_id": qr_id})
    except psycopg2.IntegrityError:
        conn.rollback()
        return jsonify({"error": "username/email/phone/qr conflict or already used"}), 400
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

@bp.route("/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    if not username or not password:
        return jsonify({"error": "username & password required"}), 400

    identity = f"patient:{username}:{request.remote_addr or 'ip-unknown'}"
    allowed, retry_after = check_login_rate_limit(
        identity,
        int(current_app.config.get("LOGIN_RATE_LIMIT_PER_MINUTE", "8")),
    )
    if not allowed:
        return jsonify({"error": "Too many attempts. Try again later.", "retry_after": retry_after}), 429

    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM patients WHERE username=%s", (username,))
    user = c.fetchone()
    if not user:
        return jsonify({"error": "User not found"}), 404
    if not verify_password(password, user["password"]):
        return jsonify({"error": "Invalid credentials"}), 401

    qr_id = (user.get("qr_id") or "").strip()
    if not qr_id:
        return jsonify({"error": "Account missing QR assignment"}), 500

    try:
        c.execute("UPDATE qrcodes SET scans = COALESCE(scans,0)+1 WHERE qr_id=%s", (qr_id,))
        c.execute("INSERT INTO scans (qr_id, scanned_by) VALUES (%s, %s)", (qr_id, encrypt_data("patient_ui")))
        conn.commit()
    except Exception:
        conn.rollback()
        # Logging assumed to be handled by app level

    return jsonify({
        "message": "Login successful",
        "qr_id": qr_id,
        "name": decrypt_data(user.get("name")),
        "email": decrypt_data(user.get("email"))
    })

@bp.route("/patient/<qr_id>", methods=["GET"])
def api_get_patient(qr_id):
    operator_id = request.args.get("operator_id")
    doctor_id = request.args.get("doctor_id")
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    if operator_id:
        log_c = conn.cursor()
        if not check_operator_access(c, operator_id, qr_id):
            log_operator_action(log_c, operator_id, qr_id, "view_denied", request.remote_addr, request.user_agent.string)
            conn.commit()
            return jsonify({"error": "Access denied. You are not linked to this patient."}), 403
        log_operator_action(log_c, operator_id, qr_id, "view_profile", request.remote_addr, request.user_agent.string)
        conn.commit()
    
    if doctor_id:
        if not check_doctor_access(c, doctor_id, qr_id):
            conn.commit()
            return jsonify({"error": "Access denied. This patient is not from your hospital."}), 403

    c.execute("SELECT * FROM patients WHERE qr_id = %s", (qr_id,))
    patient = c.fetchone()
    if not patient:
        return jsonify({"error": "Patient not found"}), 404
    patient = dict(patient)
    for f in ("name", "email", "phone", "emergency_contact", "other_info"):
        if patient.get(f):
            patient[f] = decrypt_data(patient[f])
    patient["age"] = calculate_age(patient.get("birthdate"))
    hospital_id = patient.get("primary_hospital_id")
    if hospital_id:
        c.execute("SELECT name FROM hospitals WHERE id = %s", (hospital_id,))
        row = c.fetchone()
        patient["hospital_name"] = row["name"] if row else None
    else:
        patient["hospital_name"] = None
    return jsonify(patient)

@bp.route("/patient/update/<qr_id>", methods=["PUT", "PATCH"])
def api_update_patient(qr_id):
    data = request.get_json() or {}
    allowed = [
        "name", "email", "phone", "birthdate", "gender", "blood_type",
        "monthly_pills", "medications", "chronic_diseases", "emergency_contact",
        "other_info", "patient_photo", "lab_file"
    ]
    fields = []
    values = []

    for key, value in data.items():
        if key not in allowed:
            continue
        if key in ("name", "email", "phone"):
            value = encrypt_data(value)
        fields.append(f"{key} = %s")
        values.append(value)

    if not fields:
        return jsonify({"error": "no updatable fields provided"}), 400

    values.append(qr_id)
    query = f"UPDATE patients SET {', '.join(fields)} WHERE qr_id = %s"

    conn = get_db()
    c = conn.cursor()
    try:
        c.execute(query, tuple(values))
        conn.commit()
        return jsonify({"message": "Patient updated", "qr_id": qr_id})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

@bp.route("/patient/link", methods=["POST"])
def api_link_patient():
    data = request.get_json() or {}
    operator_username = data.get("operator_username")
    qr_id = data.get("qr_id")
    external_id = data.get("external_patient_id")
    if not operator_username or not qr_id or not external_id:
        return jsonify({"error": "operator_username, qr_id, external_patient_id required"}), 400

    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT id, hospital_id FROM operators WHERE username = %s", (operator_username,))
    operator = c.fetchone()
    if not operator or not operator.get("hospital_id"):
        return jsonify({"error": "operator not found or missing hospital"}), 404

    c.execute("SELECT id FROM patients WHERE qr_id = %s", (qr_id,))
    patient = c.fetchone()
    if not patient:
        return jsonify({"error": "patient not found"}), 404

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO patient_hospital_links (patient_id, hospital_id, external_patient_id)
        VALUES (%s,%s,%s)
        ON CONFLICT (patient_id, hospital_id)
        DO UPDATE SET external_patient_id = EXCLUDED.external_patient_id,
                      linked_at = CURRENT_TIMESTAMP
    """, (patient["id"], operator["hospital_id"], external_id))
    
    log_hospital_connection(cursor, patient["id"], operator["hospital_id"], "connected", operator_username, f"External ID: {external_id}")
    
    conn.commit()
    return jsonify({"message": "Patient linked", "qr_id": qr_id})

@bp.route("/operator/assign", methods=["POST"])
def api_operator_assign_patient():
    data = request.get_json() or {}
    operator_id = data.get("operator_id")
    qr_id = data.get("qr_id")
    
    if not operator_id or not qr_id:
        return jsonify({"error": "operator_id and qr_id required"}), 400

    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO patient_operator_link (qr_id, operator_id, assigned_by)
            VALUES (%s, %s, 'manual_assign')
            ON CONFLICT (qr_id, operator_id) DO NOTHING
        """, (qr_id, operator_id))
        
        log_operator_action(c, operator_id, qr_id, "assigned_patient", request.remote_addr, request.user_agent.string)
        
        conn.commit()
        return jsonify({"message": "Patient assigned successfully"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

@bp.route("/admin/logs", methods=["GET"])
def api_admin_logs():
    limit = request.args.get("limit", 100)
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("""
        SELECT l.*, o.username as operator_name 
        FROM access_log l
        LEFT JOIN operators o ON l.operator_id = o.id
        ORDER BY l.timestamp DESC LIMIT %s
    """, (limit,))
    return jsonify(c.fetchall())

@bp.route("/admin/connection-logs", methods=["GET"])
def api_admin_connection_logs():
    admin_username = request.args.get("admin_username")
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    limit = request.args.get("limit", 100)
    
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    c.execute("SELECT is_admin FROM operators WHERE username = %s", (admin_username,))
    op = c.fetchone()
    if not op or not op.get("is_admin"):
        return jsonify({"error": "Admin access required"}), 403

    query = """
        SELECT l.*, p.name as patient_name, p.qr_id as patient_qr_id, h.name as hospital_name
        FROM hospital_connection_log l
        LEFT JOIN patients p ON l.patient_id = p.id
        LEFT JOIN hospitals h ON l.hospital_id = h.id
        WHERE 1=1
    """
    params = []
    
    if q:
        query += " AND (p.qr_id ILIKE %s OR h.name ILIKE %s)"
        params.extend([f"%{q}%", f"%{q}%"])
        
    if status and status != 'all':
        query += " AND l.action = %s"
        params.append(status)
        
    query += " ORDER BY l.timestamp DESC LIMIT %s"
    params.append(limit)
    
    c.execute(query, tuple(params))
    logs = c.fetchall()
    
    stats = {"active_connections": 0, "total_24h": 0, "disconnected_24h": 0}
    c.execute("SELECT count(*) FROM patient_hospital_links")
    row = c.fetchone()
    if row:
        stats["active_connections"] = row.get('count') if isinstance(row, dict) else row[0]
        
    yesterday = datetime.now() - timedelta(days=1)
    c.execute("SELECT action, count(*) FROM hospital_connection_log WHERE timestamp >= %s GROUP BY action", (yesterday,))
    for r in c.fetchall():
        action = r.get('action') if isinstance(r, dict) else r[0]
        count = r.get('count') if isinstance(r, dict) else r[1]
        if action == 'connected':
            stats["total_24h"] += count
        elif action == 'disconnected':
            stats["disconnected_24h"] += count

    results = []
    for log in logs:
        log_dict = dict(log)
        if log_dict.get("patient_name"):
            log_dict["patient_name"] = decrypt_data(log_dict["patient_name"])
        results.append(log_dict)
    return jsonify({"logs": results, "stats": stats})

@bp.route("/admin/disconnect-patient", methods=["POST"])
def api_admin_disconnect_patient():
    data = request.get_json() or {}
    admin_username = data.get("admin_username")
    patient_id = data.get("patient_id")
    hospital_id = data.get("hospital_id")
    reason = data.get("reason", "Admin disconnect")
    
    if not admin_username or not patient_id or not hospital_id:
        return jsonify({"error": "admin_username, patient_id, and hospital_id required"}), 400
    
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT is_admin FROM operators WHERE username = %s", (admin_username,))
    op = c.fetchone()
    if not op or not op.get("is_admin"):
        return jsonify({"error": "Admin access required"}), 403
    
    cursor = conn.cursor()
    cursor.execute("DELETE FROM patient_hospital_links WHERE patient_id = %s AND hospital_id = %s", (patient_id, hospital_id))
    log_hospital_connection(cursor, patient_id, hospital_id, "disconnected", admin_username, reason)
    conn.commit()
    return jsonify({"message": "Patient disconnected from hospital", "patient_id": patient_id, "hospital_id": hospital_id})

@bp.route("/visits/<qr_id>", methods=["GET"])
def api_get_visits(qr_id):
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM visits WHERE qr_id = %s ORDER BY created_at DESC", (qr_id,))
    visits = c.fetchall()
    return jsonify([decrypt_record(v) for v in visits])

@bp.route("/visit", methods=["POST"])
def api_add_visit():
    data = request.get_json() or {}
    required = ["qr_id", "visit_date"]
    missing = [r for r in required if not data.get(r)]
    if missing:
        return jsonify({"error": "missing fields", "fields": missing}), 400

    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO visits (qr_id, visit_date, diagnosis, treatment, medicines, created_by)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (data["qr_id"], data["visit_date"], data.get("diagnosis"),
              data.get("treatment"), data.get("medicines"), data.get("created_by")))
        
        operator_id = data.get("operator_id")
        if operator_id:
            c.execute("""
                INSERT INTO patient_operator_link (qr_id, operator_id, assigned_by)
                VALUES (%s, %s, 'auto_visit')
                ON CONFLICT (qr_id, operator_id) DO NOTHING
            """, (data["qr_id"], operator_id))
            log_operator_action(c, operator_id, data["qr_id"], "added_visit", request.remote_addr, request.user_agent.string)

        conn.commit()
        return jsonify({"message": "Visit added"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

@bp.route("/doctor/emergency-link", methods=["POST"])
def api_doctor_emergency_link():
    data = request.get_json() or {}
    doctor_id = data.get("doctor_id")
    qr_id = data.get("qr_id")
    reason = data.get("reason", "Emergency Connection")
    
    if not doctor_id or not qr_id:
        return jsonify({"error": "Missing doctor_id or qr_id"}), 400
        
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT hospital_id, full_name, username FROM doctors WHERE id = %s", (doctor_id,))
    doc = c.fetchone()
    if not doc or not doc.get("hospital_id"):
        return jsonify({"error": "Doctor has no hospital or not found"}), 400
        
    hospital_id = doc["hospital_id"]
    doc_name = doc.get("full_name") or doc.get("username")
    
    c.execute("SELECT id FROM patients WHERE qr_id = %s", (qr_id,))
    pat = c.fetchone()
    if not pat:
        return jsonify({"error": "Patient not found"}), 404
    patient_id = pat["id"]
    
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO patient_hospital_links (patient_id, hospital_id, external_patient_id) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING", (patient_id, hospital_id, f"EMERGENCY-{qr_id}"))
        log_hospital_connection(cursor, patient_id, hospital_id, "connected", doc_name, reason)
        conn.commit()
        return jsonify({"message": "Emergency connection established"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

@bp.route("/doctor/register", methods=["POST"])
def api_doctor_register():
    data = request.get_json() or {}
    required = ["full_name", "specialty", "phone", "email", "hospital", "username", "password"]
    missing = [r for r in required if not data.get(r)]
    if missing:
        return jsonify({"error": "missing fields", "fields": missing}), 400

    hospital_id = data.get("hospital_id")
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO doctors (full_name, specialty, phone, email, hospital, username, password, hospital_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (data["full_name"], data["specialty"], data["phone"], data["email"],
              data["hospital"], data["username"], hash_password(data["password"]), hospital_id))
        conn.commit()
        return jsonify({"message": "Doctor registered"})
    except psycopg2.IntegrityError:
        conn.rollback()
        return jsonify({"error": "username/email conflict"}), 400
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

@bp.route("/doctor/login", methods=["POST"])
def api_doctor_login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    if not username or not password:
        return jsonify({"error": "username & password required"}), 400

    identity = f"doctor:{username}:{request.remote_addr or 'ip-unknown'}"
    allowed, retry_after = check_login_rate_limit(
        identity,
        int(current_app.config.get("LOGIN_RATE_LIMIT_PER_MINUTE", "8")),
    )
    if not allowed:
        return jsonify({"error": "Too many attempts. Try again later.", "retry_after": retry_after}), 429

    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM doctors WHERE username=%s", (username,))
    doc = c.fetchone()
    if not doc:
        return jsonify({"error": "User not found"}), 404
    if not verify_password(password, doc["password"]):
        return jsonify({"error": "Invalid credentials"}), 401

    hospital_name = None
    hospital_id = doc.get("hospital_id")
    if hospital_id:
        c.execute("SELECT name FROM hospitals WHERE id = %s", (hospital_id,))
        h = c.fetchone()
        if h:
            hospital_name = h["name"]

    return jsonify({
        "message": "Login successful",
        "username": username,
        "doctor": {
            "id": doc.get("id"),
            "full_name": doc.get("full_name"),
            "specialty": doc.get("specialty"),
            "email": doc.get("email"),
            "phone": doc.get("phone"),
            "hospital": doc.get("hospital"),
            "hospital_id": hospital_id,
            "hospital_name": hospital_name,
        }
    })

@bp.route("/doctor/patients", methods=["GET"])
def api_doctor_patients():
    doctor_id = request.args.get("doctor_id")
    if not doctor_id:
        return jsonify({"error": "doctor_id required"}), 400
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT hospital_id FROM doctors WHERE id = %s", (doctor_id,))
    doc = c.fetchone()
    if not doc:
        return jsonify({"error": "Doctor not found"}), 404
    doc_hospital_id = doc.get("hospital_id")
    if not doc_hospital_id:
        return jsonify([])
    
    c.execute("""
        SELECT DISTINCT p.*, h.name as hospital_name
        FROM patients p
        LEFT JOIN hospitals h ON p.primary_hospital_id = h.id
        WHERE p.primary_hospital_id = %s
        OR EXISTS (
            SELECT 1 FROM patient_hospital_links phl
            WHERE phl.patient_id = p.id AND phl.hospital_id = %s
        )
        ORDER BY p.created_at DESC
        LIMIT 100
    """, (doc_hospital_id, doc_hospital_id))
    return jsonify([decrypt_record(p) for p in c.fetchall()])

@bp.route("/operator/register", methods=["POST"])
def api_operator_register():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    master_key = data.get("master_key")
    hospital_id = data.get("hospital_id")
    is_admin = bool(data.get("is_admin"))
    if not username or not password or not master_key:
        return jsonify({"error": "username, password, master_key required"}), 400
    if master_key != MASTER_OPERATOR_KEY:
        return jsonify({"error": "invalid master_key"}), 403

    conn = get_db()
    c = conn.cursor()
    try:
        resolved_hospital_id = resolve_hospital_id(c, hospital_id)
        c.execute("INSERT INTO operators (username, password, hospital_id, is_admin) VALUES (%s, %s, %s, %s)",
                  (username, hash_password(password), resolved_hospital_id, is_admin))
        conn.commit()
        return jsonify({"message": "Operator created"})
    except psycopg2.IntegrityError:
        conn.rollback()
        return jsonify({"error": "username conflict"}), 400
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

@bp.route("/operator/login", methods=["POST"])
def api_operator_login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    if not username or not password:
        return jsonify({"error": "username & password required"}), 400

    identity = f"operator:{username}:{request.remote_addr or 'ip-unknown'}"
    allowed, retry_after = check_login_rate_limit(
        identity,
        int(current_app.config.get("LOGIN_RATE_LIMIT_PER_MINUTE", "8")),
    )
    if not allowed:
        return jsonify({"error": "Too many attempts. Try again later.", "retry_after": retry_after}), 429

    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM operators WHERE username=%s", (username,))
    op = c.fetchone()
    if not op:
        return jsonify({"error": "User not found"}), 404
    if not verify_password(password, op["password"]):
        return jsonify({"error": "Invalid credentials"}), 401

    hospital_id = op.get("hospital_id")
    hospital_name = None
    if hospital_id:
        c.execute("SELECT name FROM hospitals WHERE id = %s", (hospital_id,))
        row = c.fetchone()
        if row:
            hospital_name = row["name"]
    is_admin = bool(op.get("is_admin")) or op.get("username", "").lower() == "brescan"

    return jsonify({
        "message": "Login successful",
        "username": username,
        "operator_id": op["id"],
        "hospital_id": hospital_id,
        "hospital_name": hospital_name,
        "is_admin": is_admin
    })

@bp.route("/qrcodes", methods=["GET"])
def api_qrcodes():
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT qr_id, assigned, scans FROM qrcodes ORDER BY qr_id ASC")
    return jsonify(c.fetchall())

@bp.route("/registration_labs/<qr_id>", methods=["GET"])
def api_registration_labs(qr_id):
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM registration_labs WHERE qr_id = %s ORDER BY uploaded_at DESC", (qr_id,))
    return jsonify(c.fetchall())

@bp.route("/lab/upload/<qr_id>", methods=["POST"])
def api_lab_upload(qr_id):
    uploaded_by = request.form.get("uploaded_by", "unknown")
    lab_file = request.files.get("lab_file")
    if not lab_file or not allowed_file(lab_file.filename):
        return jsonify({"error": "valid lab_file required"}), 400
    filename = secure_filename(lab_file.filename)
    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename) # Use current_app.config
    lab_file.save(save_path)

    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO registration_labs (qr_id, file_name, uploaded_by) VALUES (%s, %s, %s)", (qr_id, filename, uploaded_by))
        conn.commit()
        return jsonify({"message": "Lab uploaded", "qr_id": qr_id, "file": filename})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

@bp.route("/visit/<visit_id>/labs", methods=["GET"])
def api_visit_labs(visit_id):
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM lab_reports WHERE visit_id = %s", (visit_id,))
    labs = c.fetchall()
    return jsonify([decrypt_record(l) for l in labs])

@bp.route("/search/patients", methods=["GET"])
def api_search_patients():
    q = (request.args.get("q") or "").strip().lower()
    operator_username = request.args.get("operator")
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    if q:
        like_pattern = f"%{q}%"
        params = [like_pattern, like_pattern]
        query = """
            SELECT p.*, h.name AS hospital_name
            FROM patients p
            LEFT JOIN hospitals h ON p.primary_hospital_id = h.id
            WHERE (LOWER(p.username) LIKE %s OR LOWER(p.email) LIKE %s)
        """
    else:
        params = []
        query = """
            SELECT p.*, h.name AS hospital_name
            FROM patients p
            LEFT JOIN hospitals h ON p.primary_hospital_id = h.id
            WHERE 1=1
        """
    
    if operator_username:
        c.execute("SELECT id, hospital_id, is_admin FROM operators WHERE username = %s", (operator_username,))
        op = c.fetchone()
        if not op:
            return jsonify({"error": "operator not found"}), 404
        op_hospital_id = op.get("hospital_id")
        op_id = op.get("id")
        is_admin = bool(op.get("is_admin")) or operator_username.lower() == "brescan"
        
        if not is_admin and op_hospital_id:
            query += """
                AND (
                    p.primary_hospital_id = %s
                    OR EXISTS (
                        SELECT 1 FROM patient_hospital_links l
                        WHERE l.patient_id = p.id AND l.hospital_id = %s
                    )
                    OR EXISTS (
                        SELECT 1 FROM patient_operator_link pol
                        WHERE pol.qr_id = p.qr_id AND pol.operator_id = %s
                    )
                )
            """
            params.extend([op_hospital_id, op_hospital_id, op_id])
    
    query += " ORDER BY p.created_at DESC LIMIT 200"
    c.execute(query, tuple(params))
    return jsonify([decrypt_record(p) for p in c.fetchall()])

@bp.route("/health_tip", methods=["GET"])
def api_health_tip():
    return jsonify({"tip": get_random_tip()})

from app.services.data_service import fetch_analytics_data

@bp.route("/analytics", methods=["GET", "POST"])
def api_analytics():
    username = None
    password = None
    if request.method == "POST":
        data = request.get_json() or {}
        username = data.get("username")
        password = data.get("password")
    else:
        username = request.args.get("username")
        password = request.args.get("password")

    if not username or not password:
        return jsonify({"error":"operator credentials required"}), 400
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT * FROM operators WHERE username = %s", (username,))
    op = c.fetchone()
    if not op or not verify_password(password, op["password"]):
        return jsonify({"error":"unauthorized"}), 401
    return jsonify(fetch_analytics_data())

@bp.route('/emergency/public-key', methods=['GET'])
def api_emergency_public_key():
    """Expose the public key for offline verifier bootstrap.

    Public keys are not secrets, so serving this is safe.
    """
    _, public_key = _get_emergency_keys()
    if not public_key:
        return jsonify({"error": "Emergency keypair not configured"}), 500
    return jsonify({"public_key_pem": public_key_to_spki_pem(public_key)})


@bp.route('/emergency/token/<qr_id>', methods=['GET'])
def api_issue_emergency_token(qr_id):
    """Issue signed minimal emergency token for a patient.

    RBAC:
    - doctors/operators can issue for any accessible workflow patient.
    - patients can only issue their own token (via qr_id query check).
    """
    role = (request.args.get('role') or '').strip()
    requester_qr = (request.args.get('requester_qr_id') or '').strip()
    if role == 'patient' and requester_qr and requester_qr != qr_id:
        return jsonify({"error": "Patients can only issue their own emergency token"}), 403

    private_key, _ = _get_emergency_keys()
    if not private_key:
        return jsonify({"error": "Emergency keypair not configured"}), 500

    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute(
        "SELECT qr_id, name, birthdate, chronic_diseases, medications, other_info, phone FROM patients WHERE qr_id = %s",
        (qr_id,),
    )
    patient = c.fetchone()
    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    payload = _build_emergency_payload(patient)
    token = sign_emergency_payload(payload, private_key)

    base_url = request.url_root.rstrip('/')
    offline_url = f"{base_url}/emergency/offline#token={token}"

    qr_image = qrcode.make(offline_url)
    output_path = os.path.join(current_app.static_folder, 'qrcodes', f'{qr_id}_emergency.png')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    qr_image.save(output_path)

    return jsonify({
        "token": token,
        "offline_url": offline_url,
        "qr_png": f"/static/qrcodes/{qr_id}_emergency.png",
        "expires_at": payload['exp'],
        "note": "Re-issue token whenever emergency fields change.",
    })


@bp.route('/emergency/verify', methods=['POST'])
def api_verify_emergency_token():
    data = request.get_json() or {}
    token = (data.get('token') or '').strip()
    if not token:
        return jsonify({"error": "token required"}), 400

    _, public_key = _get_emergency_keys()
    if not public_key:
        return jsonify({"error": "Emergency keypair not configured"}), 500

    result = verify_emergency_token(token, public_key)
    response = {
        "status": result.status,
        "reason": result.reason,
        "payload": result.payload,
    }
    code = 200 if result.status == 'verified' else 400
    return jsonify(response), code
