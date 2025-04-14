#!/usr/bin/env python3
# This file contains the WSGI configuration required to serve up your
# web application at http://kinghaim.pythonanywhere.com/
# It works by setting the variable 'application' to a WSGI handler of some
# description.
#

import sys
import os
from dotenv import load_dotenv

# Add your project directory to the sys.path
path = '/home/kinghaim/physio-app'
if path not in sys.path:
    sys.path.append(path)

# Load environment variables from .env file
project_folder = os.path.expanduser(path)
load_dotenv(os.path.join(project_folder, '.env'))

# Import Flask app as the variable "application"
from run import app as application 