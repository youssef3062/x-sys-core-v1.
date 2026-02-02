from app.db import get_db

def _get_val(row, key, index):
    """Helper to get value from row whether it's dict or tuple"""
    if row is None:
        return None
    try:
        if isinstance(row, dict):
            return row[key]
        return row[index]
    except (KeyError, IndexError):
        return None

def check_operator_access(cursor, operator_id, qr_id):
    """
    Returns True if operator allowed to access patient.
    Expects cursor to be passed in.
    """
    try:
        # Check if admin
        cursor.execute("SELECT is_admin, hospital_id FROM operators WHERE id = %s", (operator_id,))
        op = cursor.fetchone()
        if not op:
            return False
        
        is_admin = _get_val(op, "is_admin", 0)
        op_hospital_id = _get_val(op, "hospital_id", 1)
        
        if is_admin:
            return True

        # Check manual link
        cursor.execute("SELECT 1 FROM patient_operator_link WHERE operator_id=%s AND qr_id=%s", (operator_id, qr_id))
        if cursor.fetchone():
            return True

        # Check Hospital Match
        if op_hospital_id:
            # Check if patient's primary hospital matches
            cursor.execute("SELECT primary_hospital_id FROM patients WHERE qr_id=%s", (qr_id,))
            pat = cursor.fetchone()
            if pat:
                primary_hospital_id = _get_val(pat, "primary_hospital_id", 0)
                if primary_hospital_id == op_hospital_id:
                    return True
            
            # Check if patient linked to this hospital
            cursor.execute("SELECT id FROM patients WHERE qr_id=%s", (qr_id,))
            pat_row = cursor.fetchone()
            if pat_row:
                patient_id = _get_val(pat_row, "id", 0)
                cursor.execute("SELECT 1 FROM patient_hospital_links WHERE patient_id=%s AND hospital_id=%s", (patient_id, op_hospital_id))
                if cursor.fetchone():
                    return True

        return False
    except Exception as e:
        print(f"Error in check_operator_access: {e}")
        return False

def check_doctor_access(cursor, doctor_id, qr_id):
    """
    Returns True if doctor allowed to access patient.
    """
    try:
        # Get doctor's hospital_id
        cursor.execute("SELECT hospital_id FROM doctors WHERE id = %s", (doctor_id,))
        doc = cursor.fetchone()
        if not doc:
            return False
        
        doc_hospital_id = _get_val(doc, "hospital_id", 0)
        
        # If doctor has no hospital (independent/Other), allow access (or maybe logic should be different, but keeping as is)
        if not doc_hospital_id:
            return True
        
        # Check if patient's primary hospital matches
        cursor.execute("SELECT id, primary_hospital_id FROM patients WHERE qr_id=%s", (qr_id,))
        pat = cursor.fetchone()
        if not pat:
            return False
        
        patient_id = _get_val(pat, "id", 0)
        primary_hospital_id = _get_val(pat, "primary_hospital_id", 1)
        
        if primary_hospital_id == doc_hospital_id:
            return True
        
        # Check if patient linked to doctor's hospital
        cursor.execute("SELECT 1 FROM patient_hospital_links WHERE patient_id=%s AND hospital_id=%s", (patient_id, doc_hospital_id))
        if cursor.fetchone():
            return True
        
        return False
    except Exception as e:
        print(f"Error in check_doctor_access: {e}")
        return False

def log_operator_action(cursor, operator_id, qr_id, action, ip_address=None, device_info=None):
    """Log operator action. Expects cursor."""
    try:
        cursor.execute("""
            INSERT INTO access_log (operator_id, qr_id, action, ip_address, device_info)
            VALUES (%s, %s, %s, %s, %s)
        """, (operator_id, qr_id, action, ip_address, device_info))
        # No commit here, caller handles it
    except Exception as e:
        print(f"Logging failed: {e}")

def log_hospital_connection(cursor, patient_id, hospital_id, action, performed_by, notes=None):
    """Log hospital connection. Expects cursor."""
    try:
        cursor.execute("""
            INSERT INTO hospital_connection_log (patient_id, hospital_id, action, performed_by, notes)
            VALUES (%s, %s, %s, %s, %s)
        """, (patient_id, hospital_id, action, performed_by, notes))
        # No commit here
    except Exception as e:
        print(f"Hospital connection logging failed: {e}")
