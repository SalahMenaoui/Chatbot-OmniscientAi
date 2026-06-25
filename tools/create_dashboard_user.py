"""Create a dashboard login. Usage: python tools/create_dashboard_user.py <client_key> <email> <password>"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import models, auth

if len(sys.argv) != 4:
    print("Usage: python tools/create_dashboard_user.py <client_key> <email> <password>")
    sys.exit(1)

_, client_key, email, password = sys.argv

models.init_db()
try:
    auth.create_dashboard_user(client_key, email, password)
    print(f"User '{email}' created for client '{client_key}'.")
except ValueError as e:
    print(f"Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
