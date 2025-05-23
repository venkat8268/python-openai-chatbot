import openai
import os
import sqlite3
import re
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

app = Flask(__name__)

# Configure SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///chatbot.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Define database model
class ChatHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_message = db.Column(db.String(500), nullable=False)
    bot_reply = db.Column(db.String(500), nullable=False)
    mood = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Initialize OpenAI API
OPENAI_API_KEY = "test-api-key"
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Mood detection function
def detect_mood(user_message):
    user_message = user_message.lower()
    
    # Define mood patterns
    mood_patterns = {
        "Happy 😊": r"\b(happy|great|awesome|excited|fantastic|good)\b",
        "Sad 😔": r"\b(sad|depressed|unhappy|crying|hurt)\b",
        "Angry 😡": r"\b(angry|frustrated|mad|furious)\b",
        "Anxious 😰": r"\b(worried|nervous|stressed|anxious)\b",
    }

    for mood, pattern in mood_patterns.items():
        if re.search(pattern, user_message):
            return mood

    return "Neutral 😐"

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    mood = detect_mood(user_message)

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": user_message}]
    )

    bot_reply = response.choices[0].message.content.strip()

    # Store chat in database
    with sqlite3.connect("chatbot.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_history (user_message, bot_reply, mood, timestamp) VALUES (?, ?, ?, datetime('now'))",
            (user_message, bot_reply, mood),
        )
        conn.commit()

    return jsonify({"reply": bot_reply, "mood": mood})

@app.route("/mood-stats", methods=["GET"])
def mood_stats():
    last_7_days = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")

    with sqlite3.connect("chatbot.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DATE(timestamp), mood FROM chat_history WHERE DATE(timestamp) >= ?",
            (last_7_days,),
        )
        data = cursor.fetchall()

    # Initialize mood count dictionary for the last 7 days
    mood_counts = {
        (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d"): {
            "Happy 😊": 0,
            "Sad 😔": 0,
            "Angry 😡": 0,
            "Anxious 😰": 0,
            "Neutral 😐": 0,
        }
        for i in range(7)
    }

    # Populate mood counts from database
    for date, mood in data:
        if mood in mood_counts[date]:
            mood_counts[date][mood] += 1

    return jsonify(mood_counts)

@app.route("/history", methods=["GET"])
def get_chat_history():
    with sqlite3.connect("chatbot.db") as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_message, bot_reply, mood FROM chat_history ORDER BY timestamp ASC LIMIT 20"
        )
        chats = cursor.fetchall()

    return jsonify(
        [
            {"user_message": chat[0], "bot_reply": chat[1], "mood": chat[2]}
            for chat in chats
        ]
    )

@app.route("/clear", methods=["POST"])
def clear_chat():
    with sqlite3.connect("chatbot.db") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_history")
        conn.commit()

    return jsonify({"status": "Chat history cleared!"})

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
