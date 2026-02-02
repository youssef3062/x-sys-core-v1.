import os
from datetime import datetime
from cryptography.fernet import Fernet
from flask import current_app

ENCRYPTION_KEY = os.getenv("BRESCAN_ENCRYPTION_KEY") or os.getenv("BRESCAN_STARTUP_@@$$")

if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = "x" * 4 

if not ENCRYPTION_KEY.endswith("="):
     # Attempt to pad if it looks like a truncated base64 string
    pad = (4 - len(ENCRYPTION_KEY) % 4) % 4
    if pad != 4:
        ENCRYPTION_KEY += "=" * pad

try:
    fernet = Fernet(ENCRYPTION_KEY.encode())
except Exception:
    fernet = None
    print("\n" + "!" * 50)
    print("WARNING: Encryption key invalid, encryption will fail.")
    print("To fix, add this to your .env file:")
    print(f"BRESCAN_ENCRYPTION_KEY={Fernet.generate_key().decode()}")
    print("!" * 50 + "\n")

def encrypt_data(value):
    if value is None or fernet is None:
        return None
    if isinstance(value, (int, float)):
        value = str(value)
    return fernet.encrypt(value.encode()).decode()

def decrypt_data(value):
    if not value or fernet is None:
        return value
    try:
        return fernet.decrypt(value.encode()).decode()
    except Exception:
        return value

def decrypt_record(record):
    if not record:
        return record
    return {k: decrypt_data(v) if isinstance(v, str) else v for k, v in record.items()}

def calculate_age(birthdate_str):
    if not birthdate_str:
        return None
    try:
        b = datetime.strptime(birthdate_str, "%Y-%m-%d")
        t = datetime.today()
        return t.year - b.year - ((t.month, t.day) < (b.month, b.day))
    except Exception:
        return None

def allowed_lab_file(filename):
    allowed_ext = current_app.config.get("ALLOWED_LAB_EXT", {"pdf", "doc", "docx", "txt", "csv", "xlsx"})
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_ext

def allowed_file(filename):
    return allowed_lab_file(filename)

def allowed_photo_file(filename):
    allowed_ext = current_app.config.get("ALLOWED_PHOTO_EXT", {"png", "jpg", "jpeg", "gif"})
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_ext
