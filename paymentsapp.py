from flask import Flask, render_template, request
import razorpay
from twilio.rest import Client
from dotenv import load_dotenv
import os
import firebase_admin
from firebase_admin import credentials, firestore

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Razorpay Credentials
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

# Twilio Credentials
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
USER_PHONE_NUMBER = os.getenv("USER_PHONE_NUMBER")

# Razorpay and Twilio Clients
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Initialize Firestore
cred = credentials.Certificate("firebase-key (2).json")
firebase_admin.initialize_app(cred)
db = firestore.client()

@app.route('/')
def home():
    payment_data = {
        "razorpay_key": RAZORPAY_KEY_ID,
        "amount": 5000,  # ₹50 in paise
        "user_name": "John Doe",
        "user_email": "john@example.com",
        "user_contact": USER_PHONE_NUMBER,
    }
    return render_template("payments.html", **payment_data)

@app.route('/payment-success', methods=['POST'])
def payment_success():
    data = request.form
    payment_id = data.get("razorpay_payment_id")
    amount = data.get("amount")

    # Optional: Static user data for now
    user_email = "john@example.com"

    # 🔥 Store in Firestore
    payment_record = {
        "email": user_email,
        "payment_id": payment_id,
        "amount": int(amount) / 100,  # Convert from paise to ₹
        "status": "Success"
    }

    db.collection("payments").add(payment_record)

    # Send SMS
    try:
        message = twilio_client.messages.create(
            body=f"Payment of ₹{int(amount)/100:.2f} successful! Payment ID: {payment_id}",
            from_=TWILIO_PHONE_NUMBER,
            to=USER_PHONE_NUMBER
        )
    except Exception as e:
        print("Twilio error:", e)

    return f"✅ Payment Successful! Payment ID: {payment_id}"

if __name__ == "__main__":
    app.run(debug=True)
