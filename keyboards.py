#keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from database import db
from config import BOT_USERNAME # <--- إضافة هذا السطر

# --- Keyboards for Users ---

def start_keyboard():
    keyboard = [
        [InlineKeyboardButton("🛍️ تصفح الخدمات", callback_data="show_categories")],
        [InlineKeyboardButton("🌐 فتح الخدمات (متطور)", web_app={"url": f"https://flasksssss.onrender.com/?user_id={{user_id}}" })], # <--- إضافة هذا الزر
        [InlineKeyboardButton("💰 شحن الرصيد", callback_data="recharge_balance")],
        [InlineKeyboardButton("👤 حسابي", callback_data="my_account")]
    ]
    return InlineKeyboardMarkup(keyboard)

def categories_keyboard(categories, current_parent_id=None):
    buttons = []
    for cat_id, name in categories:
        buttons.append([InlineKeyboardButton(name, callback_data=f"browse_cat_{cat_id}")])
    
    # زر الرجوع للفئة الأم أو القائمة الرئيسية
    if current_parent_id is not None:
        # إذا كان هناك فئة أم، نعود إليها
        parent_of_current = db.get_category_parent_id(current_parent_id)
        if parent_of_current is not None:
            buttons.append([InlineKeyboardButton("🔙 رجوع للفئة الأم", callback_data=f"browse_cat_{parent_of_current}")])
        else:
            # إذا كانت الفئة الحالية ليس لها أم (أي هي فئة رئيسية)، نعود لقائمة الخدمات الرئيسية
            buttons.append([InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="show_categories")])
    
    # زر إلغاء (في بعض السياقات مثل إضافة/تعديل منتج)
    # هذا الزر قد يكون مفيدًا إذا تم استدعاء هذه الكيبورد من سياق يتطلب إلغاء العملية
    # buttons.append([InlineKeyboardButton("إلغاء", callback_data="cancel_action")]) 
    
    return InlineKeyboardMarkup(buttons)

def products_keyboard(products, category_id):
    buttons = []
    for prod_id, name, _, price, items_per_unit, _, _, is_available in products:
        status_emoji = "✅" if is_available else "⛔"
        buttons.append([InlineKeyboardButton(f"{status_emoji} {name} ({price:.2f}$/{items_per_unit})", callback_data=f"show_product_{prod_id}")])
    
    # زر الرجوع للفئة الأم
    parent_of_category = db.get_category_parent_id(category_id) # <--- هنا كان الخطأ
    if parent_of_category is not None:
        buttons.append([InlineKeyboardButton("🔙 رجوع للفئة الأم", callback_data=f"browse_cat_{parent_of_category}")])
    else:
        buttons.append([InlineKeyboardButton("🔙 رجوع للفئات الرئيسية", callback_data="show_categories")])

    return InlineKeyboardMarkup(buttons)

def product_detail_keyboard(product_id, is_available):
    buttons = []
    if is_available:
        buttons.append([InlineKeyboardButton("🛒 شراء الآن", callback_data=f"buy_product_{product_id}")])
    else:
        buttons.append([InlineKeyboardButton("غير متوفر حالياً ❌", callback_data="unavailable_product")])
    
    buttons.append([InlineKeyboardButton("🔙 العودة للمنتجات", callback_data=f"back_to_products_from_detail_{product_id}")])
    return InlineKeyboardMarkup(buttons)


def my_account_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 عرض طلباتي", callback_data="view_my_orders")],
        [InlineKeyboardButton("💰 شحن الرصيد", callback_data="recharge_balance")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="start_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def recharge_method_keyboard(payment_methods_config):
    buttons = []
    for key, method_info in payment_methods_config.items():
        buttons.append([InlineKeyboardButton(method_info['name'], callback_data=f"select_recharge_method_{key}")])
    buttons.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="start_menu")])
    return InlineKeyboardMarkup(buttons)

def confirm_purchase_keyboard(product_id):
    keyboard = [
        [InlineKeyboardButton("✅ تأكيد الشراء", callback_data=f"confirm_purchase_{product_id}")],
        [InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_purchase_{product_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Keyboards for Admins ---

def admin_main_menu_inline_keyboard():
    keyboard = [
        [InlineKeyboardButton("🛍️ إدارة الخدمات والفئات", callback_data="admin_products_categories_menu")],
        [InlineKeyboardButton("📝 إدارة الطلبات", callback_data="admin_orders_menu")],
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users_menu")],
        [InlineKeyboardButton("💰 إدارة شحن الرصيد", callback_data="admin_recharge_requests_menu")],
        [InlineKeyboardButton("🗄️ نسخ احتياطي واستعادة", callback_data="admin_backup_restore_menu")],
        [InlineKeyboardButton("🚪 خروج من لوحة الإدارة", callback_data="admin_exit")]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_products_categories_menu_inline():
    keyboard = [
        [InlineKeyboardButton("➕ إضافة فئة جديدة", callback_data="admin_add_category")],
        [InlineKeyboardButton("🗑️ حذف فئة", callback_data="admin_delete_category")],
        [InlineKeyboardButton("➕ إضافة خدمة جديدة", callback_data="admin_add_product")],
        [InlineKeyboardButton("✏️ تعديل خدمة", callback_data="admin_edit_product")],
        [InlineKeyboardButton("🗑️ حذف خدمة", callback_data="admin_delete_product")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية للمدير", callback_data="admin_main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_orders_menu_inline():
    keyboard = [
        [InlineKeyboardButton("عرض جميع الطلبات", callback_data="admin_view_all_orders")],
        [InlineKeyboardButton("تغيير حالة طلب", callback_data="admin_change_order_status")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية للمدير", callback_data="admin_main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_users_menu_inline():
    keyboard = [
        [InlineKeyboardButton("عرض جميع المستخدمين", callback_data="admin_view_all_users")],
        [InlineKeyboardButton("البحث عن مستخدم", callback_data="admin_search_user")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية للمدير", callback_data="admin_main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_recharge_requests_menu_inline():
    keyboard = [
        [InlineKeyboardButton("عرض طلبات الشحن المعلقة", callback_data="admin_view_pending_recharge")],
        [InlineKeyboardButton("إدارة طلبات الشحن", callback_data="admin_manage_recharge_request")],
        [InlineKeyboardButton("إضافة رصيد يدوي", callback_data="admin_add_balance_manually")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية للمدير", callback_data="admin_main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_manage_recharge_status_keyboard(request_id):
    keyboard = [
        [InlineKeyboardButton("✅ اعتماد الطلب", callback_data=f"admin_approve_recharge_{request_id})")],
        [InlineKeyboardButton("❌ رفض الطلب", callback_data=f"admin_reject_recharge_{request_id}")],
        [InlineKeyboardButton("🔙 لإدارة طلبات الشحن", callback_data="admin_recharge_requests_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_backup_restore_menu_inline():
    keyboard = [
        [InlineKeyboardButton("إنشاء نسخة احتياطية", callback_data="admin_create_backup")],
        [InlineKeyboardButton("استعادة نسخة احتياطية", callback_data="admin_restore_backup")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية للمدير", callback_data="admin_main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_cancel_inline_button():
    keyboard = [
        [InlineKeyboardButton("❌ إلغاء", callback_data="admin_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_product_edit_select_field():
    keyboard = [
        [InlineKeyboardButton("الاسم", callback_data="edit_prod_name"),
         InlineKeyboardButton("الوصف", callback_data="edit_prod_description")],
        [InlineKeyboardButton("السعر", callback_data="edit_prod_price"),
         InlineKeyboardButton("الكمية/الوحدة", callback_data="edit_prod_items_per_unit")],
        [InlineKeyboardButton("الفئة", callback_data="edit_prod_category"),
         InlineKeyboardButton("رابط الصورة", callback_data="edit_prod_image_url")],
        [InlineKeyboardButton("حالة التوفر", callback_data="edit_prod_is_available")],
        [InlineKeyboardButton("🔙 لإدارة الخدمات", callback_data="admin_products_categories_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_confirm_restore_keyboard():
    keyboard = [
        [InlineKeyboardButton("✅ تأكيد الاستعادة", callback_data="admin_confirm_restore")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="admin_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_password_inline_keyboard():
    keyboard = [
        [InlineKeyboardButton("إلغاء الدخول", callback_data="admin_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_set_availability_keyboard(product_id=None):
    target_id = product_id if product_id is not None else 'new'
    
    keyboard = [
        [InlineKeyboardButton("✅ متوفر", callback_data=f"set_prod_available_{target_id}_1")],
        [InlineKeyboardButton("❌ غير متوفر", callback_data=f"set_prod_available_{target_id}_0")],
        [InlineKeyboardButton("إلغاء", callback_data="admin_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)
