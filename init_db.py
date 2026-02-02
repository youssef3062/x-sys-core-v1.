from app.db import init_db_command
from app import create_app

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        pass

    init_db_command()
