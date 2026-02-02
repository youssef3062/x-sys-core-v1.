import psycopg2
from flask import g, current_app

def get_db():
    if 'db' not in g:
        g.db = psycopg2.connect(
            dbname=current_app.config['DB_NAME'],
            user=current_app.config['DB_USER'],
            password=current_app.config['DB_PASSWORD'],
            host=current_app.config['DB_HOST'],
            port=current_app.config['DB_PORT']
        )
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_app(app):
    app.teardown_appcontext(close_db)

def init_db_command():
    """Clear the existing data and create new tables."""
    from app.config import Config
    import psycopg2
    
    conf = Config()
    conn = psycopg2.connect(**conf.DB_CONFIG)
    c = conn.cursor()
    
    schema = [
        '''CREATE TABLE IF NOT EXISTS qrcodes (
            qr_id TEXT PRIMARY KEY,
            assigned INTEGER DEFAULT 0,
            scans INTEGER DEFAULT 0
        );''',
        '''CREATE TABLE IF NOT EXISTS patients (
            id SERIAL PRIMARY KEY,
            qr_id TEXT UNIQUE,
            username TEXT UNIQUE,
            password TEXT,
            name TEXT,
            phone TEXT,
            email TEXT,
            birthdate TEXT,
            gender TEXT,
            blood_type TEXT,
            monthly_pills INTEGER,
            medications TEXT,
            chronic_diseases TEXT,
            lab_file TEXT,
            patient_photo TEXT,
            emergency_contact TEXT,
            other_info TEXT
        );''',
        '''CREATE TABLE IF NOT EXISTS operators (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT
        );''',
        '''CREATE TABLE IF NOT EXISTS scans (
            id SERIAL PRIMARY KEY,
            qr_id TEXT,
            scanned_by TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );''',
        '''CREATE TABLE IF NOT EXISTS visits (
            id SERIAL PRIMARY KEY,
            qr_id TEXT,
            visit_date TEXT,
            diagnosis TEXT,
            treatment TEXT,
            medicines TEXT,
            lab_file TEXT,
            created_by TEXT
        );''',
        '''CREATE TABLE IF NOT EXISTS lab_reports (
            id SERIAL PRIMARY KEY,
            visit_id INTEGER REFERENCES visits(id) ON DELETE CASCADE,
            file_name TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );''',
        '''CREATE TABLE IF NOT EXISTS registration_labs (
            id SERIAL PRIMARY KEY,
            qr_id TEXT NOT NULL REFERENCES patients(qr_id) ON DELETE CASCADE,
            file_name TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            uploaded_by TEXT DEFAULT 'patient'
        );''',
        '''CREATE TABLE IF NOT EXISTS doctors (
            id SERIAL PRIMARY KEY,
            full_name TEXT NOT NULL,
            specialty TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            hospital TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );''',
        '''CREATE TABLE IF NOT EXISTS patient_operator_link (
            id SERIAL PRIMARY KEY,
            qr_id TEXT NOT NULL,
            operator_id INTEGER NOT NULL REFERENCES operators(id) ON DELETE CASCADE,
            assigned_by TEXT,
            assigned_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(qr_id, operator_id) 
        );''',
        '''CREATE TABLE IF NOT EXISTS access_log (
            id SERIAL PRIMARY KEY,
            operator_id INTEGER,
            qr_id TEXT,
            action TEXT, 
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            device_info TEXT
        );'''
    ]
    
    for statement in schema:
        c.execute(statement)
        
    conn.commit()
    conn.close()
    print("Initialized the database.")
