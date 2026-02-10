# generate_qrs.py
import qrcode
import psycopg2
import psycopg2.extras
import os
import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
DB_CONFIG = {
    "dbname": os.environ.get("DB_NAME"),
    "user": os.environ.get("DB_USER"),
    "password": os.environ.get("DB_PASSWORD"),
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": os.environ.get("DB_PORT", 5432)
}

# Determine base paths
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "app" / "static" / "qrcodes"

def get_db_connection():
    """Establishes and returns a database connection."""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

def get_next_sequence(conn, prefix):
    """Finds the next available sequence number for the given prefix."""
    with conn.cursor() as cur:
        query = "SELECT qr_id FROM qrcodes WHERE qr_id LIKE %s"
        cur.execute(query, (f"{prefix}-%",))
        rows = cur.fetchall()
    
    max_idx = 0
    # Logic: Extract numbers from "PREFIX-XXXX"
    # This assumes standard formatting; robust enough for controlled generation
    for (qr_id,) in rows:
        parts = qr_id.split('-')
        if len(parts) >= 2 and parts[-1].isdigit():
            idx = int(parts[-1])
            if idx > max_idx:
                max_idx = idx
    return max_idx + 1

def generate_codes(count, prefix, dry_run=False):
    """Generates QR codes and database entries."""
    if not STATIC_DIR.exists():
        STATIC_DIR.mkdir(parents=True, exist_ok=True)
        print(f"📁 Created directory: {STATIC_DIR}")

    conn = get_db_connection()
    
    try:
        start_seq = get_next_sequence(conn, prefix)
        print(f"ℹ️  Generating {count} codes starting from {prefix}-{start_seq:04d}...")

        with conn.cursor() as cur:
            generated = 0
            for i in range(count):
                seq = start_seq + i
                qr_id = f"{prefix}-{seq:04d}"
                
                # 1. Generate Image
                img_path = STATIC_DIR / f"{qr_id}.png"
                
                if dry_run:
                    print(f"[DRY RUN] Would generate {qr_id} at {img_path}")
                    continue

                if img_path.exists():
                    print(f"⚠️  Skipping {qr_id}: File already exists.")
                    continue

                img = qrcode.make(qr_id)
                img.save(img_path)

                # 2. Insert into DB
                try:
                    cur.execute(
                        "INSERT INTO qrcodes (qr_id, assigned) VALUES (%s, 0) ON CONFLICT (qr_id) DO NOTHING",
                        (qr_id,)
                    )
                    generated += 1
                    print(f"✅ Generated: {qr_id}")
                except Exception as db_err:
                    print(f"❌ Failed to register {qr_id}: {db_err}")

            if not dry_run:
                conn.commit()
                print(f"\n🎉 Successfully generated {generated} new QR codes in '{STATIC_DIR}'.")
            else:
                print("\nℹ️  Dry run completed. No changes made.")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error during generation: {e}")
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="Batch generate QR codes for Brescan.")
    parser.add_argument("-n", "--number", type=int, default=10, help="Number of QR codes to generate (default: 10)")
    parser.add_argument("-p", "--prefix", type=str, default="BRESCAN", help="Prefix for QR IDs (default: BRESCAN)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate generation without writing files or DB")

    args = parser.parse_args()

    generate_codes(args.number, args.prefix, args.dry_run)

if __name__ == "__main__":
    main()
