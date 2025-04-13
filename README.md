# PhysioApp - Physiotherapy Practice Management System

PhysioApp is a comprehensive web application designed to help physiotherapists manage patient records, treatment sessions, appointments, and generate AI-powered clinical reports.

## Features

- **Patient Management**: Create, view, and update patient records
- **Treatment Tracking**: Record detailed treatment sessions with progress notes
- **Trigger Point Mapping**: Visual representation of trigger points on body charts
- **Appointment Scheduling**: Manage and track patient appointments
- **Calendly Integration**: Sync with Calendly for online appointment booking
- **AI Reports**: Generate comprehensive physiotherapy reports using DeepSeek AI
- **Analytics Dashboard**: Track treatment outcomes and clinic performance

## Installation

### Prerequisites

- Python 3.7 or higher
- SQLite database
- DeepSeek API key (for AI report generation)

### Setup

1. Clone the repository:

```bash
git clone https://github.com/yourusername/physio-app.git
cd physio-app
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure the application:

```bash
# Create a .env file with your configuration
touch .env
# Add your settings to .env
# Example:
# SECRET_KEY=your-secret-key
# CALENDLY_API_TOKEN=your-calendly-token
# DEEPSEEK_API_KEY=your-deepseek-api-key
```

5. Initialize the database:

```bash
flask db init
flask db migrate
flask db upgrade
```

6. Create an admin user:

```bash
python add_admin_user.py
```

## Running the Application

### Standard Method

```bash
flask run
```

### With DeepSeek API Integration

To run the application with the DeepSeek API for AI-powered physiotherapy reports:

```bash
./run_flask_with_api.sh
```

## DeepSeek API Integration

PhysioApp uses the DeepSeek AI API to generate comprehensive physiotherapy treatment reports. For detailed setup and usage instructions, see [DEEPSEEK_INTEGRATION.md](DEEPSEEK_INTEGRATION.md).

### Quick Tools

- `test_deepseek_api.py`: Test your DeepSeek API connection
- `update_deepseek_integration.py`: Configure the DeepSeek API integration
- `generate_patient_report.py`: Generate reports via command line
- `run_flask_with_api.sh`: Run Flask with API integration

## Usage Guide

### Patient Management

1. Create a new patient record with diagnosis and treatment plan
2. View patient details and treatment history
3. Generate AI reports based on treatment data

### Treatment Sessions

1. Record new treatment sessions with detailed notes
2. Track pain levels and movement restrictions
3. Map trigger points on the body chart

### Reports

1. Generate AI-powered physiotherapy reports
2. View and print treatment reports
3. Export reports as PDF documents

## Troubleshooting

See the [DEEPSEEK_INTEGRATION.md](DEEPSEEK_INTEGRATION.md) file for detailed troubleshooting steps for the AI report generation.

For general application issues:

1. Check that all dependencies are installed
2. Verify that the database is correctly initialized
3. Ensure environment variables are correctly set

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- DeepSeek AI for the report generation API
- Calendly for the appointment scheduling integration
