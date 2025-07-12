#database.py
import sqlite3
import datetime
from config import ADMIN_ID # تم استيراد ADMIN_ID لاستخدامه في get_admin_ids

class Database:
    def __init__(self, db_name="store_bot.db"):
        self.db_name = db_name
        # استخدام check_same_thread=False ضروري لـ SQLite مع AsyncIO
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        # جدول المستخدمين
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                balance REAL DEFAULT 0.0
            )
        ''')

        # جدول الفئات
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                parent_id INTEGER,
                FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE CASCADE
            )
        ''')

        # جدول المنتجات (الخدمات)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                price REAL NOT NULL,
                items_per_unit INTEGER DEFAULT 1000,
                category_id INTEGER,
                image_url TEXT,
                is_available INTEGER DEFAULT 1,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
            )
        ''')

        # جدول الطلبات
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id INTEGER,
                product_name TEXT NOT NULL,
                purchased_quantity INTEGER NOT NULL,
                price_per_unit REAL NOT NULL,
                total_amount REAL NOT NULL,
                status TEXT DEFAULT 'pending',
                order_details_input TEXT,
                order_date TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
            )
        ''')
        
        # جدول طلبات شحن الرصيد
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS recharge_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                full_name TEXT,
                amount REAL NOT NULL,
                payment_method TEXT NOT NULL,
                payment_details TEXT,
                status TEXT DEFAULT 'pending',
                request_date TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')

        self.conn.commit()

    # --- User Management ---
    def add_user(self, user_id: int, username: str, full_name: str):
        """
        يضيف مستخدمًا جديدًا إلى قاعدة البيانات إذا لم يكن موجودًا بالفعل.
        """
        self.cursor.execute("INSERT OR IGNORE INTO users (id, username, full_name, balance) VALUES (?, ?, ?, 0.0)",
                            (user_id, username, full_name))
        self.conn.commit()

    def get_user(self, user_id: int):
        """
        يسترجع جميع بيانات مستخدم واحد من قاعدة البيانات بناءً على user_id.
        يعيد صفًا (tuple) أو None إذا لم يتم العثور على المستخدم.
        الترتيب: (id, username, full_name, registered_at, balance)
        """
        self.cursor.execute("SELECT id, username, full_name, registered_at, balance FROM users WHERE id = ?", (user_id,))
        return self.cursor.fetchone()

    def user_exists(self, user_id: int) -> bool:
        """
        يتحقق مما إذا كان المستخدم موجودًا في قاعدة البيانات.
        يعيد True إذا كان موجودًا، False خلاف ذلك.
        """
        self.cursor.execute("SELECT 1 FROM users WHERE id = ?", (user_id,))
        return self.cursor.fetchone() is not None
    
    def get_all_users(self):
        """
        يسترجع جميع المستخدمين من قاعدة البيانات.
        يعيد قائمة من الصفوف (tuples).
        الترتيب: (id, username, full_name, registered_at, balance)
        """
        self.cursor.execute("SELECT id, username, full_name, registered_at, balance FROM users")
        return self.cursor.fetchall()

    def get_user_balance(self, user_id: int):
        """
        يسترجع رصيد المستخدم. يعيد 0.0 إذا لم يتم العثور على المستخدم.
        """
        self.cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result else 0.0

    def update_user_balance(self, user_id: int, amount: float):
        """
        يحدث رصيد المستخدم بإضافة المبلغ المحدد (يمكن أن يكون سالبًا للخصم).
        """
        self.cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, user_id))
        self.conn.commit()
    
    def update_user_info(self, user_id: int, username: str = None, full_name: str = None):
        """
        يقوم بتحديث معلومات المستخدم (مثل الاسم أو اسم المستخدم).
        """
        updates = []
        params = []
        if username is not None:
            updates.append("username = ?")
            params.append(username)
        if full_name is not None:
            updates.append("full_name = ?")
            params.append(full_name)
        
        if updates:
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            params.append(user_id)
            self.cursor.execute(query, tuple(params))
            self.conn.commit()
            return True
        return False

    # --- Category Management ---
    def add_category(self, name: str, parent_id: int = None):
        """
        يضيف فئة جديدة.
        """
        try:
            self.cursor.execute("INSERT INTO categories (name, parent_id) VALUES (?, ?)", (name, parent_id))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_all_categories(self, parent_id: int = None):
        """
        يسترجع جميع الفئات، أو الفئات الفرعية لفئة معينة.
        """
        if parent_id is None:
            self.cursor.execute("SELECT id, name FROM categories WHERE parent_id IS NULL") # تم تغيير OR parent_id = 0 لـ IS NULL
        else:
            self.cursor.execute("SELECT id, name FROM categories WHERE parent_id = ?", (parent_id,))
        return self.cursor.fetchall()

    def get_category_name(self, category_id: int):
        """
        يسترجع اسم الفئة بناءً على ID الخاص بها.
        """
        self.cursor.execute("SELECT name FROM categories WHERE id = ?", (category_id,))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def get_category_parent_id(self, category_id: int):
        """
        يسترجع الـ ID للفئة الأم لفئة معينة.
        """
        self.cursor.execute("SELECT parent_id FROM categories WHERE id = ?", (category_id,))
        result = self.cursor.fetchone()
        return result[0] if result else None
    
    def delete_category(self, category_id: int):
        """
        يحذف فئة بناءً على ID.
        """
        self.cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        self.conn.commit()

    # --- Product (Service) Management ---
    def add_product(self, name: str, description: str, price: float, items_per_unit: int, category_id: int, image_url: str = None, is_available: int = 1):
        """
        يضيف منتجًا جديدًا.
        """
        try:
            self.cursor.execute("INSERT INTO products (name, description, price, items_per_unit, category_id, image_url, is_available) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (name, description, price, items_per_unit, category_id, image_url, is_available))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_product_by_id(self, product_id: int):
        """
        يسترجع تفاصيل منتج واحد بناءً على ID الخاص به.
        """
        self.cursor.execute("SELECT id, name, description, price, items_per_unit, category_id, image_url, is_available FROM products WHERE id = ?", (product_id,))
        return self.cursor.fetchone()

    def get_all_products(self):
        """
        يسترجع جميع المنتجات المتوفرة.
        """
        self.cursor.execute("SELECT id, name, description, price, items_per_unit, category_id, image_url, is_available FROM products")
        return self.cursor.fetchall()

    def get_products_by_category(self, category_id: int):
        """
        يسترجع المنتجات ضمن فئة معينة.
        """
        self.cursor.execute("SELECT id, name, description, price, items_per_unit, category_id, image_url, is_available FROM products WHERE category_id = ?", (category_id,))
        return self.cursor.fetchall()
    
    def update_product(self, product_id: int, name: str = None, description: str = None, price: float = None, items_per_unit: int = None, category_id: int = None, image_url: str = None, is_available: int = None):
        """
        يحدث معلومات منتج بناءً على ID الخاص به.
        """
        updates = []
        params = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if price is not None:
            updates.append("price = ?")
            params.append(price)
        if items_per_unit is not None:
            updates.append("items_per_unit = ?")
            params.append(items_per_unit)
        if category_id is not None:
            updates.append("category_id = ?")
            params.append(category_id)
        if image_url is not None:
            updates.append("image_url = ?")
            params.append(image_url)
        if is_available is not None:
            updates.append("is_available = ?")
            params.append(is_available)
        
        if updates:
            query = f"UPDATE products SET {', '.join(updates)} WHERE id = ?"
            params.append(product_id)
            self.cursor.execute(query, tuple(params))
            self.conn.commit()
            return True
        return False

    def delete_product(self, product_id: int):
        """
        يحذف منتج بناءً على ID الخاص به.
        """
        self.cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        self.conn.commit()

    # --- Order Management ---
    def create_direct_order(self, user_id: int, product_id: int, product_name: str, purchased_quantity: int, price_per_unit: float, total_amount: float, order_details_input: str):
        """
        ينشئ طلب شراء مباشر.
        """
        self.cursor.execute("INSERT INTO orders (user_id, product_id, product_name, purchased_quantity, price_per_unit, total_amount, order_details_input, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')",
                            (user_id, product_id, product_name, purchased_quantity, price_per_unit, total_amount, order_details_input))
        order_id = self.cursor.lastrowid
        self.conn.commit()
        return order_id

    def get_user_orders(self, user_id: int):
        """
        يسترجع جميع طلبات مستخدم معين.
        """
        self.cursor.execute("SELECT id, product_name, purchased_quantity, total_amount, status, order_date, order_details_input FROM orders WHERE user_id = ? ORDER BY order_date DESC", (user_id,))
        return self.cursor.fetchall()

    def get_all_orders(self):
        """
        يسترجع جميع الطلبات في النظام.
        """
        self.cursor.execute('''
            SELECT o.id, u.username, o.product_name, o.purchased_quantity, o.total_amount, o.status, o.order_date, o.order_details_input
            FROM orders o JOIN users u ON o.user_id = u.id ORDER BY o.order_date DESC
        ''')
        return self.cursor.fetchall()

    def update_order_status(self, order_id: int, new_status: str):
        """
        يحدث حالة طلب معين.
        """
        self.cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
        self.conn.commit()
    
    # --- Recharge Requests Management ---
    def add_recharge_request(self, user_id: int, username: str, full_name: str, amount: float, payment_method: str, payment_details: str):
        """
        يضيف طلب شحن رصيد جديد.
        """
        self.cursor.execute("INSERT INTO recharge_requests (user_id, username, full_name, amount, payment_method, payment_details) VALUES (?, ?, ?, ?, ?, ?)",
                            (user_id, username, full_name, amount, payment_method, payment_details))
        request_id = self.cursor.lastrowid
        self.conn.commit()
        return request_id

    def get_all_recharge_requests(self, status: str = None):
        """
        يسترجع جميع طلبات شحن الرصيد، ويمكن تصفيتها حسب الحالة.
        """
        if status:
            self.cursor.execute("SELECT id, user_id, username, full_name, amount, payment_method, payment_details, status, request_date FROM recharge_requests WHERE status = ? ORDER BY request_date DESC", (status,))
        else:
            self.cursor.execute("SELECT id, user_id, username, full_name, amount, payment_method, payment_details, status, request_date FROM recharge_requests ORDER BY request_date DESC")
        return self.cursor.fetchall()
    
    def update_recharge_request_status(self, request_id: int, new_status: str):
        """
        يحدث حالة طلب شحن رصيد معين.
        """
        self.cursor.execute("UPDATE recharge_requests SET status = ? WHERE id = ?", (new_status, request_id))
        self.conn.commit()

    def get_recharge_request_details(self, request_id: int):
        """
        يسترجع تفاصيل طلب شحن رصيد معين.
        """
        self.cursor.execute("SELECT user_id, amount, status FROM recharge_requests WHERE id = ?", (request_id,))
        return self.cursor.fetchone()

    # دالة مساعدة للحصول على معرفات المديرين (من config.py)
    def get_admin_ids(self):
        return ADMIN_ID

    def close(self):
        """
        يغلق الاتصال بقاعدة البيانات.
        """
        self.conn.close()

# تهيئة كائن قاعدة البيانات عند استيراد الملف.
# هذا يضمن أن لديك كائن 'db' جاهز للاستخدام في ملفاتك الأخرى.
db = Database()
