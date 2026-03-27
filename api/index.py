import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request
import random
import hashlib
import io
import qrcode
from datetime import datetime, timedelta

try:
    from bakong_khqr.khqr import KHQR
except ImportError:
    KHQR = None

# ==========================================
# ⚙️ ការកំណត់ទូទៅ 
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "1248955830").strip() # ត្រូវប្រាកដថាលេខ ID បងត្រឹមត្រូវក្នុង Vercel
SECRET_SALT = os.getenv("SECRET_SALT", "MSL_FARM_SUPER_SECRET")
MY_BAKONG_TOKEN = os.getenv("MY_BAKONG_TOKEN", "").strip()

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

if MY_BAKONG_TOKEN and KHQR:
    khqr = KHQR(MY_BAKONG_TOKEN)
else:
    khqr = None

# Database បណ្តោះអាសន្ន
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
        if chat_id in pending_activations and pending_activations[chat_id].get("step") == "waiting_hwid":
            hwid = text.upper()
            days = pending_activations[chat_id]["days"]
            
            msg_wait = bot.send_message(message.chat.id, "⏳ កំពុង Generate License Key សូមរង់ចាំ...")
            try:
                key, expire_date = generate_license_key(hwid, days)
                del pending_activations[chat_id] 
                
                bot.delete_message(message.chat.id, msg_wait.message_id)
                success_text = f"🎉 **សូមអបអរសាទរ!**\n\n🔑 **License Key របស់អ្នកគឺ:**\n`{key}`\n\n⏳ **ផុតកំណត់នៅ:** {expire_date}\n\n👉 សូម Copy Key នេះយកទៅដាក់ក្នុងកម្មវិធីរបស់អ្នក។"
                bot.send_message(message.chat.id, success_text, parse_mode="Markdown")
                bot.send_message(ADMIN_ID, f"✅ បាន Generate Key ឱ្យ @{message.from_user.username} រួចរាល់! ({days} ថ្ងៃ)")
            except Exception as e:
                bot.send_message(message.chat.id, f"⚠️ មានបញ្ហាពេលបង្កើត Key: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_buy_callback(call):
    parts = call.data.split('_')
    days = int(parts[1])
    price = float(parts[2])

    bot.answer_callback_query(call.id, "⏳ កំពុងបង្កើត KHQR សម្រាប់អ្នក...")

    if khqr:
        try:
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
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌ Error generating QR: {e}")
            return
    else:
        bot.send_message(call.message.chat.id, "❌ ប្រព័ន្ធបាគងកំពុងមានបញ្ហា សូមទាក់ទង Admin។")
        return

    md5_hash = hashlib.md5(qr_string.encode('utf-8')).hexdigest()
    qr_img = qrcode.make(qr_string)
    bio = io.BytesIO()
    qr_img.save(bio, format="PNG")
    bio.seek(0)

    invoice_text = f"🧾 **វិក្កយបត្រ (Invoice)**\n-------------------\n📦 **រយៈពេល:** 💎 {days} ថ្ងៃ\n💵 **តម្លៃ:** {price}$\n\n📲 **សូម Scan QR ខាងក្រោមដើម្បីបង់ប្រាក់**\n⚠️ *បញ្ជាក់:* បន្ទាប់ពីបង់រួច សូមចុចប៊ូតុង **'✅ ខ្ញុំបានបង់ហើយ'** ខាងក្រោម។"

    markup = InlineKeyboardMarkup()
    # បញ្ជូនព័ត៌មានតម្លៃ និងចំនួនថ្ងៃទៅកាន់ callback បន្ត
    markup.add(InlineKeyboardButton("✅ ខ្ញុំបានបង់ហើយ", callback_data=f"chk_{md5_hash}_{days}_{price}"))

    bot.send_photo(call.message.chat.id, photo=bio, caption=invoice_text, reply_markup=markup, parse_mode="Markdown")


# ==========================================
# 🛡️ ផ្នែក Semi-Auto (អតិថិជនចុចថាបង់រួច ហើយបាញ់សារទៅ Admin)
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('chk_'))
def check_payment(call):
    data_parts = call.data.split('_')
    md5_hash = data_parts[1]
    days = data_parts[2]
    price = data_parts[3]
    user_id = str(call.message.chat.id)
    username = call.from_user.username or call.from_user.first_name

    if md5_hash in used_transactions:
        bot.answer_callback_query(call.id, "វិក្កយបត្រនេះត្រូវបានចាត់ការរួចហើយ!", show_alert=True)
        return
    used_transactions.add(md5_hash)

    # លុបប៊ូតុងចោលកុំឱ្យភ្ញៀវចុចផ្ទួនៗ
    try:
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    except: pass

    # លោតសារប្រាប់ភ្ញៀវឱ្យរង់ចាំ
    bot.send_message(
        call.message.chat.id,
        "⏳ **សូមរង់ចាំបន្តិច!**\n\nប្រព័ន្ធកំពុងរង់ចាំ Admin ពិនិត្យផ្ទៀងផ្ទាត់ប្រាក់ក្នុងកុងបាគង។\n(ជាទូទៅចំណាយពេល 1-5 នាទី)",
        parse_mode="Markdown"
    )
    
    # បាញ់សាររោទ៍ទៅកាន់ Admin 
    admin_text = f"🔔 **មានភ្ញៀវទើបតែទិញកញ្ចប់ថ្មី!**\n👤 ឈ្មោះ: @{username}\n🆔 អត្តសញ្ញាណ: `{user_id}`\n📦 កញ្ចប់: **{days} ថ្ងៃ**\n💵 តម្លៃ: **{price}$**\n\n👉 មេ! សូមចូលទៅឆែកមើល App បាគង បើឃើញលុយចូលមែន សូមចុច [✅ Approve]!"
    markup = InlineKeyboardMarkup()
    # បង្កប់ user_id និង days ទៅក្នុងប៊ូតុង Approve ដើម្បីងាយស្រួលធ្វើការងារបន្ត
    markup.add(
        InlineKeyboardButton("✅ ទទួលស្គាល់ (Approve)", callback_data=f"appr_{user_id}_{days}"),
        InlineKeyboardButton("❌ បដិសេធ (Reject)", callback_data=f"rej_{user_id}")
    )
    try:
        bot.send_message(ADMIN_ID, admin_text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(call.message.chat.id, "⚠️ មិនអាចទាក់ទង Admin បានទេ។ សូមឆាតទៅ Admin ផ្ទាល់។")

# ==========================================
# 👑 មុខងារផ្តាច់មុខសម្រាប់ Admin ចុច Approve / Reject
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data.startswith('appr_') or call.data.startswith('rej_'))
def admin_action(call):
    if str(call.message.chat.id) != str(ADMIN_ID):
        bot.answer_callback_query(call.id, "⚠️ អ្នកមិនមែនជា Admin ទេ!", show_alert=True)
        return

    data = call.data.split('_')
    action = data[0]
    user_id = data[1]

    # លុបប៊ូតុងចេញពីសារ Admin
    try:
        bot.edit_message_reply_markup(ADMIN_ID, call.message.message_id, reply_markup=None)
    except: pass

    if action == "appr":
        days = int(data[2])
        # ចាប់ផ្តើមវគ្គសួររក HWID ពីភ្ញៀវ
        pending_activations[user_id] = {"days": days, "step": "waiting_hwid"}
        
        bot.send_message(ADMIN_ID, f"✅ បាន Approve ឱ្យ User ID: {user_id} រួចរាល់។")
        
        # បាញ់សារទៅភ្ញៀវថា Approve ហើយ
        bot.send_message(
            int(user_id),
            "✅ **ការបង់ប្រាក់ត្រូវបានទទួលស្គាល់! (Approved)**\n\n👉 **សូម Copy Device ID (HWID)** ពីក្នុងកម្មវិធីរបស់អ្នក រួច Paste ចូលមកក្នុងឆាតនេះ ដើម្បីទទួលបាន Key:",
            parse_mode="Markdown"
        )
    elif action == "rej":
        bot.send_message(ADMIN_ID, f"❌ បាន Reject User ID: {user_id} រួចរាល់។")
        bot.send_message(
            int(user_id),
            "❌ **ការបង់ប្រាក់របស់អ្នកត្រូវបានបដិសេធ (Rejected) ដោយ Admin!**\n\nប្រសិនបើមានចម្ងល់ ឬមានការភាន់ច្រឡំ សូមទាក់ទងមកកាន់ @Mon_Sela",
            parse_mode="Markdown"
        )


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
        return "✅ MSL Semi-Auto Bot កំពុងដំណើរការយ៉ាងរលូននៅលើ Vercel!", 200

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook_token():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        return "Error", 500
