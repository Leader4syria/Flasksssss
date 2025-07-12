#config.py
import datetime

BOT_TOKEN = "7058414712:AAGtGYTdZG7KmZ0dym_YXfb724vfVoXCYng"
ADMIN_ID = [7721705352] # معرف (أو معرفات) مدير البوت. استبدله بمعرفك الحقيقي
DB_NAME = "store_bot.db" # اسم ملف قاعدة البيانات SQLite
BACKUP_CHANNEL_ID = -1002785826840 # معرف قناة/مجموعة النسخ الاحتياطي

# حالة المستخدم (لإدارة FSM - Finite State Machine)
USER_STATE = {}

# تخزين وقت آخر تسجيل دخول للأدمن
ADMIN_LAST_AUTH_TIME = {}

# كلمات سر للادمن (للوصول للوحة الادمن)
ADMIN_PASSWORD = "AhmadHassoun2009" # قم بتغييرها لكلمة سر قوية
ADMIN_AUTH_EXPIRY_HOURS = 1 # صلاحية تسجيل دخول الأدمن بالساعات (1 ساعة)

# مسارات الملفات للنسخ الاحتياطي
DB_BACKUP_PATH = "backups/store_bot_backup.db"

# --- NEW ADDITIONS / MODIFICATIONS FOR DIGITAL SERVICES ---
CURRENCY_SYMBOL = "$" # رمز العملة
DEFAULT_ITEMS_PER_UNIT = 1000 # قيمة افتراضية لعدد العناصر التي يمثلها السعر (مثلاً: 1000 متابع لكل دولار). يمكنك تغييرها.
BOT_USERNAME = "Qoehdbxugwvdbot"
# تفاصيل طرق الدفع (هذه تحتاج إلى ملئها بمعلوماتك الحقيقية)
PAYMENT_METHODS = {
    "shamcash": {
        "name": "شام كاش (ShamCash)",
        # تم تعديل الـ details لتكون قابلة للتنسيق باستخدام .format()
        "details": "للدفع عبر شام كاش، يرجى التواصل على الرقم التالي: **{account}**. بعد الدفع، أرسل لقطة شاشة للإيصال ومعرف التحويل إلى @{bot_username}. سيتم إضافة رصيدك يدوياً بعد التأكد.",
        "account_info": "+9639XXXXXXXX", # مثال: رقم الهاتف للدفع
        "image_url": "URL_لصورة_شعار_شام_كاش_او_رمز_QR_إذا_وجدت" # اختياري
    },
    "usdt": {
        "name": "تيثر (USDT - TRC20)",
        # تم تعديل الـ details لتكون قابلة للتنسيق باستخدام .format()
        "details": "للدفع عبر USDT (شبكة TRC20)، أرسل المبلغ إلى المحفظة التالية: **{account}**. بعد الإرسال، أرسل Hash العملية (TxID) أو لقطة شاشة للتأكيد إلى @{bot_username}.",
        "account_info": "TXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX", # مثال: عنوان محفظة USDT
        "image_url": "URL_لصورة_رمز_QR_لمحفظة_USDT_إذا_وجدت" # اختياري
    }
}

# رسائل البوت
START_MESSAGE = "أهلاً بك في متجر الخدمات الرقمية! 🚀 يمكنك تصفح خدماتنا أو شحن رصيدك."
ADMIN_WELCOME_MESSAGE = "مرحباً أيها المدير! 👋 لوحة التحكم للخدمات الرقمية."
