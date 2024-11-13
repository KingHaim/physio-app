# run.py
from app import create_app  # Changed from .app to app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)