from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_mail import Mail, Message
from flask_cors import CORS
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore, db # Import 'db' for Realtime Database
import random
import os
import razorpay
from twilio.rest import Client
from dotenv import load_dotenv

# Load environment variables (for Razorpay and Twilio)
load_dotenv()

app = Flask(__name__)
CORS(app) # Enable CORS for all routes

# ==== Mail Config ====
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', 'anjalimadhavi19@gmail.com') # Get from env or default
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', 'yqtontsgdgyzabre') # Get from env or default
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'anjalimadhavi19@gmail.com') # Get from env or default
mail = Mail(app)

# ==== Firebase Config (for Auth - Firestore) ====
# Ensure 'serviceAccountKey (2).json' is in the same directory as app.py
try:
    cred_auth = credentials.Certificate("serviceAccountKey (2).json")
    # Initialize the app and store the App object
    firebase_app_auth = firebase_admin.initialize_app(cred_auth, name='auth_app')
    db_auth = firestore.client(app=firebase_app_auth) # Pass the App object
    users_ref = db_auth.collection('users')
except ValueError as e:
    print(f"Error initializing auth Firebase app: {e}")
    # Handle cases where app might be initialized already in complex scenarios
    # For a simple script, this usually means the name 'auth_app' is already taken
    if "The name 'auth_app' is already in use" in str(e):
        firebase_app_auth = firebase_admin.get_app('auth_app')
        db_auth = firestore.client(app=firebase_app_auth)
        users_ref = db_auth.collection('users')
    else:
        raise # Re-raise other ValueErrors


# ==== Firebase Config (for Payments - Firestore, and Home Automation - Realtime DB) ====
try:
    cred_payments_ha = credentials.Certificate("firebase-key (2).json")
    # Initialize the app and store the App object
    # This app will be used for both payments (Firestore) and home automation (Realtime DB)
    firebase_app_payments_ha = firebase_admin.initialize_app(
        cred_payments_ha,
        options={
            'databaseURL': os.getenv('FIREBASE_DATABASE_URL', 'https://gestomateha-default-rtdb.firebaseio.com')
        },
        name='payments_ha_app'
    )
    db_payments = firestore.client(app=firebase_app_payments_ha) # Pass the App object
    # Get Realtime Database reference for home automation
    realtime_db_ref = db.reference('appliances', app=firebase_app_payments_ha) # Pass the App object
except ValueError as e:
    print(f"Error initializing payments/HA Firebase app: {e}")
    if "The name 'payments_ha_app' is already in use" in str(e):
        firebase_app_payments_ha = firebase_admin.get_app('payments_ha_app')
        db_payments = firestore.client(app=firebase_app_payments_ha)
        realtime_db_ref = db.reference('appliances', app=firebase_app_payments_ha)
    else:
        raise


# ==== Razorpay Credentials ====
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

# ==== Twilio Credentials ====
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
USER_PHONE_NUMBER = os.getenv("USER_PHONE_NUMBER") # You might want to make this dynamic

# Razorpay and Twilio Clients
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# ==== HTML Routes ====
@app.route('/')
def index():
    # Redirect to the login page as the entry point
    return redirect(url_for('login_page'))

@app.route('/login.html')
def login_page():
    return render_template('login.html')

@app.route('/web.html')
def web_page():
    return render_template('web.html') # Assuming web.html is your main dashboard after login

@app.route('/about.html')
def about_page():
    return render_template('about.html')

@app.route('/contact.html')
def contact_page():
    return render_template('contact.html')

@app.route('/gesture.html')
def gesture_page():
    return render_template('gesture.html')

@app.route('/homeautomation.html')
def homeautomation_page():
    return render_template('homeautomation.html')

@app.route('/payments.html')
def payments_page():
    payment_data = {
        "razorpay_key": RAZORPAY_KEY_ID,
        "amount": 5000,  # ₹50 in paise
        "user_name": "John Doe", # This should ideally come from user session
        "user_email": "john@example.com", # This should ideally come from user session
        "user_contact": USER_PHONE_NUMBER, # This should ideally come from user session
    }
    return render_template("payments.html", **payment_data)

# ==== API Routes ====

# ==== Generate OTP ====
def generate_otp():
    return str(random.randint(100000, 999999))

# ==== SignUp ====
@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user_doc = users_ref.document(email).get()
    if user_doc.exists:
        return jsonify({"message": "User already exists"}), 200

    users_ref.document(email).set({
        'email': email,
        'password': password
    })
    return jsonify({"message": "User registered successfully"}), 201

# ==== Send OTP ====
@app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    user_doc = users_ref.document(email).get()
    if not user_doc.exists or user_doc.to_dict().get('password') != password:
        return jsonify({"error": "Invalid credentials"}), 401

    otp = generate_otp()
    timestamp = datetime.utcnow().isoformat()

    users_ref.document(email).set({
        'otp': otp,
        'timestamp': timestamp
    }, merge=True)

    msg = Message('Your OTP Code', recipients=[email])
    msg.body = f'Your OTP is: {otp} (valid for 5 minutes)'

    try:
        mail.send(msg)
        return jsonify({"message": "OTP sent to your email."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==== Verify OTP ====
@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')

    if not email or not otp:
        return jsonify({"error": "Email and OTP required"}), 400

    user_doc = users_ref.document(email).get()
    if not user_doc.exists:
        return jsonify({"error": "User not found"}), 404

    user_data = user_doc.to_dict()

    if user_data.get('otp') != otp:
        return jsonify({"error": "Invalid OTP"}), 401

    try:
        timestamp = datetime.fromisoformat(user_data.get('timestamp'))
    except:
        return jsonify({"error": "Invalid timestamp format"}), 500

    if datetime.utcnow() - timestamp > timedelta(minutes=5):
        return jsonify({"error": "OTP expired"}), 403

    return jsonify({"message": "OTP verified successfully!"}), 200

# ==== Payment Success Route ====
@app.route('/payment-success', methods=['POST'])
def payment_success():
    data = request.form
    payment_id = data.get("razorpay_payment_id")
    amount = data.get("amount")

    # Optional: Static user data for now - ideally get this from a session or user context
    user_email = "john@example.com" # Replace with actual user email if available

    # Store in Firestore
    payment_record = {
        "email": user_email,
        "payment_id": payment_id,
        "amount": int(amount) / 100,  # Convert from paise to ₹
        "status": "Success",
        "timestamp": datetime.utcnow().isoformat()
    }

    db_payments.collection("payments").add(payment_record)

    # Send SMS
    try:
        message = twilio_client.messages.create(
            body=f"Payment of ₹{int(amount)/100:.2f} successful! Payment ID: {payment_id}",
            from_=TWILIO_PHONE_NUMBER,
            to=USER_PHONE_NUMBER
        )
        print(f"SMS sent: {message.sid}")
    except Exception as e:
        print(f"Twilio error: {e}") # Log the error, but don't fail the payment success

    return f"✅ Payment Successful! Payment ID: {payment_id}"

# ==== Home Automation Realtime Database Endpoints (Optional, for server-side control) ====
# If your HAGestureRecog.py directly updates Firebase Realtime DB,
# you might not need these endpoints unless you want the Flask app to also control.
# However, for manual control from the web UI, the JS directly updates Firebase.
# These routes could be useful if you wanted to implement an API for manual control
# from outside the web UI or from another backend service.

@app.route('/api/appliances/<device>/<state>', methods=['POST'])
def update_appliance_state(device, state):
    if device not in ['light', 'fan']:
        return jsonify({"error": "Invalid device"}), 400
    if state not in ['on', 'off']:
        return jsonify({"error": "Invalid state"}), 400

    try:
        realtime_db_ref.child(device).set(state)
        return jsonify({"message": f"{device} set to {state}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/appliances/fan_speed/<speed>', methods=['POST'])
def update_fan_speed(speed):
    if speed not in ['1', '2', '3']:
        return jsonify({"error": "Invalid fan speed. Must be 1, 2, or 3."}), 400
    try:
        realtime_db_ref.child('fan_speed').set(speed)
        return jsonify({"message": f"Fan speed set to {speed}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8000)