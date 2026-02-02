from app.services.api_client import safe_get, handle_api_response

def fetch_hospitals():
    """Fetch list of hospitals."""
    resp = safe_get("/api/hospitals")
    success, data = handle_api_response(resp)
    return data if success and isinstance(data, list) else []

def fetch_patient_from_api(qr_id: str, operator_id=None):
    """Fetch patient details."""
    if not qr_id:
        return False, "Missing QR ID"
    params = {}
    if operator_id:
        params["operator_id"] = operator_id
    resp = safe_get(f"/api/patient/{qr_id}", params=params)
    return handle_api_response(resp)

def fetch_visits_from_api(qr_id: str):
    """Fetch patient visits."""
    if not qr_id:
        return []
    resp = safe_get(f"/api/visits/{qr_id}")
    success, data = handle_api_response(resp)
    return data if success and isinstance(data, list) else []

def fetch_visit_labs_map(visits: list):
    """Fetch labs for each visit."""
    labs_map = {}
    for visit in visits or []:
        visit_id = visit.get("id")
        if not visit_id:
            continue
        resp = safe_get(f"/api/visit/{visit_id}/labs")
        success, data = handle_api_response(resp)
        if success and isinstance(data, list):
            labs_map[visit_id] = data
        else:
            labs_map[visit_id] = []
    return labs_map

from datetime import datetime, timedelta
import psycopg2.extras
from app.db import get_db
from app.utils import decrypt_record

def fetch_analytics_data():
    """Fetch analytics data directly from DB to avoid internal API auth issues."""
    conn = get_db()
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Basic Counts
    c.execute("SELECT COUNT(*) as total FROM patients")
    total_patients = c.fetchone()["total"]
    c.execute("SELECT COUNT(*) as total FROM visits")
    total_visits = c.fetchone()["total"]
    c.execute("SELECT SUM(scans) as total FROM qrcodes")
    total_scans = c.fetchone()["total"] or 0
    c.execute("SELECT COUNT(*) as total FROM operators")
    total_operators = c.fetchone()["total"]
    c.execute("SELECT COUNT(*) as total FROM doctors")
    total_doctors = c.fetchone()["total"]
    
    # Recent visits (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    c.execute("SELECT COUNT(*) as total FROM visits WHERE visit_date::date >= %s", (thirty_days_ago.date(),))
    recent_visits = c.fetchone()["total"]

    # Monthly Trends (last 6 months)
    c.execute("""
        SELECT TO_CHAR(visit_date::date, 'Mon') as month, COUNT(*) as count 
        FROM visits 
        WHERE visit_date::date >= %s 
        GROUP BY TO_CHAR(visit_date::date, 'Mon'), DATE_TRUNC('month', visit_date::date) 
        ORDER BY DATE_TRUNC('month', visit_date::date)
    """, (datetime.now() - timedelta(days=180),))
    monthly_trends = c.fetchall()

    # Gender Distribution
    c.execute("SELECT gender, COUNT(*) as count FROM patients GROUP BY gender")
    gender_distribution = c.fetchall()

    # Top Operators (by visits created)
    c.execute("""
        SELECT created_by as operator, COUNT(*) as visits 
        FROM visits 
        WHERE created_by IS NOT NULL 
        GROUP BY created_by 
        ORDER BY visits DESC 
        LIMIT 5
    """)
    top_operators_list = c.fetchall()

    # Recent Patients
    c.execute("""
        SELECT p.*, (SELECT COUNT(*) FROM visits v WHERE v.qr_id = p.qr_id) as visit_count
        FROM patients p 
        ORDER BY created_at DESC 
        LIMIT 5
    """)
    recent_patients_raw = c.fetchall()
    recent_patients = []
    for p in recent_patients_raw:
        p_dec = decrypt_record(p)
        recent_patients.append({
            "name": p_dec.get("name"),
            "qr_id": p_dec.get("qr_id"),
            "visits": p.get("visit_count", 0),
            "phone": p_dec.get("phone")
        })

    # Blood Type Distribution
    blood_type_distribution = []
    try:
        c.execute("SELECT blood_type as type, COUNT(*) as count FROM patients WHERE blood_type IS NOT NULL GROUP BY blood_type")
        blood_type_distribution = c.fetchall()
    except Exception:
        conn.rollback()

    # Top QR Codes
    c.execute("SELECT qr_id, scans FROM qrcodes ORDER BY scans DESC LIMIT 5")
    top_qr_codes = c.fetchall()

    # Weekly Activity (last 7 days)
    # Generate last 7 days list to ensure all days are present including zeros
    last_7_days = []
    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).date()
        last_7_days.append(day)
    
    c.execute("""
        SELECT visit_date::date as day, COUNT(*) as count 
        FROM visits 
        WHERE visit_date::date >= %s 
        GROUP BY visit_date::date
    """, (last_7_days[0],))
    weekly_data = {row['day']: row['count'] for row in c.fetchall()}
    
    weekly_activity = []
    for day in last_7_days:
        weekly_activity.append({
            "day": day.strftime("%Y-%m-%d"),
            "count": weekly_data.get(day, 0)
        })

    # Age Distribution
    c.execute("""
        SELECT birthdate FROM patients WHERE birthdate IS NOT NULL
    """)
    patients_birthdates = c.fetchall()
    
    age_buckets = {"0-18": 0, "19-30": 0, "31-50": 0, "51-70": 0, "70+": 0}
    for p in patients_birthdates:
        # p is RealDictRow, so we need to access 'birthdate' properly or if it's strings
        # Decrypt if necessary? p['birthdate'] is usually plain text date in this schema based on api_register
        # Actually api_register stores birthdate as-is (passed in query).
        bdate = p.get('birthdate')
        if bdate:
            try:
                # Calculate age
                dob = datetime.strptime(bdate, "%Y-%m-%d")
                today = datetime.today()
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                
                if age <= 18: age_buckets["0-18"] += 1
                elif age <= 30: age_buckets["19-30"] += 1
                elif age <= 50: age_buckets["31-50"] += 1
                elif age <= 70: age_buckets["51-70"] += 1
                else: age_buckets["70+"] += 1
            except (ValueError, TypeError):
                continue
                
    age_distribution = [{"age_group": k, "count": v} for k, v in age_buckets.items()]

    return {
        "total_patients": total_patients,
        "total_visits": total_visits,
        "total_scans": total_scans,
        "total_operators": total_operators,
        "total_doctors": total_doctors,
        "recent_visits": recent_visits,
        "monthly_trends": monthly_trends,
        "weekly_activity": weekly_activity,
        "gender_distribution": gender_distribution,
        "age_distribution": age_distribution,
        "top_operators": top_operators_list,
        "recent_patients": recent_patients,
        "blood_type_distribution": blood_type_distribution,
        "top_qr_codes": top_qr_codes
    }
