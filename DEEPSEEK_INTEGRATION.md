# DeepSeek API Integration for Physiotherapy Reports

This guide explains how to set up and use the DeepSeek API integration for generating AI-powered physiotherapy reports in the PhysioApp.

## Prerequisites

1. A valid DeepSeek API key (starts with `sk-`)
2. Python 3.6 or later with pip
3. Required Python packages: `requests`, `python-dotenv`

## Setup

### 1. Install Required Packages

```bash
pip install python-dotenv requests
```

### 2. Configure API Key

There are several ways to set up your DeepSeek API key:

**Option 1:** Add it to the `.env` file:

```bash
echo "DEEPSEEK_API_KEY=your-api-key-here" > .env
```

**Option 2:** Use the update script:

```bash
./update_deepseek_integration.py
```

This script will:

- Test your API key against multiple DeepSeek endpoints
- Find a working endpoint
- Update your `.env` file
- Create a helper script for running the app

### 3. Test Your API Key

Run the testing script to verify your API key works:

```bash
./test_deepseek_api.py
```

If successful, this script will create a `working_endpoint.txt` file that helps the application find the working API endpoint.

## Usage

### Option 1: Run the Flask App with API Integration

```bash
./run_flask_with_api.sh
```

This script will:

1. Load environment variables from .env file
2. Test the DeepSeek API connection
3. Set the working endpoint
4. Start the Flask server with the API key

### Option 2: Generate Reports from the Command Line

To generate a report for a specific patient directly:

```bash
./generate_patient_report.py <patient_id>
```

For example:

```bash
./generate_patient_report.py 8
```

This will:

1. Retrieve the patient's treatment history
2. Format it for the DeepSeek API
3. Generate a comprehensive physiotherapy report
4. Save it to the database and as a local file

## Troubleshooting

If you encounter issues with the API integration:

1. **Authentication Errors:**

   - Check that your API key is valid and correctly formatted
   - The key should start with `sk-` and have no spaces or extra characters

2. **Connection Issues:**

   - Run `./test_deepseek_api.py` to check if your API key works
   - Try running `./update_deepseek_integration.py` to test multiple endpoints

3. **Invalid Responses:**
   - Check if you have remaining credits in your DeepSeek account
   - Verify that you're using a supported DeepSeek model

## Application Features

The DeepSeek integration enables:

1. **Comprehensive Reports:** Generate detailed physiotherapy progress reports based on treatment history
2. **Clinical Assessment:** AI analysis of pain levels, movement restrictions, and treatment progress
3. **Treatment Recommendations:** Suggestions for further treatment and home exercises
4. **Professional Format:** Reports are formatted with markdown for readability and professional presentation

## Files

- `test_deepseek_api.py`: Tests the DeepSeek API connection
- `update_deepseek_integration.py`: Updates the API integration configuration
- `generate_patient_report.py`: Command-line tool for generating reports
- `run_flask_with_api.sh`: Runs the Flask app with API integration
- `working_endpoint.txt`: Contains the working DeepSeek API endpoint

---

For more information, contact support or refer to the DeepSeek API documentation.
