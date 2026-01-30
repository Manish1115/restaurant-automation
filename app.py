from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request
import firebase_admin
from firebase_admin import credentials, firestore
from twilio.twiml.messaging_response import MessagingResponse
import random
from twilio.rest import Client
import os

account_sid = os.getenv("TWILIO_SID")
auth_token = os.getenv("TWILIO_TOKEN")



client = Client(account_sid, auth_token)

def send_whatsapp_message(to, message):
    client.messages.create(
        from_='whatsapp:+14155238886',
        body=message,
        to=to
    )



cred = credentials.Certificate("firebase_key.json")
firebase_admin.initialize_app(cred)

db = firestore.client()

app = Flask(__name__)
@app.route('/')
def home():
    return render_template("index.html")

@app.route('/submit', methods=['POST'])
def submit():
    rating = int(request.form.get("rating"))
    feedback = request.form.get("feedback")

    data = {
        "rating": rating,
        "feedback": feedback
    }

    db.collection("reviews").add(data)

    if rating >= 4:
        return render_template("positive.html")
    else:
        return render_template("negative.html")

@app.route('/admin')
def admin():
    reviews_ref = db.collection("reviews").stream()
    bookings_ref = db.collection("bookings").stream()
    vouchers_ref = db.collection("vouchers").stream()
    restaurant_id = "res001"

    reviews = [doc.to_dict() for doc in reviews_ref]

    bookings = []
    for doc in bookings_ref:
        data = doc.to_dict()
        data["id"] = doc.id   
        bookings.append(data)

    vouchers = []
    for doc in vouchers_ref:
        data = doc.to_dict()
        data["id"] = doc.id
        vouchers.append(data)    

    return render_template("admin.html", reviews=reviews, bookings=bookings, vouchers=vouchers)


@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    incoming_msg = request.values.get("Body", "").lower()
    resp = MessagingResponse()
    msg = resp.message()

    if "hi" in incoming_msg:
        is_open = get_restaurant_status()
        status_text = "OPEN 🟢" if is_open else "CLOSED 🔴"
        msg.body(
            f"Welcome to Our Restaurant 🍽️\n"
            f"We are currently {status_text}\n\n"
            "Reply with:\n"
            "1️⃣ Menu\n"
            "2️⃣ Book Table\n"
            "3️⃣ Give Feedback"
        )

    elif incoming_msg == "1":
        msg.body(
            "📋 Today's Menu:\n"
            "🍕 Pizza - ₹250\n"
            "🍔 Burger - ₹180\n"
            "🥤 Cold Coffee - ₹120"
        )

    elif incoming_msg == "2":
        msg.body(
            "📅 Table Booking\n"
            "Please reply with:\n"
            "Name, Date, Time, Number of Guests"
        )

    elif incoming_msg == "3":
        msg.body("⭐ Rate us from 1–5 to share feedback.")

    elif "," in incoming_msg:
        user_number = request.values.get("From")

        db.collection("bookings").add({
            "details": incoming_msg,
            "status": "Pending",
            "phone": user_number
        })

        msg.body("✅ Booking request received. We'll confirm shortly.")

    elif incoming_msg in ["1", "2", "3", "4", "5"]:
        rating = int(incoming_msg)

        if rating >= 4:
            voucher = generate_voucher()
            user_number = request.values.get("From")

            db.collection("vouchers").add({
                "code": voucher,
                "phone": user_number,
                "discount": "10%",
                "used": False
                })

            msg.body(
                f"Thanks for your rating! 🙌\n"
                "Please leave us a Google review here:\n"
                "YOUR_GOOGLE_REVIEW_LINK\n\n"
                f"Your 10% discount code: {voucher}"
            )

        else:
            msg.body(
                "We're sorry your experience wasn't perfect.\n"
                "Please tell us what went wrong."
            )

    else:
        msg.body("Sorry, I didn’t understand that.")

    return str(resp)


@app.route('/mark_used', methods=['POST'])
def mark_used():
    voucher_id = request.form.get("id")

    voucher_ref = db.collection("vouchers").document(voucher_id)
    voucher_data = voucher_ref.get().to_dict()

    voucher_ref.update({
        "used": True
    })

    phone = voucher_data["phone"]

    send_whatsapp_message(
        phone,
        f"🎉 Your voucher {voucher_data['code']} has been successfully redeemed. Thank you for visiting us!"
    )

    return "Voucher marked as used and customer notified."


@app.route('/set_status', methods=['POST'])
def set_status():
    status = request.form.get("status")
    is_open = True if status == "open" else False

    db.collection("settings").document("status").set({
        "open": is_open
    })

    return "Status updated. Go back."



@app.route('/update_booking', methods=['POST'])
def update_booking():
    booking_id = request.form.get("id")
    action = request.form.get("action")

    new_status = "Accepted" if action == "accept" else "Rejected"

    booking_ref = db.collection("bookings").document(booking_id)
    booking_data = booking_ref.get().to_dict()

    booking_ref.update({
        "status": new_status
    })

    phone = booking_data["phone"]

    if new_status == "Accepted":
        send_whatsapp_message(phone, "✅ Your table booking is CONFIRMED. See you soon!")
    else:
        send_whatsapp_message(phone, "❌ Sorry, your booking was not available. Please try another time.")

    return "Booking updated. Go back."


def generate_voucher():
    return "DISC" + str(random.randint(1000, 9999))

def get_restaurant_status():
    doc = db.collection("settings").document("status").get()
    if doc.exists:
        return doc.to_dict().get("open", True)
    return True


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
