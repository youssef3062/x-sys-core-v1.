# generate_qrs.py
import qrcode
from dotenv import load_dotenv

load_dotenv()
import psycopg2
import psycopg2.extras
import os
import re

DB_CONFIG = {
    "dbname": os.environ.get("DB_NAME"),
    "user": os.environ.get("DB_USER"),
    "password": os.environ.get("DB_PASSWORD"),
    "host": os.environ.get("DB_HOST"),
    "port": os.environ.get("DB_PORT")
}

OUT = os.path.join("static", "qrcodes")
os.makedirs(OUT, exist_ok=True)

def extract_number(qr_id, prefix):
    m = re.match(rf"{re.escape(prefix)}-(\d+)$", qr_id)
    return int(m.group(1)) if m else 0

def generate(n=10, prefix="BRESCAN"):
    conn = psycopg2.connect(**DB_CONFIG)
    c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    c.execute("SELECT qr_id FROM qrcodes WHERE qr_id LIKE %s", (f"{prefix}-%",))
    rows = c.fetchall()
    max_idx = 0
    for row in rows:
        idx = extract_number(row["qr_id"], prefix)
        if idx > max_idx:
            max_idx = idx

    start = max_idx + 1
    for i in range(start, start + n):
        qr_id = f"{prefix}-{i:04d}"
        fname = f"{qr_id}.png"
        path = os.path.join(OUT, fname)
        # avoid overwrite: if file exists append suffix
        if os.path.exists(path):
            # create unique name (shouldn't happen due to numbering)
            base, ext = os.path.splitext(fname)
            j = 1
            while os.path.exists(os.path.join(OUT, f"{base}_{j}{ext}")):
                j += 1
            path = os.path.join(OUT, f"{base}_{j}{ext}")

        img = qrcode.make(qr_id,)
        img.save(path)
        c.execute("INSERT INTO qrcodes (qr_id, assigned) VALUES (%s, 0) ON CONFLICT (qr_id,) DO NOTHING", (qr_id,)
)
        print("->", qr_id)
    conn.commit()
    conn.close()
    print(f"✅ Generated {n} QR codes starting from {start}")

if __name__ == "__main__":
    generate(10)
