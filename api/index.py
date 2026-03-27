import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request
import hashlib
import re
import time
from datetime import datetime, timedelta

# ==========================================
# ⚙️ ការកំណត់ទូទៅ (Configurations)
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "1248955830").strip()
SECRET_SALT = os.getenv("SECRET_SALT", "MSL_FARM_SUPER_SECRET")

# 💳 ព័ត៌មានគណនីរបស់បង
BAKONG_ACCOUNT = "monsela@aclb" 
ACCOUNT_NAME = "MSL FARM"

# 🖼️ Link រូប QR របស់បង
QR_IMAGE_URL = "https://i.postimg.cc/cHCpJ78K/IMG-1872.jpg"

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

# ==========================================
# 🛡️ Database បណ្តោះអាសន្ន (In-Memory)
# ==========================================
waiting_buyers = {} 
pending_activations = {}

# ==========================================
# មុខងារបង្កើត KEY
# ==========================================
def generate_license_key(hwid, days):
    if days > 10000:
        exp_date = datetime.now() + timedelta(days=36500)
    else:
        exp_date = datetime.now() + timedelta(days=days)

    exp_str = exp_date.strftime("%Y%m%d")
    raw_string = hwid + exp_str + SECRET_SALT
    hash_str = hashlib.md5(raw_string.encode()).hexdigest().upper()
    return f"{hash_str[:4]}-{hash_str[4:8]}-{hash_str[8:12]}-{exp_str}", exp_date.strftime("%d-%m-%Y")

def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🛒 ទិញ License"),
        KeyboardButton("📁 ឆែក License"),
        KeyboardButton("🔄 Reset HWID"),
        KeyboardButton("🆘 ជំនួយ (Support)")
    )
    return markup

# ==========================================
# BOT HANDLERS សម្រាប់ឆាតផ្ទាល់ខ្លួន (Private)
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if message.chat.type != 'private': return 
    
    bot.send_message(
        message.chat.id,
        f"សួស្តី {message.from_user.first_name}! 👋\nសូមស្វាគមន៍មកកាន់ MSL FARM AUTO STORE។",
        reply_markup=main_menu()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_buy_callback(call):
    parts = call.data.split('_')
    days = int(parts[1])
    price = float(parts[2])
    
    price_str = str(price)

    if price_str not in waiting_buyers:
        waiting_buyers[price_str] = []
    
    # ការពារកុំឱ្យ User ម្នាក់ចុះឈ្មោះរង់ចាំច្រើនដងក្នុងទឹកលុយតែមួយ
    waiting_buyers[price_str] = [u for u in waiting_buyers[price_str] if u['user_id'] != call.message.chat.id]
    waiting_buyers[price_str].append({"user_id": call.message.chat.id, "days": days})

    bot.answer_callback_query(call.id, "កំពុងរៀបចំវិក្កយបត្រ...")

    # 📝 សារវិក្កយបត្រថ្មី បន្ថែមការដាស់តឿនរឿងទឹកលុយ
    invoice_text = f"""
🧾 **វិក្កយបត្រ (Invoice)**
-------------------
📦 **កញ្ចប់:** 💎 {days} ថ្ងៃ
💵 **ត្រូវបង់ប្រាក់:** **${price:.2f}**

🏦 **សូម Scan QR ឬផ្ទេរប្រាក់មកគណនីខាងក្រោម៖**
👉 គណនី: `{BAKONG_ACCOUNT}`
👤 ឈ្មោះ: **{ACCOUNT_NAME}**

⚠️ **បញ្ជាក់សំខាន់ (សូមអាន)៖** 
១. សូមផ្ទេរប្រាក់ឱ្យ **ត្រូវចំចំនួនទឹកលុយ ${price:.2f} ខាងលើបេះបិទ**។
២. បើផ្ទេរខ្វះ ឬលើស សូម្បីតែបន្តិច ប្រព័ន្ធនឹង **មិនទម្លាក់ Key ឱ្យអូតូទេ**។
៣. ប្រព័ន្ធនឹងឆែកមើលទឹកលុយ និងទម្លាក់ Key ឱ្យអូតូភ្លាមៗ នៅពេលលុយចូលដល់គណនី!
"""
    try:
        bot.send_photo(call.message.chat.id, photo=QR_IMAGE_URL, caption=invoice_text, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(call.message.chat.id, invoice_text, parse_mode="Markdown")

# ==========================================
# 🔎 HANDLER ចាប់ទឹកលុយអូតូក្នុង GROUP 
# ==========================================
@bot.message_handler(content_types=['text'])
def handle_all_text(message):
    text = message.text
    chat_id = str(message.chat.id)

    # ១. ចាប់សារបង់លុយក្នុង Group (PayWay / Bakong Notification)
    if message.chat.type in ['group', 'supergroup']:
        # ចាប់យកទម្រង់ "$0.50 paid by..." ឬ "$7.00 paid by..."
        match = re.search(r'\$([0-9\.]+)\s+paid by', text, re.IGNORECASE)
        if match:
            amount_str = str(float(match.group(1))) # បំប្លែង "0.50" ទៅជា "0.5" ដើម្បីផ្ទៀងផ្ទាត់
            
            if amount_str in waiting_buyers and len(waiting_buyers[amount_str]) > 0:
                customer = waiting_buyers[amount_str].pop(0) # យកភ្ញៀវដែលបានចុចទិញមុនគេមកចាត់ការ
                user_id = customer['user_id']
                days = customer['days']
                
                pending_activations[str(user_id)] = {"days": days, "step": "waiting_hwid"}
                
                bot.reply_to(message, f"✅ ចាប់បានទឹកលុយ **${amount_str}**!\nប្រព័ន្ធបាន Approve អូតូឱ្យអតិថិជនរួចរាល់។", parse_mode="Markdown")
                
                # បាញ់សារទៅភ្ញៀវក្នុង Private Chat
                bot.send_message(
                    user_id,
                    f"✅ **ការបង់ប្រាក់ ${amount_str} ទទួលបានជោគជ័យ!**\n\n👉 **សូម Copy Device ID (HWID)** ពីក្នុងកម្មវិធីរបស់អ្នក រួច Paste ចូលមកក្នុងឆាតនេះ ដើម្បីទទួលបាន Key:",
                    parse_mode="Markdown"
                )
        return

    # ២. ការឆ្លើយតបក្នុង Private Chat (Menu & HWID)
    if text == "🛒 ទិញ License":
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("🆕 7 ថ្ងៃ (0.50$)", callback_data="buy_7_0.5"),
            InlineKeyboardButton("💎 1 ខែ (7.00$)", callback_data="buy_30_7.0"),
            InlineKeyboardButton("🔥 3 ខែ (18.00$)", callback_data="buy_90_18.0"),
            InlineKeyboardButton("🚀 6 ខែ (35.00$)", callback_data="buy_180_35.0"),
            InlineKeyboardButton("👑 LIFETIME (99.99$)", callback_data="buy_36500_99.99")
        )
        bot.send_message(message.chat.id, "🛒 **សូមជ្រើសរើសកញ្ចប់៖**", reply_markup=markup, parse_mode="Markdown")

    elif text == "🆘 ជំនួយ (Support)":
        bot.send_message(message.chat.id, f"👨‍💻 សម្រាប់ជំនួយ សូមទាក់ទងមកកាន់ Admin: @Mon_Sela")

    elif text in ["📁 ឆែក License", "🔄 Reset HWID"]:
        bot.send_message(message.chat.id, "មុខងារនេះតម្រូវឱ្យទាក់ទង Admin ផ្ទាល់។")
        
    else:
        # បើភ្ញៀវបង់លុយរួច ហើយកំពុងដាក់ HWID
        if chat_id in pending_activations and pending_activations[chat_id].get("step") == "waiting_hwid":
            hwid = text.upper().strip()
            days = pending_activations[chat_id]["days"]
            
            msg_wait = bot.send_message(message.chat.id, "⏳ កំពុង Generate License Key...")
            try:
                key, expire_date = generate_license_key(hwid, days)
                del pending_activations[chat_id] 
                
                bot.delete_message(message.chat.id, msg_wait.message_id)
                success_text = f"🎉 **សូមអបអរសាទរ!**\n\n🔑 **License Key របស់អ្នកគឺ:**\n`{key}`\n\n⏳ **ផុតកំណត់នៅ:** {expire_date}\n\n👉 សូម Copy Key នេះយកទៅដាក់ក្នុងកម្មវិធីរបស់អ្នក។"
                bot.send_message(message.chat.id, success_text, parse_mode="Markdown")
                
                # ប្រាប់ Admin
                bot.send_message(ADMIN_ID, f"✅ បាន Generate Key ឱ្យអតិថិជនម្នាក់រួចរាល់! ({days} ថ្ងៃ)")
            except Exception as e:
                bot.send_message(message.chat.id, f"⚠️ មានបញ្ហាពេលបង្កើត Key: {e}")

# ==========================================
# 🌐 FLASK WEBHOOK ROUTES សម្រាប់ VERCEL 
# ==========================================
@app.route('/', methods=['POST', 'GET'])
def index_route():
    if request.method == 'POST':
        try:
            json_string = request.get_data().decode('utf-8')
            update = telebot.types.Update.de_json(json_string)
            bot.process_new_updates([update])
            return "OK", 200
        except Exception as e:
            return "Server Error", 500
    else:
        return "✅ MSL Auto Bot (Group Listener) ដំណើរការយ៉ាងរលូន!", 200

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook_token():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        return "Error", 500
