import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import pycountry
from database import (
    init_db, 
    get_db_connection, 
    with_db_connection, 
    close_db_connection
)
from config import Config
from flask_wtf.csrf import CSRFProtect, CSRFError, generate_csrf
import logging
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, FileField
from wtforms.validators import DataRequired, Length
from werkzeug.utils import secure_filename
from pdf_processor import PDFProcessor

app = Flask(__name__)
app.config.from_object(Config)

# Initialize CSRF protection
csrf = CSRFProtect()
csrf.init_app(app)

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize PDF processor
pdf_processor = PDFProcessor()

ALLOWED_GENDERS = ['Male', 'Female', 'Other']
ALLOWED_RELIGIONS = ['Christianity', 'Islam', 'Hinduism', 'Buddhism', 'Sikhism', 'Judaism', 'Other']

# Initialize database when the app starts
with app.app_context():
    init_db()

# Close database connection after each request
@app.teardown_appcontext
def teardown_db(exception):
    close_db_connection()

# [Rest of the existing app.py code remains the same until the upload_form route]

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(message="Username is required"),
        Length(min=3, max=50, message="Username must be between 3 and 50 characters")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required"),
        Length(min=6, message="Password must be at least 6 characters")
    ])

@with_db_connection
def validate_user(conn, username, password):
    """Validate user credentials"""
    try:
        user = conn.execute('SELECT * FROM users WHERE username = ?', 
                          (username,)).fetchone()
        if user and check_password_hash(user['password'], password):
            return True, user
        return False, None
    except Exception as e:
        logger.error(f"Database error in validate_user: {str(e)}")
        raise

class UploadForm(FlaskForm):
    file = FileField('PDF File', validators=[DataRequired()])

@app.route('/upload', methods=['GET', 'POST'])
def upload_form():
    """Handle PDF upload and form field extraction"""
    form = UploadForm()
    if form.validate_on_submit():
        file = form.file.data
        if file and file.filename.lower().endswith('.pdf'):
            filename = secure_filename(file.filename)
            filepath = os.path.join('uploads', filename)
            file.save(filepath)
            
            # Use PDFProcessor to extract form fields
            form_data = pdf_processor.process_pdf(filepath)
            
            # Create a dynamic form based on extracted fields
            class DynamicForm(FlaskForm):
                pass
            
            for field in form_data['fields']:
                setattr(DynamicForm, field['name'], StringField(field['label']))
            
            form = DynamicForm()
            
            return render_template('fill_form.html', 
                                form=form,
                                fields=form_data['fields'],
                                raw_text=form_data['raw_text'])
        
        flash('Invalid file type. Please upload a PDF file.')
        return redirect(url_for('upload_form'))
    
    return render_template('upload_form.html', form=form)

# [Rest of the existing app.py code remains the same]

@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('profile'))
    return redirect(url_for('login'))

@with_db_connection
def get_user_profile(conn, username):
    """Retrieve user profile data"""
    user = conn.execute('SELECT * FROM users WHERE username = ?', 
                       (username,)).fetchone()
    if user:
        profile = conn.execute('SELECT * FROM user_profiles WHERE user_id = ?', 
                             (user['id'],)).fetchone()
        return dict(profile) if profile else {}
    return {}

@with_db_connection
def save_user_profile(conn, username, profile_data):
    """Save updated profile data"""
    user = conn.execute('SELECT * FROM users WHERE username = ?', 
                       (username,)).fetchone()
    if user:
        # Check if profile exists
        existing_profile = conn.execute('SELECT * FROM user_profiles WHERE user_id = ?', 
                                      (user['id'],)).fetchone()
        
        if existing_profile:
            # Update existing profile
            conn.execute('''
                UPDATE user_profiles SET
                    given_name = ?,
                    last_name = ?,
                    mobile_number = ?,
                    email_address = ?,
                    address_line1 = ?,
                    address_line2 = ?,
                    address_line3 = ?,
                    address_line4 = ?,
                    city = ?,
                    state = ?,
                    country = ?,
                    post_code = ?,
                    date_of_birth = ?,
                    passport_number = ?,
                    gender = ?,
                    ethnicity = ?,
                    religion = ?
                WHERE user_id = ?
            ''', (
                profile_data['given_name'],
                profile_data['last_name'],
                profile_data['mobile_number'],
                profile_data['email_address'],
                profile_data['address_line1'],
                profile_data['address_line2'],
                profile_data['address_line3'],
                profile_data['address_line4'],
                profile_data['city'],
                profile_data['state'],
                profile_data['country'],
                profile_data['post_code'],
                profile_data['date_of_birth'],
                profile_data['passport_number'],
                profile_data['gender'],
                profile_data['ethnicity'],
                profile_data['religion'],
                user['id']
            ))
        else:
            # Insert new profile
            conn.execute('''
                INSERT INTO user_profiles (
                    user_id,
                    given_name,
                    last_name,
                    mobile_number,
                    email_address,
                    address_line1,
                    address_line2,
                    address_line3,
                    address_line4,
                    city,
                    state,
                    country,
                    post_code,
                    date_of_birth,
                    passport_number,
                    gender,
                    ethnicity,
                    religion
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user['id'],
                profile_data['given_name'],
                profile_data['last_name'],
                profile_data['mobile_number'],
                profile_data['email_address'],
                profile_data['address_line1'],
                profile_data['address_line2'],
                profile_data['address_line3'],
                profile_data['address_line4'],
                profile_data['city'],
                profile_data['state'],
                profile_data['country'],
                profile_data['post_code'],
                profile_data['date_of_birth'],
                profile_data['passport_number'],
                profile_data['gender'],
                profile_data['ethnicity'],
                profile_data['religion']
            ))
        
        conn.commit()

@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    profile_data = get_user_profile(session['username'])
    return render_template('view_profile.html', 
                         username=session['username'],
                         profile=profile_data)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('profile'))
    
    form = LoginForm()
    
    if request.method == 'POST':
        if form.validate_on_submit():
            username = form.username.data
            password = form.password.data
            
            try:
                is_valid, user = validate_user(username, password)
                if is_valid:
                    session.permanent = True
                    session['username'] = username
                    return redirect(url_for('profile'))
                else:
                    flash('Invalid username or password')
            except Exception as e:
                logger.error(f"Login error: {str(e)}")
                flash('An error occurred during login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"{field}: {error}")
    
    return render_template('login.html', form=form)

class ProfileForm(FlaskForm):
    given_name = StringField('Given Name')
    last_name = StringField('Last Name')
    mobile_number = StringField('Mobile Number')
    email_address = StringField('Email Address', validators=[DataRequired()])
    address_line1 = StringField('Address Line 1')
    address_line2 = StringField('Address Line 2')
    address_line3 = StringField('Address Line 3')
    address_line4 = StringField('Address Line 4')
    city = StringField('City')
    state = StringField('State')
    country = StringField('Country')
    post_code = StringField('Post Code')
    date_of_birth = StringField('Date of Birth')
    passport_number = StringField('Passport Number')
    gender = StringField('Gender')
    ethnicity = StringField('Ethnicity')
    religion = StringField('Religion')

@app.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    form = ProfileForm()
    profile_data = get_user_profile(session['username'])
    
    if request.method == 'POST':
        if form.validate_on_submit():
            # Update profile data
            updated_data = {
                'given_name': form.given_name.data,
                'last_name': form.last_name.data,
                'mobile_number': form.mobile_number.data,
                'email_address': form.email_address.data,
                'address_line1': form.address_line1.data,
                'address_line2': form.address_line2.data,
                'address_line3': form.address_line3.data,
                'address_line4': form.address_line4.data,
                'city': form.city.data,
                'state': form.state.data,
                'country': form.country.data,
                'post_code': form.post_code.data,
                'date_of_birth': form.date_of_birth.data,
                'passport_number': form.passport_number.data,
                'gender': form.gender.data,
                'ethnicity': form.ethnicity.data,
                'religion': form.religion.data
            }
            
            # Save updated profile
            save_user_profile(session['username'], updated_data)
            flash('Profile updated successfully!')
            return redirect(url_for('profile'))
    
    # Pre-fill form with existing data
    if profile_data:
        for field in form:
            if field.name in profile_data:
                field.data = profile_data[field.name]
    
    return render_template('profile.html', form=form)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
