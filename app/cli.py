import click
from flask.cli import with_appcontext
from app.utils import mark_past_treatments_as_completed, mark_inactive_patients
from app.models import User, db

def register_commands(app):
    @app.cli.command('update-treatment-statuses')
    @with_appcontext
    def update_treatment_statuses():
        """Update treatment statuses (mark past treatments as completed)."""
        count = mark_past_treatments_as_completed()
        click.echo(f"Marked {count} past treatments as completed.")
    
    @app.cli.command('update-patient-statuses')
    @with_appcontext
    def update_patient_statuses():
        """Update patient statuses (mark inactive patients)."""
        count = mark_inactive_patients()
        click.echo(f"Marked {count} patients as inactive.")
    
    @app.cli.command('maintenance')
    @with_appcontext
    def run_maintenance():
        """Run all maintenance tasks."""
        treatment_count = mark_past_treatments_as_completed()
        patient_count = mark_inactive_patients()
        click.echo(f"Maintenance complete: {treatment_count} treatments updated, {patient_count} patients marked inactive.")

    @click.command('create-admin')
    @click.argument('username')
    @click.argument('email')
    @click.argument('password')
    @with_appcontext
    def create_admin(username, email, password):
        """Create an admin user."""
        user = User(username=username, email=email, is_admin=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f'Admin user {username} created successfully.')

    app.cli.add_command(create_admin) 