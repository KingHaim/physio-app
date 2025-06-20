# tests/test_db_schema.py
from app import db, app
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

def test_database_connection():
    with app.app_context():
        try:
            db.session.execute(text("SELECT 1"))
            assert True
        except SQLAlchemyError:
            assert False, "Database connection failed" 