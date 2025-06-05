import click
from flask.cli import with_appcontext
from app.utils import mark_past_treatments_as_completed, mark_inactive_patients
from app.models import User, db
from datetime import datetime, timedelta, date, time

# Import models needed for the new command
from app.models import RecurringAppointment, Treatment, Patient
# Import the helper function from main routes
# from app.routes.main import generate_scheduled_treatments

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

    @click.command('create-user')
    @click.argument('username')
    @click.argument('email')
    @click.argument('password')
    @click.option('--admin', is_flag=True, help='Make the user an admin.')
    @with_appcontext
    def create_user_command(username, email, password, admin):
        """Create a new user."""
        if User.query.filter_by(username=username).first():
            click.echo(f'User {username} already exists.')
            return
        if User.query.filter_by(email=email).first():
            click.echo(f'Email {email} already registered.')
            return

        user = User(username=username, email=email, is_admin=admin)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f'User {username} created successfully. Admin: {admin}')

    @click.command('list-users')
    @with_appcontext
    def list_users_command():
        """List all users."""
        users = User.query.all()
        if not users:
            click.echo("No users found.")
            return
        click.echo("Users:")
        for user in users:
            admin_status = "(Admin)" if user.is_admin else ""
            click.echo(f"- ID: {user.id}, Username: {user.username}, Email: {user.email} {admin_status}")

    @click.command('generate-past-appointments')
    @with_appcontext
    def generate_past_appointments_command():
        """Generate Treatment records for past occurrences of recurring appointments."""
        click.echo("Starting generation of past appointments...")
        today = date.today()
        created_count = 0

        # Get all active recurring rules
        active_rules = RecurringAppointment.query.filter_by(is_active=True).all()
        click.echo(f"Found {len(active_rules)} active recurring rules.")

        for rule in active_rules:
            click.echo(f"Processing rule ID {rule.id} for Patient ID {rule.patient_id} ({rule.recurrence_type})...")
            start_date = rule.start_date
            end_date = rule.end_date or today # Use today if no end date
            current_date = start_date

            # Ensure we don't process dates after today or after the rule's end date
            effective_end_date = min(end_date, today)

            while current_date <= effective_end_date:
                occurrence_datetime = None
                is_valid_occurrence = False

                # Calculate occurrence based on recurrence type
                if rule.recurrence_type == 'weekly':
                    # Check if the current day matches the start day's weekday
                    if current_date.weekday() == start_date.weekday():
                        is_valid_occurrence = True
                elif rule.recurrence_type == 'daily-mon-fri':
                    # Check if the current day is Monday (0) to Friday (4)
                    if current_date.weekday() < 5:
                        is_valid_occurrence = True
                # Add other recurrence types here if needed

                if is_valid_occurrence:
                    # Combine date with the rule's time_of_day
                    occurrence_datetime = datetime.combine(current_date, rule.time_of_day)

                    # Check if a treatment already exists for this exact datetime and patient
                    exists = Treatment.query.filter_by(
                        patient_id=rule.patient_id,
                        created_at=occurrence_datetime
                    ).first()

                    if not exists:
                        # Create the new treatment record
                        new_treatment = Treatment(
                            patient_id=rule.patient_id,
                            treatment_type=rule.treatment_type,
                            notes=rule.notes,
                            status='Completed', # Past appointments are marked completed
                            provider=rule.provider,
                            created_at=occurrence_datetime, # Set the actual past date/time
                            updated_at=datetime.now(), # Mark when this record was generated
                            location=rule.location,
                            fee_charged=rule.fee_charged,
                            payment_method=rule.payment_method
                            # Set other fields from the rule as needed
                        )
                        db.session.add(new_treatment)
                        created_count += 1
                        # click.echo(f"  -> Created treatment for {occurrence_datetime.strftime('%Y-%m-%d %H:%M')}") # Optional: verbose output
                    # else: 
                        # click.echo(f"  -> Treatment already exists for {occurrence_datetime.strftime('%Y-%m-%d %H:%M')}") # Optional: verbose output

                # Move to the next day
                current_date += timedelta(days=1)

        try:
            db.session.commit()
            click.echo(f"Successfully generated {created_count} past treatment records.")
        except Exception as e:
            db.session.rollback()
            click.echo(f"Error committing changes: {e}")
            click.echo("Database rolled back.")

    # @app.cli.command('generate-recurring')
    # @with_appcontext
    # def generate_recurring_command():
    #     """Generate scheduled Treatment records from recurring rules."""
    #     click.echo("Generating treatments from recurring rules...")
    #     count = generate_scheduled_treatments() # Call the helper function
    #     if count >= 0:
    #         click.echo(f"Finished generating {count} treatments.")
    #     else:
    #         click.echo("An error occurred during generation.")

    app.cli.add_command(create_admin)
    app.cli.add_command(create_user_command)
    app.cli.add_command(list_users_command)
    app.cli.add_command(generate_past_appointments_command)
    # app.cli.add_command(generate_recurring_command) 