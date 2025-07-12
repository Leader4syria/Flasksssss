#admin_handlers.py
import shutil
import os
import sqlite3
import datetime
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from config import ADMIN_ID, ADMIN_WELCOME_MESSAGE, ADMIN_PASSWORD, USER_STATE, DB_NAME, DB_BACKUP_PATH, BACKUP_CHANNEL_ID, ADMIN_LAST_AUTH_TIME, ADMIN_AUTH_EXPIRY_HOURS, CURRENCY_SYMBOL, DEFAULT_ITEMS_PER_UNIT # تم التأكد من وجود DEFAULT_ITEMS_PER_UNIT
from keyboards import (
    admin_main_menu_inline_keyboard, admin_products_categories_menu_inline, admin_orders_menu_inline,
    admin_users_menu_inline, admin_backup_restore_menu_inline, admin_cancel_inline_button,
    admin_product_edit_select_field, admin_confirm_restore_keyboard, admin_password_inline_keyboard,
    categories_keyboard, admin_recharge_requests_menu_inline, admin_manage_recharge_status_keyboard,
    admin_set_availability_keyboard
)
from database import db
import logging

logger = logging.getLogger(__name__)

# استيراد دالة start من user_handlers
# سيتم تعيينها لاحقًا لتجنب الاستيراد الدائري
_user_start_handler = None

def set_user_start_handler(handler_func):
    global _user_start_handler
    _user_start_handler = handler_func

# حالات لوحة الادمن (FSM - Finite State Machine)
ADMIN_STATE_AUTH = "ADMIN_AUTH"
ADMIN_STATE_MAIN_MENU = "ADMIN_MAIN_MENU"
ADMIN_STATE_ADD_CATEGORY = "ADMIN_ADD_CATEGORY"
ADMIN_STATE_ADD_CATEGORY_PARENT = "ADMIN_ADD_CATEGORY_PARENT"
ADMIN_STATE_DELETE_CATEGORY = "ADMIN_DELETE_CATEGORY"

ADMIN_STATE_ADD_PRODUCT_NAME = "ADMIN_ADD_PRODUCT_NAME"
ADMIN_STATE_ADD_PRODUCT_DESCRIPTION = "ADMIN_ADD_PRODUCT_DESCRIPTION"
ADMIN_STATE_ADD_PRODUCT_PRICE = "ADMIN_ADD_PRODUCT_PRICE"
ADMIN_STATE_ADD_PRODUCT_ITEMS_PER_UNIT = "ADMIN_ADD_PRODUCT_ITEMS_PER_UNIT"
ADMIN_STATE_ADD_PRODUCT_CATEGORY = "ADMIN_ADD_PRODUCT_CATEGORY"
ADMIN_STATE_ADD_PRODUCT_IMAGE = "ADMIN_ADD_PRODUCT_IMAGE"
ADMIN_STATE_ADD_PRODUCT_IS_AVAILABLE = "ADMIN_ADD_PRODUCT_IS_AVAILABLE" # حالة جديدة لخطوة التوفر

ADMIN_STATE_EDIT_PRODUCT_SELECT = "ADMIN_EDIT_PRODUCT_SELECT"
ADMIN_STATE_EDIT_PRODUCT_FIELD = "ADMIN_EDIT_PRODUCT_FIELD"
ADMIN_STATE_DELETE_PRODUCT = "ADMIN_DELETE_PRODUCT"

ADMIN_STATE_CHANGE_ORDER_STATUS_SELECT_ORDER = "ADMIN_CHANGE_ORDER_STATUS_SELECT_ORDER"
ADMIN_STATE_CHANGE_ORDER_STATUS_SELECT_STATUS = "ADMIN_CHANGE_ORDER_STATUS_SELECT_STATUS"

ADMIN_STATE_MANAGE_RECHARGE_REQUEST_SELECT = "ADMIN_MANAGE_RECHARGE_REQUEST_SELECT"
ADMIN_STATE_ADD_BALANCE_MANUALLY_USER_ID = "ADMIN_ADD_BALANCE_MANUALLY_USER_ID"
ADMIN_STATE_ADD_BALANCE_MANUALLY_AMOUNT = "ADMIN_ADD_BALANCE_MANUALLY_AMOUNT"

ADMIN_STATE_SEARCH_USER = "ADMIN_SEARCH_USER"
ADMIN_STATE_RESTORE_CONFIRM = "ADMIN_RESTORE_CONFIRM"
ADMIN_STATE_RESTORE_FILE = "ADMIN_RESTORE_FILE"


async def admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_ID:
        await update.message.reply_text("ليس لديك صلاحية الوصول إلى لوحة الإدارة.")
        return

    last_auth_time = ADMIN_LAST_AUTH_TIME.get(user_id)
    if last_auth_time and (datetime.datetime.now() - last_auth_time).total_seconds() < ADMIN_AUTH_EXPIRY_HOURS * 3600:
        USER_STATE[user_id] = ADMIN_STATE_MAIN_MENU
        try:
            await update.message.reply_text(ADMIN_WELCOME_MESSAGE, reply_markup=admin_main_menu_inline_keyboard())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error sending welcome message to admin: {e}")
        return
    
    await update.message.reply_text("أدخل كلمة مرور المدير للدخول:", reply_markup=ReplyKeyboardRemove())
    USER_STATE[user_id] = ADMIN_STATE_AUTH

async def admin_main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_ID: return

    if USER_STATE.get(user_id) == ADMIN_STATE_MAIN_MENU:
        try:
            await (update.callback_query.message if update.callback_query else update.message).edit_text(
                ADMIN_WELCOME_MESSAGE, reply_markup=admin_main_menu_inline_keyboard()
            )
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing admin main menu: {e}")
    else:
        await admin_start(update, context)

async def admin_handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if user_id not in ADMIN_ID:
        await query.answer("ليس لديك صلاحية الوصول.")
        return
    
    if data == "admin_cancel":
        if user_id in USER_STATE:
            del USER_STATE[user_id]
            # مسح بيانات المستخدم المؤقتة
            context.user_data.pop('product_data', None)
            context.user_data.pop('temp_category_name', None)
            context.user_data.pop('temp_category_parent_id', None)
            context.user_data.pop('editing_product_id', None)
            context.user_data.pop('field_to_edit', None)
            context.user_data.pop('changing_order_id', None)
            context.user_data.pop('recharge_request_id', None)
            context.user_data.pop('add_balance_user_id', None)

        try:
            await query.message.edit_text(ADMIN_WELCOME_MESSAGE, reply_markup=admin_main_menu_inline_keyboard())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on admin_cancel: {e}")
        return

    if data == "admin_main_menu":
        USER_STATE[user_id] = ADMIN_STATE_MAIN_MENU
        try:
            await query.message.edit_text(ADMIN_WELCOME_MESSAGE, reply_markup=admin_main_menu_inline_keyboard())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on admin_main_menu: {e}")
        return

    if data == "admin_exit":
        if user_id in USER_STATE:
            del USER_STATE[user_id]
        if user_id in ADMIN_LAST_AUTH_TIME:
            del ADMIN_LAST_AUTH_TIME[user_id]
        
        try:
            await query.message.delete() 
        except BadRequest as e:
            logger.error(f"Error deleting admin exit message: {e}")

        await context.bot.send_message(chat_id=user_id, text="تم الخروج من لوحة الإدارة.", reply_markup=ReplyKeyboardRemove())
        
        # استخدام الدالة الممررة من main.py
        if _user_start_handler:
            await _user_start_handler(update, context) 
        else:
            logger.error("User start handler not set in admin_handlers.")
        return

    # --- إدارة الفئات والخدمات ---
    if data == "admin_products_categories_menu":
        try:
            await query.message.edit_text("اختر إجراء لإدارة الخدمات والفئات:", reply_markup=admin_products_categories_menu_inline())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing admin products/categories menu: {e}")
    
    # إدارة الفئات
    elif data == "admin_add_category":
        try:
            await query.message.edit_text("أدخل اسم الفئة الجديدة:", reply_markup=admin_cancel_inline_button())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on add category prompt: {e}")
        USER_STATE[user_id] = ADMIN_STATE_ADD_CATEGORY
        context.user_data['temp_category_name'] = None
        context.user_data['temp_category_parent_id'] = None

    elif data.startswith("select_parent_cat_"):
        parent_id_str = data.split("_")[3]
        parent_id = int(parent_id_str) if parent_id_str != "none" else None
        
        category_name = context.user_data.get('temp_category_name')
        if category_name:
            if db.add_category(category_name, parent_id):
                try:
                    await query.message.edit_text(f"تمت إضافة الفئة '{category_name}' بنجاح.", reply_markup=admin_products_categories_menu_inline())
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on category added: {e}")
            else:
                try:
                    await query.message.edit_text(f"الفئة '{category_name}' موجودة بالفعل أو حدث خطأ.", reply_markup=admin_products_categories_menu_inline())
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on category add error: {e}")
        else:
            try:
                await query.message.edit_text("حدث خطأ: اسم الفئة غير موجود.", reply_markup=admin_products_categories_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on missing category name: {e}")
        
        del USER_STATE[user_id]
        context.user_data.pop('temp_category_name', None)
        context.user_data.pop('temp_category_parent_id', None)

    elif data == "admin_delete_category":
        categories = db.get_all_categories(parent_id=None)
        if not categories:
            try:
                await query.message.edit_text("لا توجد فئات لحذفها.", reply_markup=admin_products_categories_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on no categories to delete: {e}")
            return
        
        keyboard = [[InlineKeyboardButton(name, callback_data=f"del_cat_{cat_id}")] for cat_id, name in categories]
        keyboard.append([InlineKeyboardButton("🔙 لإدارة الخدمات", callback_data="admin_products_categories_menu")])
        try:
            await query.message.edit_text("اختر الفئة (أو الفئة الرئيسية) لحذفها:", reply_markup=InlineKeyboardMarkup(keyboard))
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on delete category prompt: {e}")
    elif data.startswith("del_cat_"):
        category_id = int(data.split("_")[2])
        db.delete_category(category_id)
        try:
            await query.message.edit_text(f"تم حذف الفئة بنجاح. (سيتم حذف الفئات الفرعية والخدمات المرتبطة تلقائياً)", reply_markup=admin_products_categories_menu_inline())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on category deleted: {e}")
        if user_id in USER_STATE: del USER_STATE[user_id]

    # إدارة الخدمات (المنتجات)
    elif data == "admin_add_product":
        categories = db.get_all_categories(parent_id=None)
        if not categories:
            try:
                await query.message.edit_text("لا توجد فئات لإضافة خدمات إليها. يرجى إضافة فئة أولاً.", reply_markup=admin_products_categories_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on no categories for product: {e}")
            return
        context.user_data['product_data'] = {}
        try:
            await query.message.edit_text("أدخل اسم الخدمة:", reply_markup=admin_cancel_inline_button())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on add product name prompt: {e}")
        USER_STATE[user_id] = ADMIN_STATE_ADD_PRODUCT_NAME
    
    elif data == "admin_edit_product":
        products = db.get_all_products()
        if not products:
            try:
                await query.message.edit_text("لا توجد خدمات لتعديلها.", reply_markup=admin_products_categories_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on no products to edit: {e}")
            return
        
        keyboard = [[InlineKeyboardButton(name, callback_data=f"edit_prod_select_{prod_id}")] for prod_id, name, _, _, _, _, _, _ in products]
        keyboard.append([InlineKeyboardButton("🔙 لإدارة الخدمات", callback_data="admin_products_categories_menu")])
        try:
            await query.message.edit_text("اختر الخدمة لتعديلها:", reply_markup=InlineKeyboardMarkup(keyboard))
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on select product to edit: {e}")
    elif data.startswith("edit_prod_select_"):
        product_id = int(data.split("_")[3])
        context.user_data['editing_product_id'] = product_id
        try:
            await query.message.edit_text("اختر الحقل الذي تريد تعديله:", reply_markup=admin_product_edit_select_field())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on select product field to edit: {e}")
    
    elif data.startswith("browse_cat_"):
        category_id = int(data.split('_')[2])
        current_state = USER_STATE.get(user_id)

        if current_state == ADMIN_STATE_ADD_PRODUCT_CATEGORY:
            subcategories = db.get_all_categories(parent_id=category_id)
            if subcategories:
                try:
                    await query.message.edit_text(
                        f"اختر فئة فرعية ضمن '{db.get_category_name(category_id)}' لإضافة الخدمة:", 
                        reply_markup=categories_keyboard(subcategories, current_parent_id=category_id)
                    )
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on subcategory selection (add product): {e}")
            else:
                context.user_data['product_data']['category_id'] = category_id
                # الآن نطلب حالة التوفر باستخدام الأزرار
                try:
                    await query.message.edit_text("اختر حالة توفر الخدمة:", reply_markup=admin_set_availability_keyboard(product_id=None)) # product_id = None للدلالة على منتج جديد
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on availability prompt (add product): {e}")
                # الحالة التالية ستتم معالجتها بواسطة الكولباك لـ set_prod_available_new_X
                # لذلك لا نغير الـ USER_STATE هنا، بل ننتظر الكولباك لمعالجتها
        
        elif current_state == ADMIN_STATE_EDIT_PRODUCT_FIELD and context.user_data.get('field_to_edit') == 'category':
            subcategories = db.get_all_categories(parent_id=category_id)
            if subcategories:
                try:
                    await query.message.edit_text(
                        f"اختر فئة فرعية ضمن '{db.get_category_name(category_id)}' للخدمة:", 
                        reply_markup=categories_keyboard(subcategories, current_parent_id=category_id)
                    )
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on subcategory selection (edit product): {e}")
            else:
                product_id = context.user_data.get('editing_product_id')
                if product_id:
                    db.update_product(product_id, category_id=category_id)
                    try:
                        await query.message.edit_text("تم تحديث فئة الخدمة بنجاح.", reply_markup=admin_products_categories_menu_inline())
                    except BadRequest as e:
                        if "Message is not modified" in str(e):
                            logger.info("Message content is the same, no modification needed.")
                        else:
                            logger.error(f"Error editing message on product category updated: {e}")
                    del USER_STATE[user_id]
                    context.user_data.pop('editing_product_id', None)
                    context.user_data.pop('field_to_edit', None)
                else:
                    try:
                        await query.message.edit_text("حدث خطأ في تحديد الخدمة.", reply_markup=admin_products_categories_menu_inline())
                    except BadRequest as e:
                        if "Message is not modified" in str(e):
                            logger.info("Message content is the same, no modification needed.")
                        else:
                            logger.error(f"Error editing message on product not found (category edit): {e}")
                    del USER_STATE[user_id]
        return
    
    elif data.startswith("edit_prod_"):
        field_to_edit = data.split("_")[2]
        context.user_data['field_to_edit'] = field_to_edit
        current_product_id = context.user_data.get('editing_product_id')
        current_product = db.get_product_by_id(current_product_id)

        if not current_product:
            try:
                await query.message.edit_text("خطأ: الخدمة غير موجودة.", reply_markup=admin_products_categories_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on product not found: {e}")
            if user_id in USER_STATE: del USER_STATE[user_id]
            return
        
        message_text = ""
        if field_to_edit == "name":
            message_text = f"أدخل الاسم الجديد للخدمة (الحالي: {current_product[1]}):"
        elif field_to_edit == "description":
            message_text = f"أدخل الوصف الجديد للخدمة (الحالي: {current_product[2] or 'لا يوجد'}):"
        elif field_to_edit == "price":
            message_text = f"أدخل السعر الجديد للخدمة (الحالي: {current_product[3]:.2f} {CURRENCY_SYMBOL}):"
        elif field_to_edit == "items_per_unit":
            message_text = f"أدخل الكمية التي يمثلها السعر الجديد (مثلاً: 1000 تعني 1 دولار لكل 1000) (الحالي: {current_product[4]}):"
        elif field_to_edit == "category":
            categories = db.get_all_categories(parent_id=None)
            if not categories:
                try:
                    await query.message.edit_text("لا توجد فئات متاحة.", reply_markup=admin_products_categories_menu_inline())
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on no categories for product category edit: {e}")
                if user_id in USER_STATE: del USER_STATE[user_id]
                return
            
            try:
                await query.message.edit_text(
                    "اختر الفئة الجديدة للخدمة:", 
                    reply_markup=categories_keyboard(categories, current_parent_id=None)
                )
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on selecting product category (edit): {e}")
            USER_STATE[user_id] = ADMIN_STATE_EDIT_PRODUCT_FIELD
            return

        elif field_to_edit == "image_url":
            message_text = f"أدخل رابط الصورة الجديد للخدمة (الحالي: {current_product[6] or 'لا يوجد'}):"
        elif field_to_edit == "is_available":
            try:
                await query.message.edit_text("اختر حالة توفر الخدمة:", reply_markup=admin_set_availability_keyboard(current_product_id))
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on availability prompt (edit product): {e}")
            USER_STATE[user_id] = ADMIN_STATE_EDIT_PRODUCT_FIELD
            return
        
        try:
            await query.message.edit_text(message_text, reply_markup=admin_cancel_inline_button())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on product field edit prompt: {e}")
        USER_STATE[user_id] = ADMIN_STATE_EDIT_PRODUCT_FIELD
    
    # *** تم تعديل هذا الجزء لمعالجة حالة "new" بشكل صحيح ***
    elif data.startswith("set_prod_available_"):
        parts = data.split('_')
        # تحقق مما إذا كانت القيمة هي 'new' (لإضافة منتج) أو ID فعلي (لتعديل منتج)
        target_id_or_new = parts[3]
        is_available_value = int(parts[4])
        
        if target_id_or_new == 'new': # هذه هي حالة إضافة منتج جديد
            # يجب التأكد أننا في حالة إضافة منتج جديدة
            current_state = USER_STATE.get(user_id)
            # لا نحتاج لتعيين USER_STATE = ADMIN_STATE_ADD_PRODUCT_IS_AVAILABLE
            # قبل هذا الكولباك، لأنه سيتم معالجته مباشرة هنا.
            # التحقق من أن الـ product_data موجودة يكفي.

            context.user_data['product_data']['is_available'] = is_available_value
            
            try:
                await query.message.edit_text("أدخل رابط صورة الخدمة (اختياري، اكتب 'skip' للتخطي):", reply_markup=admin_cancel_inline_button())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on image URL prompt (add product): {e}")
            USER_STATE[user_id] = ADMIN_STATE_ADD_PRODUCT_IMAGE # ننتقل للحالة التالية هنا
            return
        
        else: # هذه هي حالة تعديل منتج موجود
            product_id = int(target_id_or_new)
            db.update_product(product_id, is_available=is_available_value)
            
            status_text = "متوفر" if is_available_value else "غير متوفر"
            try:
                await query.message.edit_text(f"تم تحديث حالة توفر الخدمة بنجاح إلى: {status_text}.", reply_markup=admin_products_categories_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on product availability updated: {e}")
            
            # تنظيف الحالة بعد التحديث لمنتج موجود
            del USER_STATE[user_id]
            context.user_data.pop('editing_product_id', None)
            context.user_data.pop('field_to_edit', None)
            return


    elif data == "admin_delete_product":
        products = db.get_all_products()
        if not products:
            try:
                await query.message.edit_text("لا توجد خدمات لحذفها.", reply_markup=admin_products_categories_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on no products to delete: {e}")
            return
        
        keyboard = [[InlineKeyboardButton(name, callback_data=f"del_prod_{prod_id}")] for prod_id, name, _, _, _, _, _, _ in products]
        keyboard.append([InlineKeyboardButton("🔙 لإدارة الخدمات", callback_data="admin_products_categories_menu")])
        try:
            await query.message.edit_text("اختر الخدمة لحذفها:", reply_markup=InlineKeyboardMarkup(keyboard))
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on select product to delete: {e}")
    elif data.startswith("del_prod_"):
        product_id = int(data.split("_")[2])
        db.delete_product(product_id)
        try:
            await query.message.edit_text(f"تم حذف الخدمة بنجاح.", reply_markup=admin_products_categories_menu_inline())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on product deleted: {e}")
        if user_id in USER_STATE: del USER_STATE[user_id]

    # --- إدارة الطلبات ---
    elif data == "admin_orders_menu":
        try:
            await query.message.edit_text("اختر إجراء لإدارة الطلبات:", reply_markup=admin_orders_menu_inline())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing admin orders menu: {e}")
    elif data == "admin_view_all_orders":
        orders = db.get_all_orders()
        if not orders:
            try:
                await query.message.edit_text("لا توجد طلبات حالياً.", reply_markup=admin_orders_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on no orders: {e}")
            return
        
        message = "**📊 جميع الطلبات:**\n\n"
        for order_id, username, product_name, purchased_quantity, total_amount, status, order_date, order_details_input in orders:
            message += f"**الطلب رقم:** `{order_id}`\n" \
                       f"**المستخدم:** {username or 'غير متوفر'}\n" \
                       f"**الخدمة:** {product_name}\n" \
                       f"**الكمية:** {purchased_quantity}\n" \
                       f"**التكلفة:** {total_amount:.2f} {CURRENCY_SYMBOL}\n" \
                       f"**الحالة:** {status}\n" \
                       f"**التاريخ:** {order_date.split('.')[0]}\n" \
                       f"**التفاصيل المدخلة:** {order_details_input or 'لا يوجد'}\n\n"
        
        try:
            await query.message.edit_text(message, reply_markup=admin_orders_menu_inline(), parse_mode='Markdown')
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on view all orders: {e}")

    elif data == "admin_change_order_status":
        orders = db.get_all_orders()
        if not orders:
            try:
                await query.message.edit_text("لا توجد طلبات لتغيير حالتها.", reply_markup=admin_orders_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on no orders to change status: {e}")
            return
        
        keyboard = [[InlineKeyboardButton(f"الطلب {order_id} ({status})", callback_data=f"change_order_status_select_{order_id}")] for order_id, _, _, _, _, status, _, _ in orders]
        keyboard.append([InlineKeyboardButton("🔙 لإدارة الطلبات", callback_data="admin_orders_menu")])
        try:
            await query.message.edit_text("اختر الطلب لتغيير حالته:", reply_markup=InlineKeyboardMarkup(keyboard))
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on select order to change status: {e}")
    elif data.startswith("change_order_status_select_"):
        order_id = int(data.split("_")[4])
        context.user_data['changing_order_id'] = order_id
        
        keyboard = [
            [InlineKeyboardButton("معلق", callback_data=f"set_order_status_{order_id}_pending")],
            [InlineKeyboardButton("قيد المعالجة", callback_data=f"set_order_status_{order_id}_processing")],
            [InlineKeyboardButton("مكتمل", callback_data=f"set_order_status_{order_id}_completed")],
            [InlineKeyboardButton("ملغى", callback_data=f"set_order_status_{order_id}_cancelled")],
            [InlineKeyboardButton("🔙 لإدارة الطلبات", callback_data="admin_orders_menu")]
        ]
        try:
            await query.message.edit_text(f"اختر الحالة الجديدة للطلب رقم {order_id}:", reply_markup=InlineKeyboardMarkup(keyboard))
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on select new order status: {e}")
    elif data.startswith("set_order_status_"):
        parts = data.split("_")
        order_id = int(parts[3])
        status = parts[4]
        db.update_order_status(order_id, status)
        try:
            await query.message.edit_text(f"تم تحديث حالة الطلب `{order_id}` إلى `{status}`.", reply_markup=admin_orders_menu_inline())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on order status updated: {e}")
        if user_id in USER_STATE: del USER_STATE[user_id]
        context.user_data.pop('changing_order_id', None)

    # --- إدارة المستخدمين ---
    elif data == "admin_users_menu":
        try:
            await query.message.edit_text("اختر إجراء لإدارة المستخدمين:", reply_markup=admin_users_menu_inline())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing admin users menu: {e}")
    elif data == "admin_view_all_users":
        users = db.get_all_users()
        if not users:
            try:
                await query.message.edit_text("لا يوجد مستخدمون مسجلون حالياً.", reply_markup=admin_users_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on no registered users: {e}")
            return
        
        message = "**👥 جميع المستخدمين:**\n\n"
        for user_id_db, username, full_name, registered_at, balance in users:
            message += f"**ID:** `{user_id_db}`\n" \
                       f"**اسم المستخدم:** {username or 'غير متوفر'}\n" \
                       f"**الاسم الكامل:** {full_name or 'غير متوفر'}\n" \
                       f"**الرصيد:** {balance:.2f} {CURRENCY_SYMBOL}\n" \
                       f"**تاريخ التسجيل:** {registered_at.split('.')[0]}\n\n"
        try:
            await query.message.edit_text(message, reply_markup=admin_users_menu_inline(), parse_mode='Markdown')
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on view all users: {e}")

    elif data == "admin_search_user":
        try:
            await query.message.edit_text("أدخل معرف المستخدم (ID) أو اسم المستخدم (Username) للبحث:", reply_markup=admin_cancel_inline_button())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on search user prompt: {e}")
        USER_STATE[user_id] = ADMIN_STATE_SEARCH_USER

    # --- إدارة شحن الرصيد ---
    elif data == "admin_recharge_requests_menu":
        try:
            await query.message.edit_text("اختر إجراء لإدارة طلبات شحن الرصيد:", reply_markup=admin_recharge_requests_menu_inline())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing admin recharge menu: {e}")
    
    elif data == "admin_view_pending_recharge":
        requests = db.get_all_recharge_requests(status='pending')
        if not requests:
            try:
                await query.message.edit_text("لا توجد طلبات شحن رصيد معلقة حالياً.", reply_markup=admin_recharge_requests_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on no pending recharge requests: {e}")
            return
        
        message = "**💰 طلبات شحن الرصيد المعلقة:**\n\n"
        for req_id, user_id_db, username, full_name, amount, method, details, status, date in requests:
            message += f"**الطلب رقم:** `{req_id}`\n" \
                       f"**معرف المستخدم:** `{user_id_db}`\n" \
                       f"**المستخدم:** {username or 'غير متوفر'}\n" \
                       f"**الاسم الكامل:** {full_name or 'غير متوفر'}\n" \
                       f"**المبلغ:** {amount:.2f} {CURRENCY_SYMBOL}\n" \
                       f"**طريقة الدفع:** {method}\n" \
                       f"**التفاصيل:** {details}\n" \
                       f"**التاريخ:** {date.split('.')[0]}\n" \
                       f"للمعالجة: /manage_recharge_{req_id}\n\n"
        
        try:
            await query.message.edit_text(message, parse_mode='Markdown', reply_markup=admin_recharge_requests_menu_inline())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on view pending recharge: {e}")
    
    elif data == "admin_manage_recharge_request":
        all_requests = db.get_all_recharge_requests()
        if not all_requests:
            try:
                await query.message.edit_text("لا توجد طلبات شحن رصيد لإدارتها.", reply_markup=admin_recharge_requests_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on no recharge requests to manage: {e}")
            return
        
        keyboard_buttons = []
        for req_id, user_id_db, username, full_name, amount, method, details, status, date in all_requests:
            keyboard_buttons.append([InlineKeyboardButton(f"طلب {req_id} - {username} ({amount:.2f} {CURRENCY_SYMBOL}) - {status}", callback_data=f"select_recharge_to_manage_{req_id}")])
        
        keyboard_buttons.append([InlineKeyboardButton("🔙 لإدارة شحن الرصيد", callback_data="admin_recharge_requests_menu")])
        
        try:
            await query.message.edit_text("اختر طلب شحن رصيد لإدارته:", reply_markup=InlineKeyboardMarkup(keyboard_buttons))
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on select recharge request to manage: {e}")

    elif data.startswith("select_recharge_to_manage_"):
        request_id = int(data.split('_')[4])
        context.user_data['recharge_request_id'] = request_id
        
        req_details = db.cursor.execute("SELECT user_id, username, full_name, amount, payment_method, payment_details, status, request_date FROM recharge_requests WHERE id = ?", (request_id,)).fetchone()
        if req_details:
            user_id_db, username, full_name, amount, method, details, status, date = req_details
            message_text = f"**تفاصيل طلب الشحن رقم:** `{request_id}`\n\n" \
                           f"**معرف المستخدم:** `{user_id_db}`\n" \
                           f"**المستخدم:** {username or 'غير متوفر'}\n" \
                           f"**الاسم الكامل:** {full_name or 'غير متوفر'}\n" \
                           f"**المبلغ:** {amount:.2f} {CURRENCY_SYMBOL}\n" \
                           f"**طريقة الدفع:** {method}\n" \
                           f"**التفاصيل:** {details}\n" \
                           f"**الحالة الحالية:** {status}\n" \
                           f"**تاريخ الطلب:** {date.split('.')[0]}"
            
            try:
                await query.message.edit_text(message_text, parse_mode='Markdown', reply_markup=admin_manage_recharge_status_keyboard(request_id))
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on view recharge request details: {e}")
        else:
            try:
                await query.message.edit_text("طلب الشحن غير موجود.", reply_markup=admin_recharge_requests_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on recharge request not found: {e}")
        USER_STATE[user_id] = ADMIN_STATE_MANAGE_RECHARGE_REQUEST_SELECT
    
    elif data.startswith("admin_approve_recharge_"):
        request_id = int(data.split('_')[3])
        req_details = db.get_recharge_request_details(request_id)
        if req_details and req_details[2] == 'pending':
            user_to_recharge_id = req_details[0]
            amount_to_add = req_details[1]
            db.update_user_balance(user_to_recharge_id, amount_to_add)
            db.update_recharge_request_status(request_id, 'approved')
            
            # إرسال إشعار للمستخدم
            try:
                await context.bot.send_message(chat_id=user_to_recharge_id, 
                                               text=f"✅ تم اعتماد طلب شحن رصيدك رقم `{request_id}` بقيمة {amount_to_add:.2f} {CURRENCY_SYMBOL}.\nرصيدك الحالي: {db.get_user_balance(user_to_recharge_id):.2f} {CURRENCY_SYMBOL}.",
                                               parse_mode='Markdown')
            except Exception as e:
                logger.warning(f"Failed to notify user {user_to_recharge_id} about recharge approval: {e}")
            
            try:
                await query.message.edit_text(f"تم اعتماد طلب الشحن رقم `{request_id}` وإضافة الرصيد للمستخدم.", reply_markup=admin_recharge_requests_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on recharge approval: {e}")
        else:
            try:
                await query.message.edit_text("طلب الشحن إما غير موجود أو تم معالجته بالفعل.", reply_markup=admin_recharge_requests_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on recharge approval error: {e}")
        context.user_data.pop('recharge_request_id', None)
        if user_id in USER_STATE: del USER_STATE[user_id]
    
    elif data.startswith("admin_reject_recharge_"):
        request_id = int(data.split('_')[3])
        req_details = db.get_recharge_request_details(request_id)
        if req_details and req_details[2] == 'pending':
            db.update_recharge_request_status(request_id, 'rejected')
            
            # إرسال إشعار للمستخدم
            try:
                await context.bot.send_message(chat_id=req_details[0], 
                                               text=f"❌ تم رفض طلب شحن رصيدك رقم `{request_id}`.\nيرجى التواصل مع الإدارة للمزيد من التفاصيل.",
                                               parse_mode='Markdown')
            except Exception as e:
                logger.warning(f"Failed to notify user {req_details[0]} about recharge rejection: {e}")

            try:
                await query.message.edit_text(f"تم رفض طلب الشحن رقم `{request_id}`.", reply_markup=admin_recharge_requests_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on recharge rejection: {e}")
        else:
            try:
                await query.message.edit_text("طلب الشحن إما غير موجود أو تم معالجته بالفعل.", reply_markup=admin_recharge_requests_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on recharge rejection error: {e}")
        context.user_data.pop('recharge_request_id', None)
        if user_id in USER_STATE: del USER_STATE[user_id]
    
    elif data == "admin_add_balance_manually":
        try:
            await query.message.edit_text("أدخل معرف المستخدم (ID) الذي تريد إضافة رصيد له:", reply_markup=admin_cancel_inline_button())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on add balance user ID prompt: {e}")
        USER_STATE[user_id] = ADMIN_STATE_ADD_BALANCE_MANUALLY_USER_ID

    # --- النسخ الاحتياطي والاستعادة ---
    elif data == "admin_backup_restore_menu":
        try:
            await query.message.edit_text("اختر إجراء للنسخ الاحتياطي والاستعادة:", reply_markup=admin_backup_restore_menu_inline())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing admin backup/restore menu: {e}")
    elif data == "admin_create_backup":
        try:
            backup_dir = os.path.dirname(DB_BACKUP_PATH)
            
            if backup_dir:
                os.makedirs(backup_dir, exist_ok=True)

            shutil.copyfile(DB_NAME, DB_BACKUP_PATH)
            await context.bot.send_document(chat_id=user_id, document=open(DB_BACKUP_PATH, 'rb'), caption="تم إنشاء نسخة احتياطية من قاعدة البيانات.")
            
            if BACKUP_CHANNEL_ID is not None:
                try:
                    await context.bot.send_document(chat_id=BACKUP_CHANNEL_ID, document=open(DB_BACKUP_PATH, 'rb'), caption="نسخة احتياطية لقاعدة بيانات البوت.")
                except Exception as e:
                    logger.warning(f"Failed to send backup to backup channel {BACKUP_CHANNEL_ID}: {e}")
                    await context.bot.send_message(chat_id=user_id, text=f"تحذير: فشل إرسال النسخة الاحتياطية إلى قناة النسخ الاحتياطي ({BACKUP_CHANNEL_ID}). تحقق من صلاحيات البوت ومعرف القناة.", reply_markup=admin_backup_restore_menu_inline())

            os.remove(DB_BACKUP_PATH)
            try:
                await query.message.edit_text("تم إنشاء وإرسال النسخة الاحتياطية بنجاح.", reply_markup=admin_backup_restore_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on backup success: {e}")
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            try:
                await query.message.edit_text(f"حدث خطأ أثناء إنشاء النسخة الاحتياطية: {e}", reply_markup=admin_backup_restore_menu_inline())
            except BadRequest as e_inner:
                if "Message is not modified" in str(e_inner):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on backup failure: {e_inner}")
    elif data == "admin_restore_backup":
        try:
            await query.message.edit_text(
                "تحذير: استعادة النسخة الاحتياطية ستحذف البيانات الحالية. هل أنت متأكد؟",
                reply_markup=admin_confirm_restore_keyboard()
            )
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on restore confirmation: {e}")
        USER_STATE[user_id] = ADMIN_STATE_RESTORE_CONFIRM
    elif data == "admin_confirm_restore":
        try:
            await query.message.edit_text("يرجى إرسال ملف قاعدة البيانات (store_bot.db) الذي تريد استعادته.", reply_markup=admin_cancel_inline_button())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on restore file prompt: {e}")
        USER_STATE[user_id] = ADMIN_STATE_RESTORE_FILE


async def admin_handle_admin_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_ID: return

    current_state = USER_STATE.get(user_id)
    text = update.message.text
    document = update.message.document

    if current_state == ADMIN_STATE_AUTH:
        if text == ADMIN_PASSWORD:
            USER_STATE[user_id] = ADMIN_STATE_MAIN_MENU
            ADMIN_LAST_AUTH_TIME[user_id] = datetime.datetime.now()
            try:
                await update.message.reply_text(ADMIN_WELCOME_MESSAGE, reply_markup=admin_main_menu_inline_keyboard())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error sending welcome message after auth: {e}")
        else:
            await update.message.reply_text("كلمة المرور غير صحيحة. حاول مرة أخرى.", reply_markup=admin_password_inline_keyboard())
        return

    if current_state is None or not current_state.startswith("ADMIN_"):
        try:
            await update.message.reply_text("يرجى استخدام لوحة الإدارة.", reply_markup=admin_main_menu_inline_keyboard())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error sending admin menu for unknown state: {e}")
        return
    
    # --- معالجة إضافة الفئة ---
    if current_state == ADMIN_STATE_ADD_CATEGORY:
        context.user_data['temp_category_name'] = text
        categories = db.get_all_categories(parent_id=None)
        
        keyboard_buttons = []
        for cat_id, name in categories:
            keyboard_buttons.append([InlineKeyboardButton(name, callback_data=f"select_parent_cat_{cat_id}")])
        
        keyboard_buttons.append([InlineKeyboardButton("لا يوجد فئة أم (فئة رئيسية)", callback_data="select_parent_cat_none")])
        keyboard_buttons.append([InlineKeyboardButton("إلغاء", callback_data="admin_cancel")])
        
        await update.message.reply_text("اختر الفئة الأم لهذه الفئة الجديدة (أو لا شيء لفئة رئيسية):", reply_markup=InlineKeyboardMarkup(keyboard_buttons))
        USER_STATE[user_id] = ADMIN_STATE_ADD_CATEGORY_PARENT
        return

    # --- معالجة إضافة الخدمة (المنتج) ---
    elif current_state == ADMIN_STATE_ADD_PRODUCT_NAME:
        context.user_data['product_data']['name'] = text
        await update.message.reply_text("أدخل وصف الخدمة:", reply_markup=admin_cancel_inline_button())
        USER_STATE[user_id] = ADMIN_STATE_ADD_PRODUCT_DESCRIPTION
    elif current_state == ADMIN_STATE_ADD_PRODUCT_DESCRIPTION:
        context.user_data['product_data']['description'] = text
        await update.message.reply_text(f"أدخل سعر الخدمة (مثال: 0.50 لـ {DEFAULT_ITEMS_PER_UNIT} وحدة، العملة {CURRENCY_SYMBOL}):", reply_markup=admin_cancel_inline_button())
        USER_STATE[user_id] = ADMIN_STATE_ADD_PRODUCT_PRICE
    elif current_state == ADMIN_STATE_ADD_PRODUCT_PRICE:
        try:
            price = float(text)
            if price <= 0:
                await update.message.reply_text("السعر يجب أن يكون رقماً موجباً.", reply_markup=admin_cancel_inline_button())
                return
            context.user_data['product_data']['price'] = price
            
            await update.message.reply_text("أدخل عدد الوحدات التي يمثلها هذا السعر (مثلاً: 1000 إذا كان السعر لـ 1000 متابع):", reply_markup=admin_cancel_inline_button())
            USER_STATE[user_id] = ADMIN_STATE_ADD_PRODUCT_ITEMS_PER_UNIT
            
        except ValueError:
            await update.message.reply_text("سعر غير صالح. يرجى إدخال رقم.", reply_markup=admin_cancel_inline_button())
    
    elif current_state == ADMIN_STATE_ADD_PRODUCT_ITEMS_PER_UNIT:
        try:
            items_per_unit = int(text)
            if items_per_unit <= 0:
                await update.message.reply_text("عدد الوحدات يجب أن يكون رقماً صحيحاً موجباً.", reply_markup=admin_cancel_inline_button())
                return
            context.user_data['product_data']['items_per_unit'] = items_per_unit

            categories = db.get_all_categories(parent_id=None)
            if not categories:
                await update.message.reply_text("لا توجد فئات لإسناد الخدمة إليها. يرجى إضافة فئة أولاً.", reply_markup=admin_products_categories_menu_inline())
                del USER_STATE[user_id]
                context.user_data.pop('product_data', None)
                return
            
            await update.message.reply_text(
                "اختر فئة الخدمة:", 
                reply_markup=categories_keyboard(categories, current_parent_id=None)
            )
            USER_STATE[user_id] = ADMIN_STATE_ADD_PRODUCT_CATEGORY
        except ValueError:
            await update.message.reply_text("عدد وحدات غير صالح. يرجى إدخال عدد صحيح.", reply_markup=admin_cancel_inline_button())

    # *** تم إزالة معالجة ADMIN_STATE_ADD_PRODUCT_IS_AVAILABLE من هنا
    # لأنها ستتم معالجتها بواسطة الكولباك في admin_handle_callback_query ***
    
    elif current_state == ADMIN_STATE_ADD_PRODUCT_IMAGE:
        if text and text.lower() == 'skip':
            context.user_data['product_data']['image_url'] = None
        elif text:
            context.user_data['product_data']['image_url'] = text
        else:
             await update.message.reply_text("يرجى إدخال رابط الصورة أو 'skip' للتخطي.", reply_markup=admin_cancel_inline_button())
             return
        
        product_data = context.user_data['product_data']
        required_keys = ['name', 'description', 'price', 'items_per_unit', 'category_id', 'is_available']
        if all(key in product_data for key in required_keys):
            db.add_product(
                product_data['name'],
                product_data['description'],
                product_data['price'],
                product_data['items_per_unit'],
                product_data['category_id'],
                product_data.get('image_url'),
                product_data['is_available']
            )
            await update.message.reply_text("تمت إضافة الخدمة بنجاح!", reply_markup=admin_products_categories_menu_inline())
            del USER_STATE[user_id]
            context.user_data.pop('product_data', None)
        else:
            await update.message.reply_text("حدث خطأ: بيانات الخدمة غير مكتملة. يرجى البدء من جديد.", reply_markup=admin_products_categories_menu_inline())
            del USER_STATE[user_id]
            context.user_data.pop('product_data', None)


    # --- معالجة تعديل الخدمة (المنتج) ---
    elif current_state == ADMIN_STATE_EDIT_PRODUCT_FIELD:
        product_id = context.user_data.get('editing_product_id')
        field = context.user_data.get('field_to_edit')
        
        if not product_id or not field:
            try:
                await update.message.reply_text("حدث خطأ في تحديد الخدمة أو الحقل. يرجى البدء من جديد.", reply_markup=admin_products_categories_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on product/field error (edit): {e}")
            if user_id in USER_STATE: del USER_STATE[user_id]
            return
        
        if field == "name":
            db.update_product(product_id, name=text)
        elif field == "description":
            db.update_product(product_id, description=text)
        elif field == "price":
            try:
                price = float(text)
                if price <= 0: raise ValueError
                db.update_product(product_id, price=price)
            except ValueError:
                await update.message.reply_text("سعر غير صالح. يرجى إدخال رقم موجب.", reply_markup=admin_cancel_inline_button())
                return
        elif field == "items_per_unit":
            try:
                items_per_unit = int(text)
                if items_per_unit <= 0: raise ValueError
                db.update_product(product_id, items_per_unit=items_per_unit)
            except ValueError:
                await update.message.reply_text("عدد وحدات غير صالح. يرجى إدخال عدد صحيح موجب.", reply_markup=admin_cancel_inline_button())
                return
        elif field == "image_url":
            db.update_product(product_id, image_url=text)
        # *** تم إزالة معالجة is_available من هنا أيضًا لأنها ستتم معالجتها بواسطة الكولباك ***
        # elif field == "is_available":
        #     if text.lower() == 'متوفر':
        #         db.update_product(product_id, is_available=1)
        #     elif text.lower() == 'غير متوفر':
        #         db.update_product(product_id, is_available=0)
        #     else:
        #         await update.message.reply_text("إدخال غير صالح. يرجى استخدام الأزرار لتحديد حالة التوفر أو كتابة 'متوفر'/'غير متوفر'.", reply_markup=admin_set_availability_keyboard(product_id))
        #         return
        
        try:
            await update.message.reply_text("تم تحديث الخدمة بنجاح.", reply_markup=admin_products_categories_menu_inline())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error editing message on product updated: {e}")
        del USER_STATE[user_id]
        context.user_data.pop('editing_product_id', None)
        context.user_data.pop('field_to_edit', None)

    # --- معالجة بحث المستخدمين ---
    elif current_state == ADMIN_STATE_SEARCH_USER:
        search_term = text
        user_info = None
        
        try:
            user_id_int = int(search_term)
            user_info = db.get_user(user_id_int)
        except ValueError:
            all_users = db.get_all_users()
            for u in all_users:
                if u[1] and search_term.lower() in u[1].lower(): # username
                    user_info = u
                    break
                if u[2] and search_term.lower() in u[2].lower(): # full_name
                    user_info = u
                    break

        if user_info:
            _, username, full_name, registered_at, balance = user_info
            message = f"**👤 معلومات المستخدم:**\n\n" \
                      f"**ID:** `{user_info[0]}`\n" \
                      f"**اسم المستخدم:** {username or 'غير متوفر'}\n" \
                      f"**الاسم الكامل:** {full_name or 'غير متوفر'}\n" \
                      f"**الرصيد:** {balance:.2f} {CURRENCY_SYMBOL}\n" \
                      f"**تاريخ التسجيل:** {registered_at.split('.')[0]}"
            try:
                await update.message.reply_text(message, reply_markup=admin_users_menu_inline(), parse_mode='Markdown')
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error sending user info message: {e}")
        else:
            try:
                await update.message.reply_text("لم يتم العثور على المستخدم.", reply_markup=admin_users_menu_inline())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error sending user not found message: {e}")
        del USER_STATE[user_id]

    # --- إضافة رصيد يدوياً ---
    elif current_state == ADMIN_STATE_ADD_BALANCE_MANUALLY_USER_ID:
        try:
            target_user_id = int(text)
            user_exists = db.get_user(target_user_id)
            if user_exists:
                context.user_data['add_balance_user_id'] = target_user_id
                await update.message.reply_text(f"تم تحديد المستخدم ID: `{target_user_id}`.\nالآن أدخل المبلغ المراد إضافته (أرقام فقط):", reply_markup=admin_cancel_inline_button())
                USER_STATE[user_id] = ADMIN_STATE_ADD_BALANCE_MANUALLY_AMOUNT
            else:
                await update.message.reply_text("معرف المستخدم غير موجود. يرجى إدخال معرف صالح.", reply_markup=admin_cancel_inline_button())
        except ValueError:
            await update.message.reply_text("معرف مستخدم غير صالح. يرجى إدخال رقم صحيح.", reply_markup=admin_cancel_inline_button())
    
    elif current_state == ADMIN_STATE_ADD_BALANCE_MANUALLY_AMOUNT:
        try:
            amount_to_add = float(text)
            if amount_to_add <= 0:
                await update.message.reply_text("المبلغ يجب أن يكون رقماً موجباً.", reply_markup=admin_cancel_inline_button())
                return
            
            target_user_id = context.user_data.get('add_balance_user_id')
            if target_user_id:
                db.update_user_balance(target_user_id, amount_to_add)
                current_balance = db.get_user_balance(target_user_id)
                await update.message.reply_text(f"تمت إضافة {amount_to_add:.2f} {CURRENCY_SYMBOL} إلى رصيد المستخدم `{target_user_id}`. رصيده الحالي: {current_balance:.2f} {CURRENCY_SYMBOL}.", reply_markup=admin_recharge_requests_menu_inline())
                
                # إرسال إشعار للمستخدم
                try:
                    await context.bot.send_message(chat_id=target_user_id, 
                                                   text=f"💰 تم إضافة رصيد يدوي إلى حسابك بقيمة {amount_to_add:.2f} {CURRENCY_SYMBOL} من قبل الإدارة.\nرصيدك الحالي: {current_balance:.2f} {CURRENCY_SYMBOL}.",
                                                   parse_mode='Markdown')
                except Exception as e:
                    logger.warning(f"Failed to notify user {target_user_id} about manual balance add: {e}")

            else:
                await update.message.reply_text("حدث خطأ في تحديد المستخدم. يرجى البدء من جديد.", reply_markup=admin_recharge_requests_menu_inline())
            
            del USER_STATE[user_id]
            context.user_data.pop('add_balance_user_id', None)
        except ValueError:
            await update.message.reply_text("مبلغ غير صالح. يرجى إدخال رقم.", reply_markup=admin_cancel_inline_button())


    # --- معالجة استعادة النسخ الاحتياطي ---
    elif current_state == ADMIN_STATE_RESTORE_FILE:
        if document:
            if document.file_name == DB_NAME:
                file_id = document.file_id
                new_file = await context.bot.get_file(file_id)
                
                try:
                    db.close()
                    await new_file.download_to_drive(DB_NAME)
                    
                    db.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
                    db.cursor = db.conn.cursor()

                    await update.message.reply_text("تمت استعادة قاعدة البيانات بنجاح! قد تحتاج لإعادة تشغيل البوت لتفعيل التغييرات بالكامل.", reply_markup=admin_backup_restore_menu_inline())
                except Exception as e:
                    logger.error(f"Error restoring database: {e}")
                    await update.message.reply_text(f"حدث خطأ أثناء استعادة قاعدة البيانات: {e}", reply_markup=admin_backup_restore_menu_inline())
            else:
                await update.message.reply_text(f"الملف الذي أرسلته ليس ملف قاعدة بيانات صالح. يجب أن يكون اسمه '{DB_NAME}'.", reply_markup=admin_cancel_inline_button())
            del USER_STATE[user_id]
        else:
            await update.message.reply_text("يرجى إرسال ملف قاعدة البيانات.", reply_markup=admin_cancel_inline_button())
        
    else:
        try:
            await update.message.reply_text("أمر غير معروف في لوحة الإدارة. يرجى استخدام الأزرار.", reply_markup=admin_main_menu_inline_keyboard())
        except BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info("Message content is the same, no modification needed.")
            else:
                logger.error(f"Error sending unknown admin command message: {e}")
