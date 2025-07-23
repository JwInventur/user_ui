from dotenv import load_dotenv
import psycopg2
import hashlib
import tkinter as tk
from tkinter import messagebox, ttk, simpledialog
import requests
import sys
import os
import time

load_dotenv()

class AutoUpdater:
    class SplashScreen:
        def __init__(self, text="Suche nach Updates..."):
            self.root = tk.Tk()
            self.root.overrideredirect(True)
            self.root.geometry("320x100+600+300")
            self.label = tk.Label(self.root, text=text, font=("Arial", 14))
            self.label.pack(expand=True)
            self.root.update()
            self.start_time = time.time()

        def close(self, min_seconds=3):
            # Mindestens min_seconds anzeigen
            elapsed = time.time() - self.start_time
            wait_time = max(0, min_seconds - elapsed)
            if wait_time > 0:
                self.root.after(int(wait_time * 1000), self.root.destroy)
                self.root.mainloop()
            else:
                self.root.destroy()

    def __init__(self, app_version, version_url, update_url):
        self.app_version = app_version
        self.version_url = version_url
        self.update_url = update_url

    def check_for_update(self, root=None):
        splash = self.SplashScreen("Suche nach Updates...")
        try:
            response = requests.get(self.version_url, timeout=5)
            response.raise_for_status()
            latest_version = response.text.strip()
            if latest_version > self.app_version:
                splash.close(min_seconds=3)
                self.download_update(root)
        except Exception as ex:
            print("Update-Check-Fehler:", ex)
            splash.close(min_seconds=3)
            self.close_app(root)
        splash.close(min_seconds=3)

    def download_update(self, root=None):
        try:
            response = requests.get(self.update_url, timeout=20)
            response.raise_for_status()
            with open(__file__, "wb") as f:
                f.write(response.content)
            print("Update installiert – Neustart ...")
            time.sleep(2)
            if root:
                root.destroy()
            script_path = os.path.abspath(__file__)
            os.execv(sys.executable, [sys.executable, script_path] + sys.argv[1:])
        except Exception as ex:
            print("Update-Fehler:", ex)
            self.close_app(root)


    def close_app(self, root=None):
        print("Programm wird wegen Update-Fehler geschlossen.")
        time.sleep(2)
        if root:
            root.destroy()
        sys.exit(1)

APP_VERSION = "0.0.2"
UPDATE_URL = "https://raw.githubusercontent.com/JwInventur/user_ui/refs/heads/main/user_ui.py"
VERSION_URL = "https://raw.githubusercontent.com/JwInventur/user_ui/refs/heads/main/version.txt"

updater = AutoUpdater(APP_VERSION, VERSION_URL, UPDATE_URL)

class Database:
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname="postgres",
            user="postgres.uvevizcwjnaaqkkxzejq",
            password="OkX8emGinhfwr74i",
            host="aws-0-eu-central-1.pooler.supabase.com",
            port=6543
)

        self.create_tables()

    def create_tables(self):
        with self.conn.cursor() as cursor:
            # Categories
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL
                );
            """)
            # Inventory
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    id SERIAL PRIMARY KEY,
                    item_name TEXT NOT NULL,
                    quantity INTEGER,
                    description TEXT,
                    category TEXT
                );
            """)
            # Requests
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id SERIAL PRIMARY KEY,
                    user_name TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    category TEXT,
                    status TEXT DEFAULT 'Pending'
                );
            """)
            # Users
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                );
            """)
        self.conn.commit()

    # --- Category operations ---
    def get_categories(self):
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT name FROM categories;")
            return [row[0] for row in cursor.fetchall()]

    def add_category(self, name):
        with self.conn.cursor() as cursor:
            try:
                cursor.execute("INSERT INTO categories (name) VALUES (%s);", (name,))
                self.conn.commit()
                return True
            except psycopg2.errors.UniqueViolation:
                self.conn.rollback()
                return False

    def delete_category(self, name):
        with self.conn.cursor() as cursor:
            cursor.execute("DELETE FROM categories WHERE name = %s;", (name,))
            self.conn.commit()

    # --- User Operations ---
    def hash_password(self, password):
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    def add_user(self, username, password):
        with self.conn.cursor() as cursor:
            try:
                cursor.execute(
                    "INSERT INTO users (username, password_hash) VALUES (%s, %s);",
                    (username, self.hash_password(password))
                )
                self.conn.commit()
                return True
            except psycopg2.errors.UniqueViolation:
                self.conn.rollback()
                return False

    def delete_user(self, username):
        with self.conn.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE username = %s;", (username,))
            self.conn.commit()

    def reset_password(self, username, new_password):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET password_hash = %s WHERE username = %s;",
                (self.hash_password(new_password), username)
            )
            self.conn.commit()

    def verify_user(self, username, password):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT password_hash FROM users WHERE username = %s;",
                (username,)
            )
            result = cursor.fetchone()
            if not result:
                return False
            return self.hash_password(password) == result[0]

    def get_users(self):
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT id, username FROM users;")
            return cursor.fetchall()

    # --- Inventory Operations ---
    def get_inventory(self):
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT id, item_name, quantity, description, category FROM inventory;")
            return cursor.fetchall()

    def add_inventory_item(self, item_name, quantity, description="", category=""):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO inventory (item_name, quantity, description, category) VALUES (%s, %s, %s, %s) RETURNING id;",
                (item_name, quantity, description, category)
            )
            self.conn.commit()
            return cursor.fetchone()[0]

    def update_inventory_item(self, item_id, quantity, category=None):
        with self.conn.cursor() as cursor:
            if category is not None:
                cursor.execute(
                    "UPDATE inventory SET quantity = %s, category = %s WHERE id = %s;",
                    (quantity, category, item_id)
                )
            else:
                cursor.execute(
                    "UPDATE inventory SET quantity = %s WHERE id = %s;",
                    (quantity, item_id)
                )
            self.conn.commit()

    def delete_inventory_item(self, item_id):
        with self.conn.cursor() as cursor:
            cursor.execute("DELETE FROM inventory WHERE id = %s;", (item_id,))
            self.conn.commit()

    def update_inventory_item_full(self, item_id, name, quantity, description, category):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "UPDATE inventory SET item_name = %s, quantity = %s, description = %s, category = %s WHERE id = %s;",
                (name, quantity, description, category, item_id)
            )
            self.conn.commit()

    # --- Request Operations ---
    def get_requests(self):
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT id, user_name, item_name, quantity, category, status FROM requests;")
            return cursor.fetchall()

    def add_request(self, user_name, item_name, quantity, category=""):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO requests (user_name, item_name, quantity, category) VALUES (%s, %s, %s, %s) RETURNING id;",
                (user_name, item_name, quantity, category)
            )
            self.conn.commit()
            return cursor.fetchone()[0]

    def update_request_status(self, request_id, status):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "UPDATE requests SET status = %s WHERE id = %s;",
                (status, request_id)
            )
            self.conn.commit()

    def delete_request(self, request_id):
        with self.conn.cursor() as cursor:
            cursor.execute("DELETE FROM requests WHERE id = %s;", (request_id,))
            self.conn.commit()

    # --- Utility ---
    def close(self):
        self.conn.close()

class UserApp:
    def __init__(self, root):
        self.db = Database()
        self.root = root
        self.root.title("Logistics Manager — User Mode")
        self.username = None

        self.init_login_screen()

    def init_login_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        tk.Label(self.root, text="User Login", font=("Arial", 14, "bold")).pack(pady=20)
        tk.Label(self.root, text="Username:", font=("Arial", 12)).pack()
        self.username_var = tk.StringVar()
        tk.Entry(self.root, textvariable=self.username_var, font=("Arial", 12)).pack(pady=4)
        tk.Label(self.root, text="Password:", font=("Arial", 12)).pack()
        self.password_var = tk.StringVar()
        tk.Entry(self.root, textvariable=self.password_var, font=("Arial", 12), show="*").pack(pady=4)
        tk.Button(self.root, text="Login", font=("Arial", 12), command=self.check_login).pack(pady=12)

    def check_login(self):
        username = self.username_var.get().strip()
        password = self.password_var.get()
        if not username or not password:
            messagebox.showerror("Login Failed", "Please enter both username and password.")
            return
        if self.db.verify_user(username, password):
            self.username = username
            self.init_main_screen()
        else:
            messagebox.showerror("Login Failed", "Invalid username or password.")

    def init_main_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        # --- Top frame for side-by-side lists ---
        top_frame = tk.Frame(self.root)
        top_frame.pack(padx=10, pady=5, fill='both', expand=True)

        # Inventory List (left)
        inv_frame = tk.Frame(top_frame)
        inv_frame.pack(side='left', padx=5, fill='both', expand=True)
        tk.Label(inv_frame, text="Current Inventory (Available to You)", font=("Arial", 13, "bold")).pack(pady=3)

        # --- Searchbar + Category Filter (gemeinsame Zeile) ---
        search_frame = tk.Frame(inv_frame)
        search_frame.pack(fill='x', pady=(2, 4))

        tk.Label(search_frame, text="Search Item:").pack(side='left')
        self.inventory_search_var = tk.StringVar()
        tk.Entry(search_frame, textvariable=self.inventory_search_var, width=20).pack(side='left', padx=5)

        tk.Label(search_frame, text="   Category:").pack(side='left', padx=(10, 0))
        self.category_filter_var = tk.StringVar(value="All Categories")
        categories = ["All Categories"] + self.db.get_categories()
        self.category_filter_combo = ttk.Combobox(search_frame, values=categories, textvariable=self.category_filter_var, state="readonly", width=18)
        self.category_filter_combo.pack(side='left', padx=6)
        self.category_filter_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_inventory())


        tree_frame = tk.Frame(inv_frame)
        tree_frame.pack(fill='both', expand=True)
        self.inventory_tree = ttk.Treeview(tree_frame, columns=("ID", "Name", "Qty", "Desc", "Category"), show="headings")
        for col, w in zip(("ID", "Name", "Qty", "Desc", "Category"), (40, 150, 90, 180, 90)):
            self.inventory_tree.heading(col, text=col)
            self.inventory_tree.column(col, width=w)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.inventory_tree.yview)
        self.inventory_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        self.inventory_tree.pack(side='left', fill='both', expand=True, padx=(0,0), pady=(2,2))
        self.inventory_tree.bind("<Double-1>", self.on_inventory_double_click)

        
        
        # Requests List (right)
        reqs_frame = tk.Frame(top_frame)
        reqs_frame.pack(side='left', padx=12, fill='y', expand=True)
        tk.Label(reqs_frame, text="Your Requests", font=("Arial", 13, "bold")).pack(pady=3)
        
        # --- Searchbar Right ---
        search_frame = tk.Frame(reqs_frame)
        search_frame.pack(fill='x', pady=(2, 4))
        tk.Label(search_frame, text="Search Item:").pack(side='left')
        self.requests_search_var = tk.StringVar()
        tk.Entry(search_frame, textvariable=self.requests_search_var, width=20).pack(side='left', padx=5)

        self.requests_tree = ttk.Treeview(reqs_frame, columns=("ReqID", "Item", "Qty", "Status", "Category"), show="headings", height=10, selectmode="browse")
        for col, w in zip(("ReqID", "Item", "Qty", "Status", "Category"), (50, 120, 60, 85, 90)):
            self.requests_tree.heading(col, text=col)
            self.requests_tree.column(col, width=w)
        self.requests_tree.pack(pady=2, fill='y')
        
        # Delete Request button
        self.delete_btn = tk.Button(reqs_frame, text="Delete Selected Request", command=self.delete_selected_request, state='disabled')
        self.delete_btn.pack(pady=6)

        # Bind selection event to enable/disable delete button
        self.requests_tree.bind("<<TreeviewSelect>>", self.on_request_select)


        # --- Request new item ---
        new_frame = tk.Frame(self.root, padx=5, pady=5, relief=tk.RIDGE, bd=2)
        new_frame.pack(pady=5, fill='x', padx=10)
        tk.Label(new_frame, text="Request New Item", font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=3, sticky='w', pady=5)
        tk.Label(new_frame, text="Item Name:").grid(row=1, column=0, sticky='w')
        self.new_item_name = tk.StringVar()
        tk.Entry(new_frame, textvariable=self.new_item_name, width=16).grid(row=1, column=1, padx=5)
        tk.Label(new_frame, text="Quantity:").grid(row=1, column=2, sticky='w')
        self.new_item_qty = tk.StringVar()
        tk.Entry(new_frame, textvariable=self.new_item_qty, width=8).grid(row=1, column=3, padx=5)
        tk.Label(new_frame, text="Description (optional):").grid(row=2, column=0, sticky='w')
        self.new_item_desc = tk.StringVar()
        tk.Entry(new_frame, textvariable=self.new_item_desc, width=30).grid(row=2, column=1, columnspan=3, pady=2, sticky='w')

        # CATEGORY DROPDOWN for exclusive selection
        tk.Label(new_frame, text="Category:").grid(row=1, column=4, sticky='w', padx=8)
        self.category_var = tk.StringVar()
        categories = self.db.get_categories()
        self.category_combo = ttk.Combobox(new_frame, textvariable=self.category_var, values=categories, state="readonly", width=12)
        self.category_combo.grid(row=1, column=5, padx=4)
        if categories:
            self.category_combo.current(0)  # select first by default

        tk.Button(new_frame, text="Request New Item", command=self.request_new_item).grid(row=3, column=0, columnspan=6, pady=5)

        # Exit button
        tk.Button(self.root, text="Exit", command=self.on_exit).pack(pady=10)

        self.refresh_inventory()
        self.refresh_user_requests()
        self.auto_refresh()


    def refresh_inventory(self):
        selected_id = None
        selected = self.inventory_tree.selection()
        if selected:
            selected_values = self.inventory_tree.item(selected[0])['values']
            if selected_values:
                selected_id = selected_values[0]

        inventory_rows = self.db.get_inventory()

        # Summe aller Pending/Approved-Requests pro Item
        all_requests = [
            r for r in self.db.get_requests()
            if r[5] in ("Pending", "Approved")
        ]
        requested_qty = {}
        for req in all_requests:
            item_name = req[2]
            qty = req[3]
            requested_qty[item_name] = requested_qty.get(item_name, 0) + qty

        self.inventory_tree.delete(*self.inventory_tree.get_children())

        selected_cat = self.category_filter_var.get()
        search_term = self.inventory_search_var.get().strip().lower() if hasattr(self, "inventory_search_var") else ""

        for row in inventory_rows:
            item_id, item_name, quantity, desc, category = row

            # Filter nach Kategorie
            if selected_cat != "All Categories" and category != selected_cat:
                continue

            # Filter nach Suchbegriff (falls gesetzt)
            if search_term and search_term not in item_name.lower():
                continue

            # Verfügbare Menge berechnen
            if quantity is None:
                qty_display = ""
            else:
                qty_left = quantity - requested_qty.get(item_name, 0)
                qty_left = max(qty_left, 0)
                qty_display = qty_left

            tree_id = self.inventory_tree.insert(
                "", "end", values=(item_id, item_name, qty_display, desc, category)
            )

            if selected_id == item_id:
                self.inventory_tree.selection_set(tree_id)
                self.inventory_tree.focus(tree_id)

         



    def refresh_user_requests(self):
        # 1. Save selected request ID (if any)
        selected = self.requests_tree.selection()
        selected_id = None
        if selected:
            selected_id = self.requests_tree.item(selected[0])['values'][0]

        # 2. Get all requests for this user
        user_reqs = [
            (r[0], r[2], r[3], r[5], r[4])  # (ReqID, Item, Qty, Status, Category)
            for r in self.db.get_requests() if r[1] == self.username
        ]

        # 3. Filter by search term (if search bar is present)
        search_term = self.requests_search_var.get().strip().lower() if hasattr(self, "requests_search_var") else ""
        if search_term:
            user_reqs = [req for req in user_reqs if search_term in req[1].lower()]

        # 4. Delete all and re-insert filtered
        self.requests_tree.delete(*self.requests_tree.get_children())
        for req in user_reqs:
            self.requests_tree.insert("", "end", values=req)

        # 5. Reselect the previously selected item (if present)
        if selected_id is not None:
            for iid in self.requests_tree.get_children():
                if self.requests_tree.item(iid)['values'][0] == selected_id:
                    self.requests_tree.selection_set(iid)
                    self.requests_tree.focus(iid)
                    break

        # 6. Disable delete button until a selection is made again
        self.delete_btn['state'] = 'disabled'


    def refresh_categories(self):
        categories = ["All Categories"] + self.db.get_categories()
        if hasattr(self, "category_filter_combo"):
            old_value = self.category_filter_var.get()
            self.category_filter_combo['values'] = categories
            if old_value in categories:
                self.category_filter_var.set(old_value)
            else:
                self.category_filter_var.set("All Categories")

    def on_request_select(self, event):
        selected = self.requests_tree.selection()
        if selected:
            self.delete_btn['state'] = 'normal'
        else:
            self.delete_btn['state'] = 'disabled'

    def delete_selected_request(self):
        selected = self.requests_tree.selection()
        if not selected:
            return
        req_id = self.requests_tree.item(selected[0])['values'][0]
        req_item = self.requests_tree.item(selected[0])['values'][1]
        req_status = self.requests_tree.item(selected[0])['values'][3]

        if not messagebox.askyesno("Confirm Delete", f"Delete request {req_id} for '{req_item}'?"):
            return

        self.db.delete_request(req_id)
        self.refresh_user_requests()
        self.refresh_inventory()

    def request_existing_item(self):
        try:
            item_id = int(self.selected_item_id.get())
            quantity = int(self.request_qty.get())
            if quantity <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid Item ID and quantity.")
            return

        inventory_map = {row[0]: row for row in self.db.get_inventory()}
        if item_id not in inventory_map:
            messagebox.showerror("Not Found", "Item ID not found in inventory.")
            return

        # Unpack full row, for robustness
        _, item_name, total_qty, desc, category = inventory_map[item_id]

        current_requested = sum(
            r[3] for r in self.db.get_requests()
            if r[2] == item_name and r[5] in ("Pending", "Approved")
        )
        available_qty = total_qty - current_requested if total_qty is not None else None

        if total_qty is not None and quantity > available_qty:
            proceed = messagebox.askyesno(
                "Insufficient Inventory",
                f"Only {available_qty} units of '{item_name}' are available.\n"
                f"Do you want to request {quantity} anyway?"
            )
            if not proceed:
                return

        # Add the request with the *existing* category from inventory
        self.db.add_request(self.username, item_name, quantity, category)
        self.selected_item_id.set("")
        self.request_qty.set("")
        self.refresh_user_requests()
        self.refresh_inventory()


    def request_new_item(self):
        name = self.new_item_name.get().strip()
        desc = self.new_item_desc.get().strip()
        category = self.category_var.get()

        try:
            quantity = int(self.new_item_qty.get())
            if not name or quantity <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid item name and quantity.")
            return

        if not category:
            messagebox.showerror("Category Required", "Please select a category.")
            return

        # 🔍 Check if item already exists in inventory
        inventory_items = self.db.get_inventory()
        for item in inventory_items:
            inv_id, inv_name, inv_qty, inv_desc, inv_cat = item
            if inv_name.strip().lower() == name.lower():
                messagebox.showwarning(
                    "Item Already Exists",
                    f"The item '{name}' already exists in the inventory.\nPlease request it using the 'Current Inventory' section."
                )
                return

        # ✅ Proceed to add request
        self.db.add_request(self.username, name, quantity, category)
        messagebox.showinfo("Request Submitted", f"Requested new item '{name}' (Qty: {quantity}, Category: {category}).")

        self.new_item_name.set("")
        self.new_item_qty.set("")
        self.new_item_desc.set("")

        self.refresh_user_requests()
        self.refresh_inventory()


    def on_exit(self):
        self.db.close()
        self.root.destroy()

    def auto_refresh(self):
        self.refresh_inventory()
        self.refresh_user_requests()
        self.refresh_categories()
        self.root.after(2000, self.auto_refresh)


    def on_inventory_double_click(self, event):
        item = self.inventory_tree.identify_row(event.y)
        if not item:
            return

        item_values = self.inventory_tree.item(item)['values']
        if not item_values or len(item_values) < 2:
            return

        item_id = item_values[0]
        item_name = item_values[1]

        qty_str = tk.simpledialog.askstring("Request Item", f"Enter quantity for '{item_name}':", parent=self.root)
        if not qty_str:
            return
        try:
            quantity = int(qty_str)
            if quantity <= 0:
                raise ValueError
        except:
            messagebox.showerror("Invalid input", "Please enter a valid positive number.")
            return

        # Hole vollständige Inventardaten
        inventory_map = {row[0]: row for row in self.db.get_inventory()}
        if item_id not in inventory_map:
            messagebox.showerror("Not Found", "Item not found in inventory.")
            return

        _, item_name, total_qty, desc, category = inventory_map[item_id]

        current_requested = sum(
            r[3] for r in self.db.get_requests()
            if r[2] == item_name and r[5] in ("Pending", "Approved")
        )
        available_qty = total_qty - current_requested if total_qty is not None else None

        if total_qty is not None and quantity > available_qty:
            proceed = messagebox.askyesno(
                "Insufficient Inventory",
                f"Only {available_qty} units of '{item_name}' are available.\n"
                f"Do you want to request {quantity} anyway?"
            )
            if not proceed:
                return

        self.db.add_request(self.username, item_name, quantity, category)
        self.refresh_user_requests()
        self.refresh_inventory()


if __name__ == "__main__":
    updater = AutoUpdater(APP_VERSION, VERSION_URL, UPDATE_URL)
    updater.check_for_update()

    root = tk.Tk()
    app = UserApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_exit)
    root.mainloop()
