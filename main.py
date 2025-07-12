#main.py
import threading
from flask import Flask, jsonify, render_template, request
import sqlite3
import os

app = Flask(__name__)
DATABASE = 'store_bot.db'
bzbzhzz
def get_db_connection(): # <--- تم تغيير اسم الدالة لتجنب تضارب محتمل مع متغير `db`
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/categories')
def get_categories():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM categories WHERE parent_id IS NULL")
    return jsonify([dict(row) for row in cur.fetchall()])

@app.route('/subcategories')
def get_subcategories():
    parent_id = request.args.get('parent_id')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM categories WHERE parent_id = ?", (parent_id,))
    return jsonify([dict(row) for row in cur.fetchall()])

@app.route('/services')
def get_services():
    subcategory_id = request.args.get('subcategory_id')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, price FROM products WHERE category_id = ? AND is_available = 1", (subcategory_id,))
    return jsonify([dict(row) for row in cur.fetchall()])

@app.route('/user_data') # <--- إضافة هذا المسار الجديد
def get_user_data():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # جلب الرصيد
    cur.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    user_balance_row = cur.fetchone()
    balance = user_balance_row[0] if user_balance_row else 0.0

    # جلب المبلغ المنفق (مجموع الـ total_amount من الطلبات المكتملة أو جميعها)
    # هنا نفترض أنك تريد المبلغ المنفق على جميع الطلبات لهذا المستخدم
    cur.execute("SELECT SUM(total_amount) FROM orders WHERE user_id = ? AND status = 'completed'", (user_id,)) # <--- يمكن تعديل status
    amount_spent_row = cur.fetchone()
    amount_spent = amount_spent_row[0] if amount_spent_row and amount_spent_row[0] is not None else 0.0
    
    return jsonify({
        "user_id": user_id,
        "balance": balance,
        "amount_spent": amount_spent
    })

def run_flask():
    app.run(host='0.0.0.0', port=21155)


flask_thread = threading.Thread(target=run_flask)
flask_thread.start()

#main.py
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
# استيراد من config.py
from config import BOT_TOKEN, ADMIN_ID, USER_STATE, DEFAULT_ITEMS_PER_UNIT, BOT_USERNAME # DEFAULT_ITEMS_PER_UNIT لم تُستخدم هنا ولكن لا بأس بوجودها
# استيراد معالجات المستخدمين
from user_handlers import start, handle_callback_query, handle_text_messages, error_handler
# استيراد معالجات المدير
from admin_handlers import (
    admin_start,
    # admin_main_menu_handler, # هذا لم يُستخدم في الكود المقدم، لذا سأبقي عليه كتعليق لتجنب أخطاء الاستيراد غير الضرورية
    admin_handle_admin_text_input,
    admin_handle_callback_query,
    set_user_start_handler # هذا مهم لكي يتمكن المدير من العودة لقائمة المستخدمين
)
# استيراد من database.py
from database import db # تم استيراده ولكن لم يُستخدم مباشرة في main.py، لا بأس بذلك
# استيراد من keyboards.py مع تصحيح 'main_menu_inline_keyboard'
from keyboards import (
    start_keyboard, # هذا هو الكيبورد الرئيسي للمستخدمين
    admin_cancel_inline_button,
    # باقي لوحات مفاتيح المدير التي قد تحتاجها بشكل مباشر هنا (إن وجدت)، وإلا فاستيرادها في admin_handlers يكفي
    # على سبيل المثال: admin_main_menu_inline_keyboard
)


# --- بداية تعديل إعدادات التسجيل ---
logging.basicConfig(
    filename='error.log', # <--- تم تحديد ملف السجل هنا
    filemode='a',         # <--- تم تعيين الوضع للإلحاق (append) بدلاً من الكتابة فوقه (overwrite)
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO    # <--- يمكن تغيير هذا إلى logging.ERROR لتسجيل الأخطاء فقط، أو تركه INFO للرؤية العامة
)
logger = logging.getLogger(__name__)

# خفض مستوى تسجيل httpx لتقليل الإخراج
logging.getLogger("httpx").setLevel(logging.WARNING)
# --- نهاية تعديل إعدادات التسجيل ---

async def main_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # توجيه التحديثات بناءً على حالة المستخدم وما إذا كان أدمن
    # الأولوية لحالات الأدمن إذا كان المستخدم أدمن وفي حالة أدمن
    if user_id in ADMIN_ID and user_id in USER_STATE and USER_STATE.get(user_id, "").startswith("ADMIN_"):
        # التعامل مع أوامر المدير (نصوص أو مستندات أو كولباكات)
        if update.callback_query:
            await admin_handle_callback_query(update, context)
        elif update.message and (update.message.text or update.message.document):
            await admin_handle_admin_text_input(update, context)
        else:
            # رسالة لأي نوع رسالة غير نصية أو مستند في وضع الأدمن
            if update.message:
                await update.message.reply_text("عذراً، أنا أنتظر نصاً أو ملف قاعدة بيانات منك في وضع الأدمن.", reply_markup=admin_cancel_inline_button())

    else: # تحديثات المستخدم العادي
        if update.callback_query:
            await handle_callback_query(update, context)
        elif update.message and update.message.text:
            await handle_text_messages(update, context)
        elif update.message: # إذا كانت رسالة وليست نص (مثل صورة أو فيديو)
            await update.message.reply_text("عذراً، يرجى استخدام الأزرار في القائمة الرئيسية.", reply_markup=start_keyboard()) # استخدام start_keyboard

def main():
    """تشغيل البوت."""
    application = Application.builder().token(BOT_TOKEN).build()

    # قم بتمرير دالة start الخاصة بالمستخدمين إلى admin_handlers
    # هذا يسمح للمدير بالعودة إلى قائمة المستخدم العادية بعد الخروج من لوحة الإدارة
    set_user_start_handler(start)

    # إضافة معالج الأخطاء العام
    # هذا المعالج هو المكان الذي يجب أن يتم فيه تسجيل الأخطاء باستخدام logger.error()
    application.add_error_handler(error_handler)

    # معالج أمر /start للمستخدمين العاديين (يستخدم دالة start من user_handlers)
    application.add_handler(CommandHandler("start", start))

    # معالج أمر /admin للمديرين (يستخدم دالة admin_start من admin_handlers)
    application.add_handler(CommandHandler("admin", admin_start, filters=filters.User(ADMIN_ID)))

    # معالج شامل لجميع الرسائل النصية والـ Callbacks وأي تحديثات أخرى
    # يتم استخدام main_handler لتوجيه الرسائل بناءً على نوعها وحالة المستخدم
    # هنا، يجب أن نتأكد أن main_handler لا يعالج أوامر /start و /admin مرة أخرى لتجنب الازدواجية
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, main_handler))
    application.add_handler(CallbackQueryHandler(main_handler))


    logger.info("البوت يعمل...") # هذه الرسالة ستذهب أيضاً إلى error.log لأنها INFO
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
