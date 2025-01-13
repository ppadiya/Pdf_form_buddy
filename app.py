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
from PyPDF2 import PdfReader, PdfWriter
import requests
from transformers import pipeline
from dotenv import load_dotenv

app = Flask(__name__)
app.config.from_object(Config)

# Initialize CSRF protection
csrf = CSRFProtect()
csrf.init_app(app)

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALLOWED_GENDERS = ['Male', 'Female', 'Other']
ALLOWED_RELIGIONS = ['Christianity', 'Islam', 'Hinduism', 'Buddhism', 'Sikhism', 'Judaism', 'Other']

# Initialize database when the app starts
with app.app_context():
    init_db()

# Close database connection after each request
@app.teardown_appcontext
def teardown_db(exception):
    close_db_connection()

# In your routes, use get_db_connection() when you need a database cursor
# Example:
def some_database_function():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Perform database operations

def get_country_list():
    """Retrieve a sorted list of country names"""
    return sorted([country.name for country in pycountry.countries])

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

@with_db_connection
def create_user(conn, username, password):
    """Create a new user"""
    hashed_password = generate_password_hash(password)
    conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', 
                (username, hashed_password))
    conn.commit()

@with_db_connection
def save_user_profile(conn, user_id, profile_data):
    """Save or update user profile"""
    columns = ', '.join(profile_data.keys())
    placeholders = ', '.join(['?' for _ in profile_data])
    conn.execute(f'''
        INSERT OR REPLACE INTO user_profiles 
        (user_id, {columns}) 
        VALUES (?, {placeholders})
    ''', (user_id, *profile_data.values()))
    conn.commit()

@with_db_connection
def get_user_profile(conn, user_id):
    """Retrieve user profile"""
    profile = conn.execute('SELECT * FROM user_profiles WHERE user_id = ?', 
                          (user_id,)).fetchone()
    return dict(profile) if profile else {}

def validate_profile_data(profile_data):
    if not profile_data.get('email_address'):
        return False, "Email address is required"
    # Add more validation as needed
    return True, None

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(message="Username is required"),
        Length(min=3, max=50, message="Username must be between 3 and 50 characters")
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required"),
        Length(min=6, message="Password must be at least 6 characters")
    ])

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

class UploadForm(FlaskForm):
    file = FileField('PDF File', validators=[DataRequired()])

class FillFormForm(FlaskForm):
    pass  # We'll create fields dynamically

# Load environment variables
load_dotenv()

# Configure Hugging Face
HUGGINGFACE_API_KEY = os.getenv('HUGGINGFACE_API_KEY')
HUGGINGFACE_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"
headers = {"Authorization": f"Bearer {os.getenv('HUGGINGFACE_API_KEY')}"}

# Add these configurations to your app
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_form_fields(pdf_path):
    """Extract form fields from PDF with better structure handling"""
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text()

    try:
        fields = []
        lines = text.split('\n')
        current_section = ""
        
        logger.info("Raw text from PDF:")
        logger.info(text)  # Debug log
        
        for i, line in enumerate(lines):
            # Clean the line
            line = ''.join(char for char in line if char.isprintable())
            line = line.strip()
            
            # Skip empty lines or form dimensions
            if not line or len(line) < 2 or line.startswith('210㎜×297㎜'):
                continue

            # Check if this is a section header
            if line[0].isdigit() and '.' in line[:3]:
                current_section = line
                logger.info(f"Found section: {current_section}")
                continue

            # Look for field indicators
            if any(char in line for char in [':', '□', '■', '_', '/', '(', ')']):
                # Extract field name and English translation
                field_name = line
                english_name = None
                korean_name = None

                # Try different patterns to extract field names
                if '(' in line and ')' in line:
                    # Pattern: Korean (English)
                    korean = line[:line.find('(')].strip()
                    english = line[line.find('(')+1:line.find(')')].strip()
                    if english and all(ord(c) < 128 for c in english):
                        english_name = english
                        korean_name = korean
                elif '/' in line:
                    # Pattern: Korean/English
                    parts = line.split('/')
                    if len(parts) == 2:
                        korean_name = parts[0].strip()
                        english_name = parts[1].split('(')[0].strip()

                # Use English name if available, otherwise use original
                display_name = english_name or field_name
                
                # Clean and normalize the field name
                clean_field_name = ''.join(
                    char.lower() for char in (english_name or field_name)
                    if char.isalnum() or char.isspace()
                ).strip().replace(' ', '_')

                # Skip if field name is too short or is a note
                if len(clean_field_name) < 2 or any(word in clean_field_name.lower() for word in ['note', 'reference']):
                    continue

                # Determine field type
                field_type = 'text'  # default
                if any(word in display_name.lower() for word in ['date', 'birth', 'issued', 'expiry']):
                    field_type = 'date'
                elif any(word in display_name.lower() for word in ['gender', 'sex']):
                    field_type = 'select'
                elif 'yes' in line.lower() or 'no' in line.lower():
                    field_type = 'radio'
                elif any(word in display_name.lower() for word in ['email']):
                    field_type = 'email'
                elif any(word in display_name.lower() for word in ['phone', 'mobile', 'tel']):
                    field_type = 'tel'

                # Look for options in next few lines for select/radio fields
                options = []
                if field_type in ['select', 'radio']:
                    next_lines = lines[i+1:i+5]  # Look at next 4 lines
                    for next_line in next_lines:
                        if '□' in next_line or '■' in next_line:
                            option = next_line.replace('□', '').replace('■', '').strip()
                            if option and len(option) > 1:
                                options.append(option)

                field = {
                    "name": clean_field_name,
                    "original_name": display_name,
                    "korean_name": korean_name,
                    "type": field_type,
                    "section": current_section,
                    "required": '*' in line,
                    "options": options
                }
                
                logger.info(f"Found field: {display_name} (Type: {field_type})")
                if options:
                    logger.info(f"Options for {display_name}: {options}")
                
                fields.append(field)

        # Remove duplicates while preserving order
        seen = set()
        unique_fields = []
        for field in fields:
            if field['name'] not in seen:
                seen.add(field['name'])
                unique_fields.append(field)

        logger.info(f"Successfully extracted {len(unique_fields)} unique fields")
        return {"fields": unique_fields}

    except Exception as e:
        logger.error(f"Error extracting form fields: {str(e)}")
        raise

def fill_pdf_form(pdf_path, form_data):
    """Fill PDF form with provided data"""
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    
    # Get the first page
    page = reader.pages[0]
    writer.add_page(page)
    
    # Create a new PDF with filled form fields
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'filled_form.pdf')
    
    try:
        # Get form fields from the PDF
        form = reader.get_form_texts() if hasattr(reader, 'get_form_texts') else {}
        
        # Fill each field with corresponding data
        for field_name, field in form.items():
            if field_name in form_data:
                field.update(
                    value=form_data[field_name]
                )
        
        # Write the filled form to a new PDF
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        return output_path
        
    except Exception as e:
        logger.error(f"Error filling PDF form: {str(e)}")
        raise

def cleanup_temp_data():
    """Clean up old temporary form data"""
    try:
        conn = get_db_connection()
        # Delete temp data older than 1 hour
        conn.execute('''
            DELETE FROM temp_form_data 
            WHERE created_at < datetime('now', '-1 hour')
        ''')
        conn.commit()
    except Exception as e:
        logger.error(f"Error cleaning up temp data: {str(e)}")
    finally:
        if conn:
            conn.close()

# Add this to your routes that need cleanup
@app.before_request
def before_request():
    cleanup_temp_data()

@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('profile'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if request.method == 'POST' and form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        
        try:
            create_user(username, password)
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists. Please choose another.')
    
    return render_template('register.html', form=form)

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
                    flash('Login successful!', 'success')
                    return redirect(url_for('profile'))
                else:
                    flash('Invalid username or password', 'error')
            except Exception as e:
                logger.error(f"Login error: {str(e)}")
                flash('An error occurred during login', 'error')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"{field}: {error}", 'error')
    
    # For GET requests or failed POST requests
    return render_template('login.html', form=form)

@app.route('/profile', methods=['GET'])
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        user = conn.execute('SELECT id FROM users WHERE username = ?', 
                          (session['username'],)).fetchone()
        
        if not user:
            conn.close()  # Close connection before redirect
            flash('User not found')
            return redirect(url_for('login'))
        
        user_id = user['id']
        profile = conn.execute('SELECT * FROM user_profiles WHERE user_id = ?', 
                           (user_id,)).fetchone()
        
        profile_data = dict(profile) if profile else {}
        conn.close()  # Close connection after all database operations
        
        return render_template('view_profile.html', 
                             username=session['username'], 
                             profile=profile_data)
    except sqlite3.Error as e:
        flash(f'Database error occurred: {str(e)}')
        return redirect(url_for('login'))

@app.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    form = ProfileForm()  # Create form instance
    
    try:
        conn = get_db_connection()
        user = conn.execute('SELECT id FROM users WHERE username = ?', 
                          (session['username'],)).fetchone()
        
        if not user:
            conn.close()
            return redirect(url_for('login'))
        
        user_id = user['id']
        
        if request.method == 'POST' and form.validate_on_submit():
            profile_data = {
                'given_name': form.given_name.data,
                'last_name': form.last_name.data,
                'address_line1': form.address_line1.data,
                'address_line2': form.address_line2.data,
                'address_line3': form.address_line3.data,
                'address_line4': form.address_line4.data,
                'city': form.city.data,
                'state': form.state.data,
                'country': form.country.data,
                'post_code': form.post_code.data,
                'mobile_number': form.mobile_number.data,
                'email_address': form.email_address.data,
                'date_of_birth': form.date_of_birth.data,
                'passport_number': form.passport_number.data,
                'gender': form.gender.data,
                'ethnicity': form.ethnicity.data,
                'religion': form.religion.data
            }
            
            is_valid, error = validate_profile_data(profile_data)
            if not is_valid:
                conn.close()
                flash(error)
                return redirect(url_for('edit_profile'))
            
            # Use the same connection for saving profile
            columns = ', '.join(profile_data.keys())
            placeholders = ', '.join(['?' for _ in profile_data])
            
            conn.execute(f'''
                INSERT OR REPLACE INTO user_profiles 
                (user_id, {columns}) 
                VALUES (?, {placeholders})
            ''', (user_id, *profile_data.values()))
            conn.commit()
            conn.close()
            
            flash('Profile updated successfully!')
            return redirect(url_for('profile'))
        
        # For GET request
        profile = conn.execute('SELECT * FROM user_profiles WHERE user_id = ?', 
                             (user_id,)).fetchone()
        profile_data = dict(profile) if profile else {}
        conn.close()
        
        # Populate form with existing data
        if profile_data:
            for field, value in profile_data.items():
                if hasattr(form, field):
                    getattr(form, field).data = value
        
        countries = get_country_list()
        
        return render_template('profile.html', 
                             username=session['username'], 
                             profile=profile_data,
                             form=form,  # Pass form to template
                             countries=countries)
                             
    except sqlite3.Error as e:
        flash(f'Database error occurred: {str(e)}')
        return redirect(url_for('profile'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('You have been logged out.')
    return redirect(url_for('login'))

@app.route('/upload_form', methods=['GET', 'POST'])
def upload_form():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    form = UploadForm()
    
    if request.method == 'POST' and form.validate_on_submit():
        flash('Processing uploaded file...', 'info')
        file = form.file.data
        if file and allowed_file(file.filename):
            try:
                # Get user_id
                conn = get_db_connection()
                user = conn.execute('SELECT id FROM users WHERE username = ?', 
                                  (session['username'],)).fetchone()
                user_id = user['id']

                # Create a unique filename
                filename = secure_filename(f"{session['username']}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                flash('File uploaded successfully, extracting form fields...', 'info')
                
                # Extract form fields
                form_fields = extract_form_fields(filepath)
                
                if not form_fields.get('fields'):
                    flash('No form fields could be extracted from the PDF', 'error')
                    return redirect(request.url)
                
                # Store form data in database instead of session
                import json
                conn.execute('''
                    INSERT INTO temp_form_data (user_id, pdf_path, form_fields)
                    VALUES (?, ?, ?)
                ''', (user_id, filepath, json.dumps(form_fields)))
                conn.commit()
                
                # Store only the temp_form_data id in session
                temp_data = conn.execute('''
                    SELECT id FROM temp_form_data 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC LIMIT 1
                ''', (user_id,)).fetchone()
                
                session['temp_form_id'] = temp_data['id']
                
                flash(f"Successfully extracted {len(form_fields['fields'])} fields from the form", 'success')
                logger.info(f"Successfully processed PDF form with {len(form_fields['fields'])} fields")
                return redirect(url_for('fill_form'))
                
            except Exception as e:
                logger.error(f"Error processing PDF: {str(e)}")
                flash(f'Error processing PDF: Please ensure it is a valid form', 'error')
                return redirect(request.url)
            finally:
                conn.close()
        else:
            flash('Please upload a valid PDF file', 'error')
    
    return render_template('upload_form.html', form=form)

@app.route('/fill_form', methods=['GET', 'POST'])
def fill_form():
    if 'username' not in session or 'temp_form_id' not in session:
        return redirect(url_for('login'))
    
    form = FillFormForm()
    
    try:
        conn = get_db_connection()
        # Get form data from database
        temp_data = conn.execute('''
            SELECT * FROM temp_form_data WHERE id = ?
        ''', (session['temp_form_id'],)).fetchone()
        
        if not temp_data:
            flash('Form data not found', 'error')
            return redirect(url_for('upload_form'))
        
        import json
        form_fields = json.loads(temp_data['form_fields'])
        pdf_path = temp_data['pdf_path']
        
        # Get user profile data
        user = conn.execute('SELECT id FROM users WHERE username = ?', 
                          (session['username'],)).fetchone()
        user_id = user['id']
        profile = conn.execute('SELECT * FROM user_profiles WHERE user_id = ?', 
                             (user_id,)).fetchone()
        profile_data = dict(profile) if profile else {}

        if request.method == 'POST' and form.validate_on_submit():
            # Collect form data
            form_data = {}
            for field in form_fields['fields']:
                field_name = field['name']
                value = request.form.get(field_name, '')
                form_data[field_name] = value
                
                # Update profile with new data if it's not already there
                if value and field_name not in profile_data:
                    try:
                        flash(f'Adding new field to profile: {field_name}', 'info')
                        conn.execute(f'ALTER TABLE user_profiles ADD COLUMN {field_name} TEXT')
                    except sqlite3.OperationalError:
                        # Column might already exist
                        pass
            
            # Update profile with new data
            if form_data:
                flash('Updating profile with new data...', 'info')
                columns = ', '.join(form_data.keys())
                placeholders = ', '.join(['?' for _ in form_data])
                values = list(form_data.values())
                
                conn.execute(f'''
                    UPDATE user_profiles 
                    SET ({columns}) = ({placeholders})
                    WHERE user_id = ?
                ''', (*values, user_id))
                conn.commit()
                flash('Profile updated successfully!', 'success')
            
            # Store form data in session for confirmation
            session['form_data'] = form_data
            
            # Show review page
            return render_template('review_form.html',
                                form=form,
                                form_data=form_data,
                                profile_data=profile_data)
        
        # GET request - show form with pre-filled data
        # Map common field names to profile fields
        field_mappings = {
            'full_name': ['given_name', 'last_name'],
            'name': ['given_name', 'last_name'],
            'first_name': ['given_name'],
            'last_name': ['last_name'],
            'email': ['email_address'],
            'phone': ['mobile_number'],
            'mobile': ['mobile_number'],
            'address': ['address_line1'],
            'date_of_birth': ['date_of_birth'],
            'passport': ['passport_number'],
            'gender': ['gender'],
            'nationality': ['nationality']
        }

        # Pre-fill form fields from profile data
        for field in form_fields['fields']:
            field_name = field['name'].lower()
            # Check direct match
            if field_name in profile_data:
                field['value'] = profile_data[field_name]
            else:
                # Check mapped fields
                for map_key, profile_keys in field_mappings.items():
                    if map_key in field_name:
                        # Handle composite fields (like full name)
                        if len(profile_keys) > 1:
                            values = [profile_data.get(key, '') for key in profile_keys]
                            field['value'] = ' '.join(filter(None, values))
                        else:
                            field['value'] = profile_data.get(profile_keys[0], '')

        flash('Please review and complete the form fields below', 'info')
        return render_template('fill_form.html',
                             form=form,
                             form_fields=form_fields['fields'],
                             profile_data=profile_data)
                             
    except Exception as e:
        logger.error(f"Error in fill_form: {str(e)}")
        flash(f'Error processing form: {str(e)}', 'error')
        return redirect(url_for('profile'))
    finally:
        conn.close()

# Add this function to reinitialize the database
def reinit_db():
    """Reinitialize database with new tables"""
    with app.app_context():
        init_db()
        flash('Database reinitialized successfully', 'success')

# Add this route for development purposes
@app.route('/reinit_db')
def reinit_db_route():
    if app.debug:  # Only allow in debug mode
        reinit_db()
        return redirect(url_for('login'))
    return "Not allowed", 403

def init_app(app):
    app.teardown_appcontext(close_db_connection)
    with app.app_context():
        init_db()

# Use it in your app initialization
init_app(app)

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    if request.method == 'GET':
        # Don't show error for GET requests
        return render_template('login.html', form=LoginForm())
    else:
        flash('The form has expired. Please try again.', 'error')
        return redirect(url_for('login'))

if __name__ == '__main__':
    print("Starting Flask server...")
    app.run(debug=True)