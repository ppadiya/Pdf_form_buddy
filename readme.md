# User App

User App is a web application designed to handle user registration, login, profile management, and PDF form processing. This project is still a work in progress.

## Features

- User Registration and Login
- Profile Management
- PDF Form Upload and Field Extraction
- OCR Processing for Scanned PDFs
- Form Autofill using Profile Data

## Project Structure
user_app/ ├── pycache/ ├── p/ ├── .env ├── app.py ├── app.py.backup ├── app.log ├── config.py ├── database.py ├── fieldextractor.log ├── fieldextractor.py ├── fill_form_handler.py ├── form_autofill.py ├── ocr_processor.py ├── requirements.txt ├── retrievedata.py ├── static/ │ └── css/ │ └── styles.css ├── templates/ │ ├── base.html │ ├── fill_form.html │ ├── login.html │ ├── profile.html │ ├── register.html │ ├── review_form.html │ ├── upload_form.html │ └── view_profile.html ├── Sample Files/ ├── TEST.PY └── uploads/


## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/user_app.git
    cd user_app
    ```

2. Create a virtual environment and activate it:
    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. Install the required packages:
    ```sh
    pip install -r requirements.txt
    ```

4. Set up the environment variables in a [.env](http://_vscodecontentref_/22) file:
    ```env
    HUGGINGFACE_API_KEY="your_huggingface_api_key"
    SECRET_KEY="your_secret_key"
    WTF_CSRF_SECRET_KEY="your_csrf_secret_key"
    DEEPSEEK_API_KEY="your_deepseek_api_key"
    ```

5. Initialize the database:
    ```sh
    python -c "from database import init_db; init_db()"
    ```

## Usage

1. Run the application:
    ```sh
    flask run
    ```

2. Open your web browser and go to `http://127.0.0.1:5000/`.

## Project Components

### [app.py](http://_vscodecontentref_/23)

The main application file that sets up the Flask app, routes, and handles user authentication and profile management.

### [config.py](http://_vscodecontentref_/24)

Contains configuration settings for the Flask app, including secret keys and session settings.

### [database.py](http://_vscodecontentref_/25)

Handles database connections and operations, including user and profile management.

### [fieldextractor.py](http://_vscodecontentref_/26)

Uses the DeepSeek API to extract fields from uploaded PDF forms.

### [fill_form_handler.py](http://_vscodecontentref_/27)

Handles the form filling process, including field validation and autofill using profile data.

### [form_autofill.py](http://_vscodecontentref_/28)

Contains logic for autofilling form fields based on user profile data.

### [ocr_processor.py](http://_vscodecontentref_/29)

Processes PDF files using OCR to extract text content.

### [retrievedata.py](http://_vscodecontentref_/30)

A utility script to retrieve and print user data from the database.

### Templates

- [base.html](http://_vscodecontentref_/31): Base template for the application.
- [fill_form.html](http://_vscodecontentref_/32): Template for displaying and filling out extracted form fields.
- [login.html](http://_vscodecontentref_/33): Template for user login.
- [profile.html](http://_vscodecontentref_/34): Template for editing user profile.
- [register.html](http://_vscodecontentref_/35): Template for user registration.
- [review_form.html](http://_vscodecontentref_/36): Template for reviewing form data before submission.
- [upload_form.html](http://_vscodecontentref_/37): Template for uploading PDF forms.
- [view_profile.html](http://_vscodecontentref_/38): Template for viewing user profile.

### Static Files

- [styles.css](http://_vscodecontentref_/39): Contains the CSS styles for the application.

## Logs

- [app.log](http://_vscodecontentref_/40): Logs application events and errors.
- [fieldextractor.log](http://_vscodecontentref_/41): Logs field extraction events and errors.

## Testing

To run the tests, use the following command:
```sh
python TEST.PY

Contributing
Contributions are welcome! Please fork the repository and submit a pull request.




