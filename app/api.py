from flask import Blueprint, jsonify, current_app
import requests
from datetime import datetime, timedelta
from app.models import Treatment as Appointment, Patient
from app import db

api = Blueprint('api', __name__)

# Rest of your code remains the same 