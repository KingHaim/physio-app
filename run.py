# run.py
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app  # Changed from .app to app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
