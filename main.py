import firebase_admin
from firebase_admin import credentials, firestore, functions
from flask import Flask, request, jsonify
import requests
import datetime

# Initialize Firebase Admin SDK
cred = credentials.Certificate("path/to/your/serviceAccountKey.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

# Flask App Setup
app = Flask(__name__)

# WhatsApp API Configuration
WHATSAPP_API_URL = "https://graph.facebook.com/v17.0/YOUR_PHONE_NUMBER_ID/messages"
VERIFY_TOKEN = "YOUR_VERIFY_TOKEN"
ACCESS_TOKEN = "YOUR_ACCESS_TOKEN"

# Webhook Verification
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if token == VERIFY_TOKEN:
        return challenge, 200
    else:
        return "Forbidden", 403

# Webhook for Receiving Messages
@app.route("/webhook", methods=["POST"])
def handle_webhook():
    data = request.get_json()

    if "entry" in data:
        for entry in data["entry"]:
            if "changes" in entry:
                for change in entry["changes"]:
                    if "value" in change and "messages" in change["value"]:
                        for message in change["value"]["messages"]:
                            handle_message(message, change["value"]["metadata"]["phone_number_id"])
    return "EVENT_RECEIVED", 200

def handle_message(message, phone_number_id):
    from_number = message["from"]
    text_body = message.get("text", {}).get("body", "")

    # Check if user is already registered
    user_ref = db.collection("users").document(from_number)
    user = user_ref.get()

    if not user.exists:
        # Register new user
        user_ref.set({
            "phone_number": from_number,
            "created_at": datetime.datetime.utcnow().isoformat(),
        })
        send_whatsapp_message(from_number, phone_number_id, "Welcome! You have been registered. Send your notes, and I will help you schedule revisions.")
    else:
        # Save message to Firestore
        note_ref = db.collection("notes").add({
            "user_id": from_number,
            "content": text_body,
            "created_at": datetime.datetime.utcnow().isoformat(),
            "schedule": generate_schedule()
        })

        # Send acknowledgment back to WhatsApp
        send_whatsapp_message(from_number, phone_number_id, "Thanks for your message! I'll help you schedule revisions.")

# Generate Revision Schedule
def generate_schedule():
    base_date = datetime.datetime.utcnow()
    intervals = [20, 72, 168, 360, 720, 2160, 4320]  # Hours: 20h, 3d, 7d, 15d, 1m, 3m, 6m
    return [(base_date + datetime.timedelta(hours=i)).isoformat() for i in intervals]

# Send Message via WhatsApp API
def send_whatsapp_message(to, phone_number_id, message):
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    requests.post(WHATSAPP_API_URL, headers=headers, json=payload)

# Firebase Cloud Function Wrapper
firebase_app = functions.get_app()
firestore_functions = functions.https.on_request(app)

if __name__ == "__main__":
    app.run(debug=True)
