from flask import Flask
from .config import Config

def create_app(config_class=Config):
    import os
    # Ensure simplified structure: app/templates and app/static
    base_dir = os.path.dirname(os.path.abspath(__file__))
    app = Flask(__name__, 
                template_folder=os.path.join(base_dir, "templates"),
                static_folder=os.path.join(base_dir, "static"))
    app.config.from_object(config_class)

    # Initialize DB
    from . import db
    db.init_app(app)

    # Register Blueprints
    from .api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    from .routes.common import common_bp
    app.register_blueprint(common_bp)
    
    from .routes.auth import auth_bp
    app.register_blueprint(auth_bp)
    
    from .routes.patient import patient_bp
    app.register_blueprint(patient_bp)
    
    from .routes.doctor import doctor_bp
    app.register_blueprint(doctor_bp)
    
    from .routes.operator import operator_bp
    app.register_blueprint(operator_bp)
    
    from .routes.admin import admin_bp
    app.register_blueprint(admin_bp)

    return app
