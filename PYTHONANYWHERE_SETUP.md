# Deploying PhysioApp to PythonAnywhere

This guide will help you deploy PhysioApp to PythonAnywhere.

## Prerequisites

1. A PythonAnywhere account (Free tier works, but a paid account is recommended for a production app)
2. Your PhysioApp GitHub repository

## Deployment Steps

### 1. Set Up a Web App on PythonAnywhere

1. Log in to your PythonAnywhere account
2. Go to the Dashboard and click on "Web" tab
3. Click "Add a new web app"
4. Select "Manual configuration"
5. Choose Python 3.9 or newer
6. Click Next

### 2. Clone the Repository

1. Open a Bash console from the PythonAnywhere dashboard
2. Clone your GitHub repository:
   ```
   git clone https://github.com/kinghaim/physio-app.git
   ```
   (Replace with your actual GitHub repository URL)

### 3. Set Up a Virtual Environment

1. Create a virtual environment:
   ```
   cd physio-app
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

### 4. Configure Environment Variables

1. Create a `.env` file in your project directory:
   ```
   nano .env
   ```
2. Add your environment variables:
   ```
   CALENDLY_API_TOKEN=your_calendly_api_token_here
   DEEPSEEK_API_KEY=your_deepseek_api_key_here
   DEEPSEEK_API_ENDPOINT=https://api.deepseek.com/v1/chat/completions
   SECRET_KEY=your_flask_secret_key_here
   ```
3. Save and exit (Ctrl+X, then Y, then Enter)

### 5. Configure the Web App

1. Go back to the "Web" tab in the PythonAnywhere dashboard
2. In the "Code" section:

   - Set "Source code" to `/home/kinghaim/physio-app`
   - Set "Working directory" to `/home/kinghaim/physio-app`
   - Set "WSGI configuration file" to the default path PythonAnywhere provides

3. Edit the WSGI configuration file by clicking the link, and replace its contents with:

   ```python
   import sys
   import os
   from dotenv import load_dotenv

   # Add your project directory to the path
   path = '/home/kinghaim/physio-app'
   if path not in sys.path:
       sys.path.append(path)

   # Load environment variables
   project_folder = os.path.expanduser(path)
   load_dotenv(os.path.join(project_folder, '.env'))

   # Import your app
   from run import app as application
   ```

   (Replace `yourusername` with your actual PythonAnywhere username)

4. In the "Virtualenv" section:
   - Set it to `/home/kinghaim/physio-app/venv`

### 6. Initialize the Database

1. Open a Bash console
2. Navigate to your project directory:
   ```
   cd physio-app
   ```
3. Activate the virtual environment:
   ```
   source venv/bin/activate
   ```
4. Initialize the database:
   ```
   python init_db.py
   ```
5. Create an admin user:
   ```
   python add_admin_user.py
   ```

### 7. Restart the Web App

1. Go back to the "Web" tab
2. Click the "Reload" button for your web app

### 8. Visit Your Website

Your application should now be running at:

```
https://yourusername.pythonanywhere.com
```

## Troubleshooting

If your app doesn't work:

1. Check the error logs in the "Web" tab
2. Ensure all environment variables are set correctly
3. Verify the database has been initialized properly
4. Make sure all dependencies are installed in your virtual environment

## Updating Your Application

To update your application after pushing changes to GitHub:

1. Open a Bash console
2. Navigate to your project directory
3. Pull the latest changes:
   ```
   cd ~/physio-app
   git pull
   ```
4. Reload your web app from the "Web" tab
