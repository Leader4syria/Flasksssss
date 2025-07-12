#user_handlers.py
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from config import USER_STATE, CURRENCY_SYMBOL, BOT_USERNAME, PAYMENT_METHODS, ADMIN_ID
from keyboards import (
    start_keyboard, categories_keyboard, products_keyboard, product_detail_keyboard,
    my_account_keyboard, recharge_method_keyboard, confirm_purchase_keyboard
)
from database import db
import logging
import traceback # <--- إضافة هذا الاستيراد

logger = logging.getLogger(__name__)

# حالات المستخدمين (FSM - Finite State Machine)
USER_STATE_MAIN_MENU = "USER_MAIN_MENU"
USER_STATE_Browse_CATEGORIES = "USER_Browse_CATEGORIES"
USER_STATE_Browse_PRODUCTS = "USER_Browse_PRODUCTS"
USER_STATE_VIEWING_PRODUCT_DETAIL = "USER_VIEWING_PRODUCT_DETAIL"
USER_STATE_ENTERING_PURCHASE_DETAILS = "USER_ENTERING_PURCHASE_DETAILS"
USER_STATE_CONFIRMING_PURCHASE = "USER_CONFIRMING_PURCHASE"
USER_STATE_RECHARGE_AMOUNT = "USER_RECHARGE_AMOUNT"
USER_STATE_RECHARGE_DETAILS = "USER_RECHARGE_DETAILS"
USER_STATE_WAITING_FOR_ADMIN_RECHARGE = "USER_WAITING_FOR_ADMIN_RECHARGE"
USER_STATE_MY_ACCOUNT = "USER_MY_ACCOUNT" # حالة جديدة لحسابي

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    full_name = update.effective_user.full_name
    
    db.add_user(user_id, username, full_name)
    db.update_user_info(user_id, username, full_name)
    
    await update.message.reply_text("أهلاً بك في متجرنا! اختر من القائمة:", reply_markup=start_keyboard())
    USER_STATE[user_id] = USER_STATE_MAIN_MENU

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    try: # <--- إضافة كتلة try هنا لتغطية جميع معالجات الكولباك
        # --- القائمة الرئيسية للمستخدم ---
        if data == "start_menu":
            try:
                await query.message.edit_text("أهلاً بك في متجرنا! اختر من القائمة:", reply_markup=start_keyboard())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on start_menu: {e}")
            USER_STATE[user_id] = USER_STATE_MAIN_MENU
            return

        # --- تصفح الخدمات / الفئات ---
        elif data == "show_categories":
            categories = db.get_all_categories(parent_id=None)
            if categories:
                try:
                    await query.message.edit_text("اختر فئة لتصفح الخدمات:", reply_markup=categories_keyboard(categories, current_parent_id=None))
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on show_categories: {e}")
                USER_STATE[user_id] = USER_STATE_Browse_CATEGORIES
            else:
                try:
                    await query.message.edit_text("لا توجد فئات متاحة حالياً.", reply_markup=start_keyboard())
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on no categories: {e}")
                USER_STATE[user_id] = USER_STATE_MAIN_MENU
            return

        elif data.startswith("browse_cat_"):
            category_id = int(data.split('_')[2])
            subcategories = db.get_all_categories(parent_id=category_id)
            products = db.get_products_by_category(category_id)
            
            if subcategories:
                try:
                    await query.message.edit_text(
                        f"اختر فئة فرعية ضمن '{db.get_category_name(category_id)}':",
                        reply_markup=categories_keyboard(subcategories, current_parent_id=category_id)
                    )
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on browse_cat_ with subcategories: {e}")
                USER_STATE[user_id] = USER_STATE_Browse_CATEGORIES
            elif products:
                try:
                    await query.message.edit_text(
                        f"الخدمات في فئة '{db.get_category_name(category_id)}':",
                        reply_markup=products_keyboard(products, category_id)
                    )
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on browse_cat_ with products: {e}")
                USER_STATE[user_id] = USER_STATE_Browse_PRODUCTS
            else:
                try:
                    await query.message.edit_text(
                        f"لا توجد خدمات أو فئات فرعية في فئة '{db.get_category_name(category_id)}' حالياً.",
                        reply_markup=categories_keyboard([], current_parent_id=category_id) 
                    )
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on empty category: {e}")
                USER_STATE[user_id] = USER_STATE_Browse_CATEGORIES
            return

        elif data.startswith("show_product_"):
            product_id = int(data.split('_')[2])
            product = db.get_product_by_id(product_id)
            if product:
                name = product[1]
                description = product[2]
                price = product[3]
                items_per_unit = product[4]
                category_id = product[5]
                image_url = product[6]
                is_available = product[7]

                message_text = (
                    f"**خدمة:** {name}\n\n"
                    f"**الوصف:** {description}\n\n"
                    f"**السعر:** {price:.2f} {CURRENCY_SYMBOL} لكل {items_per_unit} وحدة\n"
                    f"**الحالة:** {'✅ متوفر' if is_available else '⛔ غير متوفر'}\n\n"
                    f"**رصيدك:** {db.get_user_balance(user_id):.2f} {CURRENCY_SYMBOL}"
                )
                
                try:
                    await query.message.delete()
                except Exception as e:
                    logger.warning(f"Failed to delete previous message: {e}")

                if image_url:
                    try:
                        await context.bot.send_photo(chat_id=user_id, photo=image_url, caption=message_text,
                                                    reply_markup=product_detail_keyboard(product_id, is_available), parse_mode='Markdown')
                    except Exception as e:
                        logger.warning(f"Failed to send photo for product {product_id}: {e}. Sending text instead.")
                        await context.bot.send_message(chat_id=user_id, text=message_text, reply_markup=product_detail_keyboard(product_id, is_available), parse_mode='Markdown')
                else:
                    await context.bot.send_message(chat_id=user_id, text=message_text, reply_markup=product_detail_keyboard(product_id, is_available), parse_mode='Markdown')

                USER_STATE[user_id] = USER_STATE_VIEWING_PRODUCT_DETAIL
                context.user_data['current_product_id'] = product_id
            else:
                try:
                    await query.message.edit_text("الخدمة المطلوبة غير موجودة.", reply_markup=start_keyboard())
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on product not found: {e}")
                USER_STATE[user_id] = USER_STATE_MAIN_MENU
            return
        
        elif data.startswith("back_to_products_from_detail_"):
            product_id = int(data.split('_')[4])
            product = db.get_product_by_id(product_id)
            if product:
                category_id = product[5]
                products_in_category = db.get_products_by_category(category_id)
                try:
                    await query.message.edit_text(
                        f"الخدمات في فئة '{db.get_category_name(category_id)}':",
                        reply_markup=products_keyboard(products_in_category, category_id)
                    )
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on back_to_products: {e}")
                USER_STATE[user_id] = USER_STATE_Browse_PRODUCTS
            else:
                categories = db.get_all_categories(parent_id=None)
                try:
                    await query.message.edit_text("عذراً، لم نتمكن من العثور على المنتجات. اختر فئة:", reply_markup=categories_keyboard(categories, current_parent_id=None))
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on back_to_products fallback: {e}")
                USER_STATE[user_id] = USER_STATE_Browse_CATEGORIES
            return

        elif data.startswith("buy_product_"):
            product_id = int(data.split('_')[2])
            product = db.get_product_by_id(product_id)
            if product and product[7]:
                context.user_data['purchase_product_id'] = product_id
                try:
                    await query.message.edit_text("الرجاء إدخال التفاصيل المطلوبة للخدمة (مثلاً: الرابط أو الاسم أو الرقم):", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="cancel_purchase")]]) )
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on buy_product prompt: {e}")
                USER_STATE[user_id] = USER_STATE_ENTERING_PURCHASE_DETAILS
            elif product and not product[7]:
                try:
                    await query.message.edit_text("الخدمة غير متوفرة حالياً.", reply_markup=product_detail_keyboard(product_id, False))
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on unavailable product: {e}")
            else:
                try:
                    await query.message.edit_text("الخدمة غير موجودة.", reply_markup=start_keyboard())
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on buy_product (not found): {e}")
                USER_STATE[user_id] = USER_STATE_MAIN_MENU
            return
        
        elif data == "cancel_purchase":
            if user_id in USER_STATE:
                del USER_STATE[user_id]
                context.user_data.pop('purchase_product_id', None)
                context.user_data.pop('purchase_details_input', None)
            try:
                await query.message.edit_text("تم إلغاء عملية الشراء.", reply_markup=start_keyboard())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on cancel purchase: {e}")
            return

        elif data.startswith("confirm_purchase_"):
            product_id = int(data.split('_')[2])
            product = db.get_product_by_id(product_id)
            purchase_details = context.user_data.get('purchase_details_input')
            
            if not product or not purchase_details:
                try:
                    await query.message.edit_text("حدث خطأ في بيانات الشراء. يرجى البدء من جديد.", reply_markup=start_keyboard())
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on confirm_purchase (data error): {e}")
                del USER_STATE[user_id]
                context.user_data.pop('purchase_product_id', None)
                context.user_data.pop('purchase_details_input', None)
                return

            user_balance = db.get_user_balance(user_id)
            product_price = product[3]
            product_name = product[1]
            purchased_quantity = 1
            total_amount = product_price

            if user_balance >= total_amount:
                db.update_user_balance(user_id, -total_amount)
                db.create_direct_order(user_id, product_id, product_name, purchased_quantity, product_price, total_amount, purchase_details)
                
                try:
                    await query.message.edit_text(f"✅ تم تأكيد شراء '{product_name}' بنجاح!\nسيتم تنفيذ طلبك قريباً.\nرصيدك الحالي: {db.get_user_balance(user_id):.2f} {CURRENCY_SYMBOL}", reply_markup=start_keyboard())
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on purchase confirmed: {e}")
                
                admin_message = (
                    f"🎉 **طلب جديد!**\n\n"
                    f"**المستخدم:** {update.effective_user.full_name} (@{update.effective_user.username or 'N/A'}) - ID: `{user_id}`\n"
                    f"**الخدمة:** {product_name}\n"
                    f"**الكمية:** {purchased_quantity}\n"
                    f"**السعر:** {total_amount:.2f} {CURRENCY_SYMBOL}\n"
                    f"**التفاصيل المدخلة:** {purchase_details}\n"
                    f"**الرصيد الحالي للمستخدم:** {db.get_user_balance(user_id):.2f} {CURRENCY_SYMBOL}"
                )
                for admin_id in ADMIN_ID:
                    try:
                        await context.bot.send_message(chat_id=admin_id, text=admin_message, parse_mode='Markdown')
                    except Exception as e:
                        logger.error(f"Failed to send new order notification to admin {admin_id}: {e}")

            else:
                try:
                    await query.message.edit_text(f"رصيدك غير كافٍ لإتمام عملية الشراء. رصيدك الحالي: {user_balance:.2f} {CURRENCY_SYMBOL}\nسعر الخدمة: {total_amount:.2f} {CURRENCY_SYMBOL}", reply_markup=recharge_method_keyboard(PAYMENT_METHODS))
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on insufficient balance: {e}")

            del USER_STATE[user_id]
            context.user_data.pop('purchase_product_id', None)
            context.user_data.pop('purchase_details_input', None)
            return

        # --- شحن الرصيد ---
        elif data == "recharge_balance":
            try:
                await query.message.edit_text("اختر طريقة الدفع لشحن رصيدك:", reply_markup=recharge_method_keyboard(PAYMENT_METHODS))
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on recharge_balance: {e}")
            return

        elif data.startswith("select_recharge_method_"):
            method_key = data.split('_')[3]
            if method_key in PAYMENT_METHODS:
                context.user_data['recharge_method'] = method_key
                try:
                    await query.message.edit_text(f"أدخل المبلغ الذي تريد شحنه ({CURRENCY_SYMBOL}).", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="start_menu")]]) )
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on select_recharge_method: {e}")
                USER_STATE[user_id] = USER_STATE_RECHARGE_AMOUNT
            else:
                try:
                    await query.message.edit_text("طريقة دفع غير صالحة.", reply_markup=recharge_method_keyboard(PAYMENT_METHODS))
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on invalid recharge method: {e}")
            return

        # --- حسابي ---
        elif data == "my_account":
            user_balance = db.get_user_balance(user_id)
            message = (
                f"**👤 حسابي**\n\n"
                f"**الرصيد الحالي:** {user_balance:.2f} {CURRENCY_SYMBOL}\n"
            )
            try:
                await query.message.edit_text(message, reply_markup=my_account_keyboard(), parse_mode='Markdown')
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on my_account: {e}")
            USER_STATE[user_id] = USER_STATE_MY_ACCOUNT
            return

        elif data == "view_my_orders":
            orders = db.get_user_orders(user_id)
            if not orders:
                try:
                    await query.message.edit_text("ليس لديك أي طلبات حالياً.", reply_markup=my_account_keyboard())
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error editing message on no user orders: {e}")
                return
            
            message = "**📊 طلباتي:**\n\n"
            for order_id, product_name, purchased_quantity, total_amount, status, order_date, order_details_input in orders:
                message += f"**الطلب رقم:** `{order_id}`\n" \
                           f"**الخدمة:** {product_name}\n" \
                           f"**الكمية:** {purchased_quantity}\n" \
                           f"**التكلفة:** {total_amount:.2f} {CURRENCY_SYMBOL}\n" \
                           f"**الحالة:** {status}\n" \
                           f"**التاريخ:** {order_date.split('.')[0]}\n" \
                           f"**التفاصيل المدخلة:** {order_details_input or 'لا يوجد'}\n\n"
            
            try:
                await query.message.edit_text(message, reply_markup=my_account_keyboard(), parse_mode='Markdown')
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error editing message on view_my_orders: {e}")
            return
    except Exception as e: # <--- نهاية كتلة try وبداية كتلة except
        logger.error(f"Error in handle_callback_query for user {user_id} (Data: {data}): {e}", exc_info=True)
        # إرسال رسالة خطأ للمستخدم
        try:
            await query.message.edit_text("عذراً، حدث خطأ غير متوقع أثناء معالجة طلبك. يرجى المحاولة مرة أخرى أو العودة إلى القائمة الرئيسية.", reply_markup=start_keyboard())
        except BadRequest as edit_error:
            logger.error(f"Failed to edit message with error notification for user {user_id}: {edit_error}")
            await context.bot.send_message(chat_id=user_id, text="عذراً، حدث خطأ غير متوقع أثناء معالجة طلبك. يرجى المحاولة مرة أخرى أو العودة إلى القائمة الرئيسية.", reply_markup=start_keyboard())

        # إرسال تفاصيل الخطأ للمدير
        error_message = (
            f"⚠️ **خطأ في بوت الخدمات الرقمية!**\n\n"
            f"**المستخدم:** {update.effective_user.full_name} (@{update.effective_user.username or 'N/A'}) - ID: `{user_id}`\n"
            f"**البيانات التي تم النقر عليها:** `{data}`\n"
            f"**الخطأ:** `{e}`\n"
            f"**تتبع الخطأ (Traceback):**\n```python\n{traceback.format_exc()}\n```"
        )
        for admin_id in ADMIN_ID:
            try:
                await context.bot.send_message(chat_id=admin_id, text=error_message, parse_mode='Markdown')
            except Exception as admin_send_error:
                logger.error(f"Failed to send error notification to admin {admin_id}: {admin_send_error}")
        USER_STATE[user_id] = USER_STATE_MAIN_MENU # إعادة المستخدم للحالة الرئيسية

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_state = USER_STATE.get(user_id)
    text = update.message.text

    try: # <--- إضافة كتلة try هنا لتغطية جميع معالجات الرسائل النصية
        if current_state == USER_STATE_ENTERING_PURCHASE_DETAILS:
            product_id = context.user_data.get('purchase_product_id')
            product = db.get_product_by_id(product_id)
            if product:
                context.user_data['purchase_details_input'] = text
                product_name = product[1]
                product_price = product[3]
                message_text = (
                    f"**تأكيد الشراء:**\n\n"
                    f"**الخدمة:** {product_name}\n"
                    f"**السعر:** {product_price:.2f} {CURRENCY_SYMBOL}\n"
                    f"**تفاصيلك المدخلة:** {text}\n\n"
                    f"**رصيدك الحالي:** {db.get_user_balance(user_id):.2f} {CURRENCY_SYMBOL}\n"
                    f"هل أنت متأكد من الشراء؟"
                )
                try:
                    await update.message.reply_text(message_text, reply_markup=confirm_purchase_keyboard(product_id), parse_mode='Markdown')
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error sending confirmation message: {e}")
                USER_STATE[user_id] = USER_STATE_CONFIRMING_PURCHASE
            else:
                try:
                    await update.message.reply_text("حدث خطأ في تحديد الخدمة. يرجى البدء من جديد.", reply_markup=start_keyboard())
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error sending product not found message during purchase: {e}")
                del USER_STATE[user_id]
                context.user_data.pop('purchase_product_id', None)
                context.user_data.pop('purchase_details_input', None)
            return
        
        elif current_state == USER_STATE_RECHARGE_AMOUNT:
            try:
                amount = float(text)
                if amount <= 0:
                    await update.message.reply_text("المبلغ يجب أن يكون رقماً موجباً.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="start_menu")]]))
                    return
                context.user_data['recharge_amount'] = amount
                method_key = context.user_data.get('recharge_method')
                method_info = PAYMENT_METHODS.get(method_key)
                
                if method_info:
                    payment_instructions = method_info['details'].format(
                        amount=f"{amount:.2f}",
                        currency=CURRENCY_SYMBOL,
                        account=method_info['account_info'],
                        bot_username=BOT_USERNAME
                    )
                    try:
                        await update.message.reply_text(
                            f"**لقد اخترت دفع {amount:.2f} {CURRENCY_SYMBOL} عبر {method_info['name']}.**\n"
                            f"يرجى إتباع التعليمات التالية لإتمام عملية الدفع:\n\n"
                            f"{payment_instructions}\n\n"
                            f"بعد إتمام الدفع، يرجى إرسال أي تفاصيل ذات صلة (مثل لقطة شاشة، رقم المعاملة، اسم المرسل) لتأكيد الدفع.",
                            parse_mode='Markdown',
                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء طلب الشحن", callback_data="start_menu")]])
                        )
                    except BadRequest as e:
                        if "Message is not modified" in str(e):
                            logger.info("Message content is the same, no modification needed.")
                        else:
                            logger.error(f"Error sending recharge instructions: {e}")
                    USER_STATE[user_id] = USER_STATE_RECHARGE_DETAILS
                else:
                    await update.message.reply_text("حدث خطأ في طريقة الدفع. يرجى البدء من جديد.", reply_markup=start_keyboard())
                    del USER_STATE[user_id]
                    context.user_data.pop('recharge_method', None)
                    context.user_data.pop('recharge_amount', None)
            except ValueError:
                await update.message.reply_text("مبلغ غير صالح. يرجى إدخال رقم.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="start_menu")]]))
            return
        
        elif current_state == USER_STATE_RECHARGE_DETAILS:
            amount = context.user_data.get('recharge_amount')
            method = context.user_data.get('recharge_method')
            details = text
            
            if amount and method:
                request_id = db.add_recharge_request(user_id, update.effective_user.username, update.effective_user.full_name, amount, method, details)
                
                try:
                    await update.message.reply_text(
                        "✅ تم استلام طلب شحن رصيدك بنجاح! سيتم مراجعته من قبل الإدارة قريباً.\n"
                        "سيتم إعلامك فور تحديث حالته.",
                        reply_markup=start_keyboard()
                    )
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error sending recharge request received message: {e}")
                
                admin_message = (
                    f"💰 **طلب شحن رصيد جديد!**\n\n"
                    f"**المستخدم:** {update.effective_user.full_name} (@{update.effective_user.username or 'N/A'}) - ID: `{user_id}`\n"
                    f"**المبلغ:** {amount:.2f} {CURRENCY_SYMBOL}\n"
                    f"**الطريقة:** {PAYMENT_METHODS.get(method, {}).get('name', method)}\n"
                    f"**تفاصيل الدفع:** {details}\n\n"
                    f"لإدارة الطلب: /manage_recharge_{request_id}"
                )
                for admin_id in ADMIN_ID:
                    try:
                        await context.bot.send_message(chat_id=admin_id, text=admin_message, parse_mode='Markdown')
                    except Exception as e:
                        logger.error(f"Failed to send recharge request notification to admin {admin_id}: {e}")

            else:
                try:
                    await update.message.reply_text("حدث خطأ في بيانات الشحن. يرجى البدء من جديد.", reply_markup=start_keyboard())
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        logger.info("Message content is the same, no modification needed.")
                    else:
                        logger.error(f"Error sending recharge data error message: {e}")
            
            del USER_STATE[user_id]
            context.user_data.pop('recharge_amount', None)
            context.user_data.pop('recharge_method', None)
            return

        if current_state in [USER_STATE_MAIN_MENU, USER_STATE_Browse_CATEGORIES, USER_STATE_Browse_PRODUCTS, USER_STATE_VIEWING_PRODUCT_DETAIL, USER_STATE_CONFIRMING_PURCHASE, USER_STATE_MY_ACCOUNT, USER_STATE_WAITING_FOR_ADMIN_RECHARGE]:
            try:
                await update.message.reply_text("يرجى استخدام الأزرار في لوحة المفاتيح للتنقل.", reply_markup=start_keyboard())
            except BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info("Message content is the same, no modification needed.")
                else:
                    logger.error(f"Error sending 'use buttons' message: {e}")
            return
    except Exception as e: # <--- نهاية كتلة try وبداية كتلة except
        logger.error(f"Error in handle_text_messages for user {user_id} (Text: {text}): {e}", exc_info=True)
        try:
            await update.message.reply_text("عذراً، حدث خطأ غير متوقع أثناء معالجة رسالتك. يرجى المحاولة مرة أخرى أو العودة إلى القائمة الرئيسية.", reply_markup=start_keyboard())
        except BadRequest as reply_error:
            logger.error(f"Failed to reply with error message for user {user_id}: {reply_error}")
        
        error_message = (
            f"⚠️ **خطأ في بوت الخدمات الرقمية!**\n\n"
            f"**المستخدم:** {update.effective_user.full_name} (@{update.effective_user.username or 'N/A'}) - ID: `{user_id}`\n"
            f"**الرسالة النصية:** `{text}`\n"
            f"**الحالة:** `{current_state}`\n"
            f"**الخطأ:** `{e}`\n"
            f"**تتبع الخطأ (Traceback):**\n```python\n{traceback.format_exc()}\n```"
        )
        for admin_id in ADMIN_ID:
            try:
                await context.bot.send_message(chat_id=admin_id, text=error_message, parse_mode='Markdown')
            except Exception as admin_send_error:
                logger.error(f"Failed to send error notification to admin {admin_id}: {admin_send_error}")
        USER_STATE[user_id] = USER_STATE_MAIN_MENU # إعادة المستخدم للحالة الرئيسية

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error {context.error}", exc_info=True) # <--- إضافة exc_info=True هنا
    user_id = update.effective_user.id if update.effective_user else None
    
    if user_id:
        try:
            await context.bot.send_message(chat_id=user_id, text="عذراً، حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى أو العودة إلى القائمة الرئيسية.", reply_markup=start_keyboard())
        except Exception as e:
            logger.error(f"Failed to send error message to user {user_id}: {e}")
    
    # إرسال الخطأ إلى المدير (سيتم إرساله من هنا كمعالج أخطاء عام)
    # يمكن تخصيص هذه الرسالة لتكون أكثر عمومية أو إضافة تفاصيل إضافية
    error_message = (
        f"🚨 **خطأ عام في البوت!**\n\n"
        f"**الخطأ:** `{context.error}`\n"
        f"**التحديث:** `{update}`\n"
        f"**تتبع الخطأ (Traceback):**\n```python\n{traceback.format_exc()}\n```"
    )
    for admin_id in ADMIN_ID:
        try:
            await context.bot.send_message(chat_id=admin_id, text=error_message, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Failed to send general error notification to admin {admin_id}: {e}")

