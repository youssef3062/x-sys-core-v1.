import os

class Config:
    SECRET_KEY = os.environ.get("BRESCAN_UI_SECRET", "dev-secret-key")
    # API base not needed if internal, but keeping for reference
    BRESCAN_API_BASE = os.environ.get("BRESCAN_API_BASE", "http://127.0.0.1:5000")
    
    # Paths
    APP_ROOT = os.path.dirname(os.path.abspath(__file__))
    STATIC_DIR = os.path.join(APP_ROOT, "static")
    PHOTOS_DIR = os.path.join(STATIC_DIR, "photos")
    LABS_DIR = os.path.join(STATIC_DIR, "labs")
    TMP_UPLOAD_FOLDER = os.path.join(APP_ROOT, "..", "tmp_uploads")
    
    # Database
    DATABASE_URL = os.environ.get("DATABASE_URL")
    
    if DATABASE_URL:
        # Parse the URL to get credentials (rudimentary parsing or just use the URL directly if using non-individual-field logic)
        # However, since the rest of the app might use 'dbname', 'user', etc in a dict, we might need to parse it.
        # Actually, let's keep it simple: If DATABASE_URL is present, we try to use it.
        # But wait, looking at lines 22-30, DB_CONFIG returns a dict. 
        # We need to parse the URL or change how DB_CONFIG is constructed.
        import urllib.parse
        url = urllib.parse.urlparse(DATABASE_URL)
        DB_NAME = url.path[1:]
        DB_USER = url.username
        DB_PASSWORD = url.password
        DB_HOST = url.hostname
        DB_PORT = url.port
    else:
        DB_NAME = os.environ.get("DB_NAME")
        DB_USER = os.environ.get("DB_USER")
        DB_PASSWORD = os.environ.get("DB_PASSWORD")
        DB_HOST = os.environ.get("DB_HOST")
        DB_PORT = os.environ.get("DB_PORT")

    @property
    def DB_CONFIG(self):
        return {
            "dbname": self.DB_NAME,
            "user": self.DB_USER,
            "password": self.DB_PASSWORD,
            "host": self.DB_HOST,
            "port": self.DB_PORT
        }

    ALLOWED_LAB_EXT = {"pdf", "doc", "docx", "txt", "csv", "xlsx"}
    ALLOWED_PHOTO_EXT = {"png", "jpg", "jpeg", "gif"}
