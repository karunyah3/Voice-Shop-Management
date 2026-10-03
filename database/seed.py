import sqlite3
import os
import sys
from datetime import datetime, timedelta

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from .database import get_db, init_db
from config import Config

SAMPLE_PRODUCTS = [
    {"name": "Rice", "category": "Grains & Staples", "unit": "kg", "current_stock": 50.0, "cost_price": 40.0, "selling_price": 50.0, "min_stock_alert": 10.0},
    {"name": "Sugar", "category": "Grains & Staples", "unit": "kg", "current_stock": 40.0, "cost_price": 35.0, "selling_price": 45.0, "min_stock_alert": 10.0},
    {"name": "Biscuits", "category": "Snacks & Beverages", "unit": "packets", "current_stock": 30.0, "cost_price": 20.0, "selling_price": 30.0, "min_stock_alert": 8.0},
    {"name": "Sunflower Oil", "category": "Cooking Oils", "unit": "liters", "current_stock": 25.0, "cost_price": 120.0, "selling_price": 150.0, "min_stock_alert": 5.0},
    {"name": "Tea Powder", "category": "Snacks & Beverages", "unit": "packets", "current_stock": 20.0, "cost_price": 70.0, "selling_price": 90.0, "min_stock_alert": 5.0},
    {"name": "Wheat Flour", "category": "Grains & Staples", "unit": "kg", "current_stock": 45.0, "cost_price": 30.0, "selling_price": 38.0, "min_stock_alert": 10.0},
    {"name": "Milk", "category": "Dairy & Bakery", "unit": "liters", "current_stock": 15.0, "cost_price": 28.0, "selling_price": 34.0, "min_stock_alert": 5.0},
    {"name": "Bath Soap", "category": "Personal Care", "unit": "pieces", "current_stock": 40.0, "cost_price": 25.0, "selling_price": 35.0, "min_stock_alert": 10.0},
    {"name": "Salt", "category": "Grains & Staples", "unit": "packets", "current_stock": 35.0, "cost_price": 15.0, "selling_price": 22.0, "min_stock_alert": 8.0},
    {"name": "Toor Dal", "category": "Grains & Staples", "unit": "kg", "current_stock": 30.0, "cost_price": 110.0, "selling_price": 140.0, "min_stock_alert": 8.0}
]

def seed_database(db_path: str = None, force_reset: bool = False):
    """
    Seed initial products and sample transactions into the SQLite database.
    If products already exist and force_reset is False, leaves data intact.
    """
    if db_path is None:
        db_path = Config.DATABASE_PATH

    init_db(db_path)
    conn = get_db(db_path)
    cur = conn.cursor()

    if force_reset:
        cur.execute("DELETE FROM pending_contexts")
        cur.execute("DELETE FROM transactions")
        cur.execute("DELETE FROM products")
        conn.commit()

    # Check if products already exist
    cur.execute("SELECT COUNT(*) as count FROM products")
    count = cur.fetchone()['count']

    if count == 0:
        print(f"[*] Seeding {len(SAMPLE_PRODUCTS)} initial products into {db_path}...")
        for p in SAMPLE_PRODUCTS:
            cur.execute("""
                INSERT INTO products (name, category, unit, current_stock, cost_price, selling_price, min_stock_alert)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (p["name"], p["category"], p["unit"], p["current_stock"], p["cost_price"], p["selling_price"], p["min_stock_alert"]))
        conn.commit()

        # Seed realistic transactions
        # 1. Past Purchases
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)

        cur.execute("SELECT id, name, unit, cost_price, selling_price FROM products WHERE name = 'Rice'")
        rice = cur.fetchone()
        cur.execute("SELECT id, name, unit, cost_price, selling_price FROM products WHERE name = 'Biscuits'")
        biscuits = cur.fetchone()
        cur.execute("SELECT id, name, unit, cost_price, selling_price FROM products WHERE name = 'Sugar'")
        sugar = cur.fetchone()

        sample_txns = [
            # Initial purchases
            ("PURCHASE", rice['id'], rice['name'], 50.0, rice['unit'], 40.0, 2000.0, "Kumar Suppliers", "Grains & Staples", 0.0, "Initial wholesale stock purchase", two_days_ago.strftime("%Y-%m-%d %H:%M:%S")),
            ("PURCHASE", biscuits['id'], biscuits['name'], 40.0, biscuits['unit'], 20.0, 800.0, "Metro Wholesale", "Snacks & Beverages", 0.0, "Stock refill", two_days_ago.strftime("%Y-%m-%d %H:%M:%S")),
            ("PURCHASE", sugar['id'], sugar['name'], 45.0, sugar['unit'], 35.0, 1575.0, "Ramesh Agencies", "Grains & Staples", 0.0, "Sugar stock batch", two_days_ago.strftime("%Y-%m-%d %H:%M:%S")),
            
            # Initial Sales
            ("SALE", biscuits['id'], biscuits['name'], 10.0, biscuits['unit'], 30.0, 300.0, "Walk-in Customer", "Snacks & Beverages", (30.0 - 20.0) * 10.0, "Sold 10 packets biscuits", yesterday.strftime("%Y-%m-%d %H:%M:%S")),
            ("SALE", sugar['id'], sugar['name'], 5.0, sugar['unit'], 45.0, 225.0, "Rahul", "Grains & Staples", (45.0 - 35.0) * 5.0, "Sold 5 kg sugar to Rahul", yesterday.strftime("%Y-%m-%d %H:%M:%S")),
            
            # Initial Expenses
            ("EXPENSE", None, None, None, None, None, 450.0, None, "Electricity", 0.0, "Paid monthly electricity bill", yesterday.strftime("%Y-%m-%d %H:%M:%S")),
            ("EXPENSE", None, None, None, None, None, 80.0, None, "Tea & Snacks", 0.0, "Staff evening tea and snacks", now.strftime("%Y-%m-%d %H:%M:%S"))
        ]

        for tx in sample_txns:
            cur.execute("""
                INSERT INTO transactions (type, product_id, product_name, quantity, unit, unit_price, total_amount, party_name, category, profit, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, tx)
        conn.commit()
        print(f"[+] Seeding completed successfully. Sample transactions and inventory ready.")
    else:
        print(f"[*] Database already contains {count} products. Skipping seed.")

    if not os.environ.get('FLASK_ENV'):
        conn.close()

if __name__ == "__main__":
    seed_database(force_reset=True)
