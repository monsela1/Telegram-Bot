import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, jsonify
import random
import hashlib
import json
from datetime import datetime, timedelta
from bakong_khqr.khqr import KHQR
import io
import qrcode

# ==========================================
# ⚙️ ការកំណត់ទូទៅ (Configurations via Vercel ENV)
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "ដាក់_TOKEN_បងនៅ_VERCEL_ENV")
ADMIN_ID = os.getenv("ADMIN_ID", "1248955830")
SECRET_SALT = os.getenv("SECRET_SALT", "MSL_FARM_SUPER_SECRET")
MY_BAKONG_TOKEN = os.getenv("MY_BAKONG_TOKEN", "ដាក់_BAKONG_TOKEN_នៅ_VERCEL_ENV")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
khqr = KHQR(MY_BAKONG_TOKEN)

# ==========================================
# 🛡️ ប្រព័ន្ធ Database (ចំណាំសម្រាប់ Vercel)
# ==========================================
# ដោយសារ Vercel មិនរក្សាទុកទិន្នន័យ (Stateless) អថេរខាងក្រោមនឹង Reset ពេល Server Sleep។
# សម្រាប់ការប្រើប្រាស់ជាក់ស្តែង បងត្រូវប្តូរវាទៅប្រើ Database ដូចជា Firebase ឬ Vercel KV។
used_transactions = set()
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

    final_key = f"{hash_str[:4]}-{hash_str[4:8]}-{hash_str[8:12]}-{exp_str}"
    return final_key, exp_date.strftime("%d-%m-%Y")

# ==========================================
# ផ្ទាំង MAIN MENU
# ==========================================
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🛒 ទិញ License"),
        KeyboardButton("📁 ឆែក License"),
        KeyboardButton("🔄 Reset HWID"),
        KeyboardButton("🆘 ជំនួយ (Support)")
    )
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = str(message.chat.id)
    if chat_id in pending_activations:
        del pending_activations[chat_id]

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
        if chat_id in pending_activations:
            del pending_activations[chat_id]
            
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("🆕 7 ថ្ងៃ (0.50$)", callback_data="buy_7_0.50"),
            InlineKeyboardButton("💎 1 ខែ (7.00$)", callback_data="buy_30_7.00"),
            InlineKeyboardButton("🔥 3 ខែ (18.00$)", callback_data="buy_90_18.00"),
            InlineKeyboardButton("🚀 6 ខែ (35.00$)", callback_data="buy_180_35.00"),
            InlineKeyboardButton("👑 LIFETIME (99.99$)", callback_data="buy_36500_99.99")
        )
        bot.send_message(message.chat.id, "🛒 **សូមជ្រើសរើសកញ្ចប់៖**", reply_markup=markup, parse_mode="Markdown")

    elif text == "🆘 ជំនួយ (Support)":
        bot.send_message(message.chat.id, "👨‍💻 សម្រាប់ជំនួយ សូមទាក់ទងមកកាន់ Admin: @Mon_Sela")

    elif text in ["📁 ឆែក License", "🔄 Reset HWID"]:
        bot.send_message(message.chat.id, "មុខងារនេះតម្រូវឱ្យទាក់ទង Admin ផ្ទាល់។")
        
    else:
        # ពិនិត្យមើលថាគាត់កំពុងរង់ចាំដាក់ HWID ឬអត់
        if chat_id in pending_activations and pending_activations[chat_id].get("step") == "waiting_hwid":
            hwid = text.upper()
            days = pending_activations[chat_id]["days"]
            
            msg_wait = bot.send_message(message.chat.id, "⏳ កំពុង Generate License Key សូមរង់ចាំ...")
            try:
                key, expire_date = generate_license_key(hwid, days)
                del pending_activations[chat_id] # លុបចោលវិញពេលធ្វើរួច
                
                bot.delete_message(message.chat.id, msg_wait.message_id)
                success_text = f"🎉 **សូមអបអរសាទរ!**\n\n🔑 **License Key របស់អ្នកគឺ:**\n`{key}`\n\n⏳ **ផុតកំណត់នៅ:** {expire_date}\n\n👉 សូម Copy Key នេះយកទៅដាក់ក្នុងកម្មវិធីរបស់អ្នក។"
                bot.send_message(message.chat.id, success_text, parse_mode="Markdown")
                
                bot.send_message(ADMIN_ID, f"✅ ប្រព័ន្ធ Auto បាន Generate Key ឱ្យ @{message.from_user.username} រួចរាល់! ({days} ថ្ងៃ)")
            except Exception as e:
                bot.send_message(message.chat.id, f"⚠️ មានបញ្ហាពេលបង្កើត Key: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_buy_callback(call):
    parts = call.data.split('_')
    days = int(parts[1])
    price = float(parts[2])

    bot.answer_callback_query(call.id, "⏳ កំពុងបង្កើត KHQR សម្រាប់អ្នក...")

    qr_string = khqr.create_qr(
        bank_account="monsela@aclb", 
        merchant_name="MSL FARM",
        merchant_city="Phnom Penh",
        amount=price,
        currency="USD",
        store_label="MSL FARM",
        phone_number="012345678",
        bill_number=f"TRX{int(random.random()*100000)}",
        terminal_label="BOT",
        static=False
    )

    md5_hash = hashlib.md5(qr_string.encode('utf-8')).hexdigest()

    qr_img = qrcode.make(qr_string)
    bio = io.BytesIO()
    qr_img.save(bio, format="PNG")
    bio.seek(0)

    invoice_text = f"""
🧾 **វិក្កយបត្រ (Invoice)**
-------------------
📦 **រយៈពេល:** 💎 {days} ថ្ងៃ
💵 **តម្លៃ:** {price}$

📲 **សូម Scan QR ខាងក្រោមដើម្បីបង់ប្រាក់**
⚠️ *បញ្ជាក់:* បន្ទាប់ពីបង់រួច សូមចុចប៊ូតុង **'✅ ខ្ញុំបានបង់ហើយ'** ខាងក្រោម។
    """

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ ខ្ញុំបានបង់ហើយ", callback_data=f"chk_{md5_hash}_{days}"))

    try:
        bot.send_photo(call.message.chat.id, photo=bio, caption=invoice_text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ មានបញ្ហា: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('chk_'))
def check_payment(call):
    data_parts = call.data.split('_')
    md5_hash = data_parts[1]
    days = int(data_parts[2])

    if md5_hash in used_transactions:
        bot.answer_callback_query(call.id, "វិក្កយបត្រនេះត្រូវបានប្រើប្រាស់រួចហើយ!", show_alert=True)
        return

    bot.answer_callback_query(call.id, "⏳ កំពុងឆែកមើលប្រវត្តិបង់ប្រាក់ពីបាគងអូតូ...")
    
    try:
        # សាកល្បងឆែកពីបាគង
        status = khqr.check_payment(md5_hash)
        
        if status:
            used_transactions.add(md5_hash) # កត់សម្គាល់ថាបានប្រើហើយ

            try:
                bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            except: pass

            # កត់ត្រាថាភ្ញៀវនេះដល់វគ្គរង់ចាំដាក់ HWID
            chat_id = str(call.message.chat.id)
            pending_activations[chat_id] = {"days": days, "step": "waiting_hwid"}

            bot.send_message(
                call.message.chat.id,
                f"✅ **ការបង់ប្រាក់ជោគជ័យ!**\n\n👉 **សូម Copy Device ID (HWID)** ពីក្នុងកម្មវិធីរបស់អ្នក រួច Paste ចូលមកក្នុងឆាតនេះ ដើម្បីទទួលបាន Key:",
                parse_mode="Markdown"
            )
            bot.send_message(ADMIN_ID, f"✅ ប្រព័ន្ធអូតូទើបតែទទួលបានការបង់ប្រាក់ពីភ្ញៀវ @{call.from_user.username} សម្រាប់កញ្ចប់ {days} ថ្ងៃ។")
        else:
            bot.send_message(
                call.message.chat.id, 
                f"❌ **រកមិនទាន់ឃើញប្រាក់ចូលទេ!**\nប្រសិនបើអ្នកទើបតែបង់រួច សូមរង់ចាំប្រហែល ១៥ វិនាទី រួចចុច Check ម្តងទៀត។"
            )
            
    except Exception as e:
        bot.send_message(call.message.chat.id, f"⚠️ Error ភ្ជាប់ទៅបាគង។ សូមទាក់ទង Admin។")
        print(f"Bakong API Error: {e}")

# ==========================================
# 🌐 FLASK WEBHOOK ROUTES សម្រាប់ VERCEL
# ==========================================

# ផ្លូវនេះគឺសម្រាប់ Telegram បាញ់ Update ចូលមកកាន់ Bot យើង
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

# ផ្លូវនេះសម្រាប់ឱ្យបងងាយស្រួល Set Webhook បន្ទាប់ពី Upload ទៅ Vercel រួច
@app.route("/set_webhook", methods=['GET'])
def webhook():
    bot.remove_webhook()
    # ជំនួស URL នេះជាមួយនឹង Domain ដែល Vercel ផ្តល់អោយបង (ឧ. https://msl-farm-bot.vercel.app)
    app_url = request.url_root.replace("http://", "https://")
    webhook_url = f"{app_url}{BOT_TOKEN}"
    bot.set_webhook(url=webhook_url)
    return f"Webhook is set to: {webhook_url}", 200

# សម្រាប់ឆែកថា Server កំពុងដើរ
@app.route("/")
def index():
    return "Bot is running perfectly on Vercel!", 200

