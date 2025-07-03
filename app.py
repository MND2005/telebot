import telebot
import time
import google.generativeai as genai
import firebase_admin
from firebase_admin import credentials, firestore
import os
import json
import random
import requests
from io import BytesIO
from PIL import Image



# Set API keys
TELEGRAM_BOT_TOKEN = "7347334702:AAHICtIm3cpnugHTyNFW8YOCMLGzztkBog0"
GEMINI_API_KEY = "AIzaSyAJohSYe5H_SOW-g52ARBTC9Z72bM1RUIw"
ADMIN_ID = 1908056692

# Initialize Telegram bot
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Initialize Gemini AI
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# Initialize Firebase
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()



# JSON files
USERS_FILE = "users.json"
MESSAGES_FILE = "messages.json"
BANNED_USERS_FILE = "banned_users.json"



# ---------------- Helper Functions ----------------

def load_banned_users():
    """Load the list of banned users."""
    return load_json(BANNED_USERS_FILE)

def save_banned_users(banned_users):
    """Save the banned users list to a JSON file."""
    save_json(BANNED_USERS_FILE, banned_users)

def is_user_banned(user_id):
    """Check if the user is banned."""
    banned_users = load_banned_users()
    return str(user_id) in banned_users



def load_json(filename):
    """Load JSON data from a file safely."""
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as file:
            try:
                data = json.load(file)
                return data if data else {}  # Return empty dict if data is empty
            except json.JSONDecodeError:
                return {}  # Return empty dict if JSON is invalid
    return {}  # Return empty dict if file doesn't exist

def save_to_firestore(user_id, user_input, ai_response, image_url=None):
    """Save user inputs and AI responses to Firestore with first name."""

    # Fetch user details from Firestore
    user_ref = db.collection("users").document(str(user_id))
    user_doc = user_ref.get()

    if user_doc.exists:
        user_data = user_doc.to_dict()
        first_name = user_data.get("first_name", "Unknown")  # Default to "Unknown" if not found
    else:
        first_name = "Unknown"

    # Save data with first name
    data = {
        "user_id": user_id,
        "first_name": first_name,
        "user_input": user_input,
        "ai_response": ai_response,
        "image_url": image_url,
        "timestamp": firestore.SERVER_TIMESTAMP
    }
    db.collection("ai_responses").add(data)

def save_json(filename, data):
    """Save data as JSON, handling non-serializable objects."""
    def convert(obj):
        if isinstance(obj, set):
            return list(obj)  # Convert sets to lists
        return str(obj)  # Convert Sentinel and other objects to strings

    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False, default=convert)

def register_user(user_id, first_name, username):
    """Register user in Firestore and users.json if not banned."""
    if is_user_banned(user_id):
        return  # Do not register banned users

    user_id = str(user_id)
    users = load_json(USERS_FILE)

    if user_id not in users:
        user_data = {
            "user_id": user_id,
            "first_name": first_name,
            "username": username or "No username",
            "timestamp": firestore.SERVER_TIMESTAMP
        }
        users[user_id] = user_data
        save_json(USERS_FILE, users)  # Save locally

        # Save to Firestore
        db.collection("users").document(user_id).set(user_data)



def save_message(user_id, user_input, ai_response):
    """Save messages to messages.json file."""
    messages = load_json(MESSAGES_FILE)

    message_data = {
        "user_id": str(user_id),
        "user_input": user_input,
        "ai_response": ai_response,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    if user_id not in messages:
        messages[user_id] = []

    messages[user_id].append(message_data)
    save_json(MESSAGES_FILE, messages)

def ask_gemini(text, image=None):
    """Generate AI response using Gemini AI."""
    try:
        if image:
            response = model.generate_content([text, image])
        else:
            response = model.generate_content(text)
        return response.text if response else "Sorry, I couldn't generate a response."
    except Exception as e:
        return f"Error: {str(e)}"


# ---------------- Telegram Bot Handlers ----------------

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username or "No username"

    # Register the user
    register_user(user_id, first_name, username)

    welcome_text = (
        "👋 Welcome to MND AI Bot!\n\n"
        "📌 Send me a text, and I'll generate a response.\n"
        "📷 Send me an image with a question, and I'll analyze it.\n\n"
        "📌User Guidance\n\n"
        "ඔබට පවතින ගැටලුව type කිරීමෙන් හෝ Image ආකාරයෙන් හෝ Bot වෙත යොමු කිරීමෙන් පිළිතුරක් ලැබෙනු ඇත."
        "වෙනත් file ආකාර ඇතුළත් කිරීමෙන් ඔබට පිළිතුරු නොලැබෙනු ඇත.\n"
        "ඔබ විෂය භාහිර ප්‍රශ්න Bot වෙත දිගින් දිගටම යොමු කිරීම ඔබව Ban වීමට හේතුවක් විය හැක..\n\n"
        " Join our support group ; https://t.me/+gkCUG7jni6I3YjI1 \n\n"
        "Enjoy! 🚀\nPowered by Manuja Niroshan 😎"
        '\n\n❗️Warning❗️: මෙහි එන අන්තර්ගතයන් කෘතිම බුද්ධි වැඩසටහනක් මගින් සකසා ඇති බැවින් ඒවායේ නිරවද්‍යතාව 100% යැයි තහවුරු කළ නොහැක..'
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['ban'])
def ban_user(message):
    """Ban a user (Admin only)."""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Access Denied!\n\nYou are banned from using this bot due to a violation of our rules.")
        return

    try:
        _, user_id = message.text.split()
        banned_users = load_banned_users()
        banned_users[user_id] = {"banned_by": ADMIN_ID, "reason": "Violation of rules"}
        save_banned_users(banned_users)

        bot.reply_to(message, f"✅ User {user_id} has been banned.")
    except:
        bot.reply_to(message, "⚠️ Invalid usage. Use: /ban <user_id>")


@bot.message_handler(commands=['unban'])
def unban_user(message):
    """Unban a user (Admin only)."""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Access Denied!\n\nYou are banned from using this bot due to a violation of our rules.")
        return

    try:
        _, user_id = message.text.split()
        banned_users = load_banned_users()

        if user_id in banned_users:
            del banned_users[user_id]
            save_banned_users(banned_users)
            bot.reply_to(message, f"✅ User {user_id} has been unbanned.")
        else:
            bot.reply_to(message, "⚠️ User is not banned.")
    except:
        bot.reply_to(message, "⚠️ Invalid usage. Use: /unban <user_id>")





@bot.message_handler(content_types=['photo'])
def handle_images(message):
    user_id = message.from_user.id

    # Check if user is banned
    if is_user_banned(user_id):
        bot.reply_to(message, "❌ Access Denied!\n\nYou are banned from using this bot due to a violation of our rules.")
        return

    # Register user
    first_name = message.from_user.first_name
    username = message.from_user.username or "No username"
    register_user(user_id, first_name, username)

    # Download image
    file_info = bot.get_file(message.photo[-1].file_id)
    file = bot.download_file(file_info.file_path)
    image = Image.open(BytesIO(file))

    # Check caption
    caption = message.caption.strip().lower() if message.caption else ""

    print("Caption:", caption)  # Debug

    if caption == "/identify":
        prompt = (
            "මෙම පින්තූරය විශ්ලේෂණය කර එය සත්ත්වයකු හෝ वनස්පතියෙකු නම් කරන්න. "
            "පහත විස්තර සිංහල භාෂාවෙන් ලබාදෙන්න:\n\n"
            "📸 නම (සාමාන්‍ය නම)\n"
            "🔬 විද්‍යාත්මක නම (Scientific Name)\n"
            "🧬 පවුල (Family)\n"
            "🌿 වාසස්ථානය (Habitat)\n"
            "🍽️ ආහාර පුරුද්ද\n"
            "🧠 හැසිරීමේ රටාවන්\n"
            "❤️ පරිසරය තුළ වැදගත්කම\n"
            "🚨 ආරක්ෂණ තත්ත්වය (Conservation Status)\n\n"
            "ඊට අමතරව, සිංහල භාෂාවෙන් පැරැග්‍රාෆයක් ලෙස විස්තරාත්මක විවරණයක් ලබාදෙන්න.do not bold any text and add these imojies"
        )
    else:
        prompt = (
            "Analyze the question, solve it, and give the explanation and answer in Sinhala language..do not bold any text "
        )

    try:
        response = ask_gemini(prompt, image)
        powered_message = response + "\n\n🚀 Powered by Manuja Niroshan 😎" + \
            '\n\n```❗️Warning❗: This content was generated by AI.```'



        bot.reply_to(message, powered_message,parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"⚠️ Error processing image: {str(e)}")





















@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id

    if is_user_banned(user_id):
        bot.reply_to(message, "❌ Access Denied!\n\nYou are banned from using this bot due to a violation of our rules.")
        return

    first_name = message.from_user.first_name
    username = message.from_user.username or "No username"

    register_user(user_id, first_name, username)

    response = ask_gemini(message.text)
    powered_message = response + "\n\n🚀 Powered by Manuja Niroshan 😎" +         '\n```❗️Warning❗️: This content was generated by AI.```'



    bot.reply_to(message, powered_message,parse_mode="Markdown")








# ---------------- Start the bot ----------------

print("Bot is running...")
bot.polling(none_stop=True)
