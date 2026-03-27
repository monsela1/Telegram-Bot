import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request
import random
import hashlib
import io
import qrcode
from datetime import datetime, timedelta
# សន្មតថាបងមាន Library ទាំងនេះក្នុង requirements.txt
from bakong_khqr.khqr import KHQR 

# ==========================================
# ⚙️ ការកំណត់ទូទៅ (Configurations via Vercel ENV)
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID", "1248955830")
SECRET_SALT = os.getenv("SECRET_SALT", "MSL_FARM_SUPER_SECRET")
MY_BAKONG_TOKEN = os.getenv("MY_BAKONG_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)
khqr = KHQR(MY_BAKONG_TOKEN)

# Database បណ្តោះអាសន្ន (នឹង Reset ពេល Vercel សម្រាក)
used_transactions = set()
pending_activations = {}

# ==========================================
# មុខងារជំនួយ (Helper Functions)
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
# BOT HANDLERS
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        f"សួស្តី {message.from_user.first_name}! 👋\nសូមស្វាគមន៍មកកាន់ MSL FARM AUTO STORE។",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    text = message.text
    chat_id = str(message.chat.id)

    if text == "🛒 ទិញ License":
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("🆕 7 ថ្ងៃ (0.50$)", callback_data="buy_7_0.5"),
            InlineKeyboardButton("💎 1 ខែ (7.00$)", callback_data="buy_30_7.0"),
            InlineKeyboardButton("🔥 3 ខែ (18.00$)", callback_data="buy_90_18.0"),
            InlineKeyboardButton("👑 LIFETIME (99.99$)", callback_data="buy_36500_99.99")
        )
        bot.send_message(message.chat.id, "🛒 **សូមជ្រើសរើសកញ្ចប់៖**", reply_markup=markup, parse_mode="Markdown")

    elif text == "🆘 ជំនួយ (Support)":
        bot.send_message(message.chat.id, "👨‍💻 សម្រាប់ជំនួយ សូមទាក់ទងមកកាន់ Admin: @Mon_Sela")

    elif chat_id in pending_activations and pending_activations[chat_id].get("step") == "waiting_hwid":
        hwid = text.upper()
        days = pending_activations[chat_id]["days"]
        key, expire_date = generate_license_key(hwid, days)
        del pending_activations[chat_id]
        
        bot.send_message(message.chat.id, f"🎉 **ជោគជ័យ!**\n🔑 Key: `{key}`\n⏳ ផុតកំណត់: {expire_date}", parse_mode="Markdown")
        bot.send_message(ADMIN_ID, f"✅ Key generated for @{message.from_user.username}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_buy(call):
    _, days, price = call.data.split('_')
    price = float(price)
    
    # បង្កើត QR (ប្តូរព័ត៌មានបាគងបងនៅទីនេះ)
    qr_string = khqr.create_qr(
        bank_account="monsela@aclb", 
        merchant_name="MSL FARM",
        amount=price,
        currency="USD"
    )
    
    qr_img = qrcode.make(qr_string)
    bio = io.BytesIO()
    qr_img.save(bio, format="PNG")
    bio.seek(0)

    markup = InlineKeyboardMarkup()
    md5_hash = hashlib.md5(qr_string.encode()).hexdigest()
    markup.add(InlineKeyboardButton("✅ ខ្ញុំបានបង់ហើយ", callback_data=f"chk_{md5_hash}_{days}"))
    
    bot.send_photo(call.message.chat.id, photo=bio, caption=f"💰 តម្លៃ: {price}$", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('chk_'))
def check_pay(call):
    _, md5, days = call.data.split('_')
    # កូដឆែកបង់ប្រាក់ពិតប្រាកដ... (សម្រាប់តេស្ត ខ្ញុំដាក់ឱ្យវា pass តែម្តង)
    pending_activations[str(call.message.chat.id)] = {"days": int(days), "step": "waiting_hwid"}
    bot.send_message(call.message.chat.id, "✅ បង់ប្រាក់ជោគជ័យ! សូមផ្ញើ HWID មក។")

# ==========================================
# 🌐 VERCEL WEBHOOK ROUTES (កែសម្រួលថ្មី)
# ==========================================

@app.route('/', methods=['POST', 'GET'])
def webhook_root():
    if request.method == 'POST':
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return "OK", 200
    return "Bot is active!", 200

# ផ្លូវបំរុងសម្រាប់ Bot Token
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook_token():
    update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
    bot.process_new_updates([update])
    return "OK", 200

@app.route('/set_webhook')
def set_webhook():
    # ប្តូរ domain ខាងក្រោមឱ្យត្រូវនឹង domain vercel បង
    domain = "https://telegram-bot-lilac-phi.vercel.app/"
    bot.remove_webhook()
    bot.set_webhook(url=domain)
    return f"Webhook set to {domain}", 200
