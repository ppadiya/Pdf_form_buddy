from flask import Flask
from database import get_all_users, get_user_by_username, count_users
from config import Config

# Create Flask app instance
app = Flask(__name__)
app.config.from_object(Config)

# Use application context
with app.app_context():
    # Get all users
    all_users = get_all_users()
    print("\nAll Users:")
    print(all_users)

    # Get a specific user
    user = get_user_by_username("johndoe")
    print("\nSpecific User:")
    print(user)

    # Count total users
    total_users = count_users()
    print(f"\nTotal number of users: {total_users}")