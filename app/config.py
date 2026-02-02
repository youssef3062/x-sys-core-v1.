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
