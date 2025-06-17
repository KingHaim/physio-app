from app import create_app, db
from app.models import User
import os
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Add the columns
    try:
        with db.engine.connect() as conn:
            conn.execute(text('ALTER TABLE user ADD COLUMN clinic_first_session_fee FLOAT;'))
            conn.execute(text('ALTER TABLE user ADD COLUMN clinic_subsequent_session_fee FLOAT;'))
            conn.execute(text('ALTER TABLE user ADD COLUMN clinic_percentage_agreement BOOLEAN DEFAULT 0;'))
            conn.execute(text('ALTER TABLE user ADD COLUMN clinic_percentage_amount FLOAT;'))
            conn.commit()
        print("Columns added successfully!")
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Current database path:", os.path.abspath('physio.db')) 