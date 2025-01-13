import sqlite3
import os
from flask import g
from functools import wraps
import logging

logger = logging.getLogger(__name__)

# Define the database path
DATABASE = 'users.db'

def get_db_connection():
    """Create and return a new database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def close_db_connection(conn=None):
    """Close a specific database connection"""
    if conn is not None:
        conn.close()

def with_db_connection(func):
    """Decorator to handle database connections"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Create a new connection for this request
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        
        try:
            # Pass the connection as first argument
            result = func(conn, *args, **kwargs)
            conn.commit()  # Commit any changes
            return result
        except Exception as e:
            conn.rollback()  # Rollback on error
            logger.error(f"Database error in {func.__name__}: {str(e)}")
            raise
        finally:
            conn.close()  # Always close the connection
    return wrapper

def init_db():
    """Initialize the database with required tables"""
    try:
        conn = get_db_connection()
        # Create users table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        
        # Create user_profiles table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                given_name TEXT,
                last_name TEXT,
                mobile_number TEXT,
                email_address TEXT,
                address_line1 TEXT,
                address_line2 TEXT,
                address_line3 TEXT,
                address_line4 TEXT,
                city TEXT,
                state TEXT,
                country TEXT,
                post_code TEXT,
                date_of_birth TEXT,
                passport_number TEXT,
                gender TEXT,
                ethnicity TEXT,
                religion TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        # Create temp_form_data table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS temp_form_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                pdf_path TEXT,
                form_fields TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        conn.commit()
    finally:
        conn.close()

@with_db_connection
def get_all_users(conn):
    """Retrieve all users from the database"""
    try:
        users = conn.execute('''
            SELECT users.*, user_profiles.*
            FROM users
            LEFT JOIN user_profiles ON users.id = user_profiles.user_id
        ''').fetchall()
        return [dict(user) for user in users]
    except sqlite3.Error as e:
        logger.error(f"Error retrieving users: {e}")
        return []

@with_db_connection
def get_user_by_username(conn, username):
    """Retrieve a specific user by username"""
    try:
        user = conn.execute('''
            SELECT users.*, user_profiles.*
            FROM users
            LEFT JOIN user_profiles ON users.id = user_profiles.user_id
            WHERE users.username = ?
        ''', (username,)).fetchone()
        return dict(user) if user else None
    except sqlite3.Error as e:
        logger.error(f"Error retrieving user: {e}")
        return None

@with_db_connection
def count_users(conn):
    """Count total number of users in the database"""
    try:
        result = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()
        return result['count']
    except sqlite3.Error as e:
        logger.error(f"Error counting users: {e}")
        return 0