# manage.py
from flask.cli import FlaskGroup
from .app import create_app, db
from app.models import Patient, Treatment, TriggerPoint  # Import your models

cli = FlaskGroup(create_app=create_app)

@cli.command("create_db")
def create_db():
    db.drop_all()
    db.create_all()
    db.session.commit()
    print("Database created successfully!")

@cli.command("seed_db")
def seed_db():
    # Add any initial data you want
    # For example:
    # patient = Patient(name="Test Patient", ...)
    # db.session.add(patient)
    db.session.commit()
    print("Database seeded!")

if __name__ == "__main__":
    cli()