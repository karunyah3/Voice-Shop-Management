"""
Inventory Management Service.
Handles stock checking, updates, negative stock prevention, and catalog lookup.
"""
from typing import List, Optional, Dict, Any
from database.database import get_db, query_db, execute_db
from database.models import Product
from config import Config

class InventoryService:
    def __init__(self, db_path: str = None):
        self.db_path = db_path

    def get_all_products(self) -> List[Product]:
        """Retrieve all products ordered by name."""
        rows = query_db("SELECT * FROM products ORDER BY name ASC", db_path=self.db_path)
        return [Product.from_row(r) for r in rows]

    def find_product_by_name(self, name: str) -> Optional[Product]:
        """Case-insensitive product search by exact name or match."""
        if not name:
            return None
        cleaned = name.strip()
        row = query_db("SELECT * FROM products WHERE name = ? COLLATE NOCASE", (cleaned,), one=True, db_path=self.db_path)
        if row:
            return Product.from_row(row)
        
        # Substring search fallback (e.g. 'rice' matches 'Basmati Rice')
        row = query_db("SELECT * FROM products WHERE name LIKE ? COLLATE NOCASE LIMIT 1", (f"%{cleaned}%",), one=True, db_path=self.db_path)
        if row:
            return Product.from_row(row)
        return None

    def get_product_by_id(self, product_id: int) -> Optional[Product]:
        """Find product by primary key id."""
        row = query_db("SELECT * FROM products WHERE id = ?", (product_id,), one=True, db_path=self.db_path)
        return Product.from_row(row) if row else None

    def add_product(self, name: str, category: str = "General", unit: str = "pcs",
                    current_stock: float = 0.0, cost_price: float = 0.0,
                    selling_price: float = 0.0, min_stock_alert: float = 5.0) -> Product:
        """Add a new product to inventory."""
        cleaned_name = name.strip().title()
        pid = execute_db("""
            INSERT INTO products (name, category, unit, current_stock, cost_price, selling_price, min_stock_alert, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (cleaned_name, category, unit, current_stock, cost_price, selling_price, min_stock_alert), db_path=self.db_path)
        return self.get_product_by_id(pid)

    def increase_stock(self, product_name: str, quantity: float, unit: str = "pcs",
                       unit_cost: Optional[float] = None, category: str = "General") -> Product:
        """
        Increase product stock upon purchase.
        If product does not exist, automatically register it in inventory catalog.
        """
        if quantity <= 0:
            raise ValueError("Purchase quantity must be greater than zero.")

        product = self.find_product_by_name(product_name)
        if not product:
            # Auto-create product
            cost_p = unit_cost if unit_cost is not None else 0.0
            sell_p = cost_p * 1.25 if cost_p > 0 else 0.0 # 25% default markup if unknown
            product = self.add_product(
                name=product_name,
                category=category,
                unit=unit,
                current_stock=quantity,
                cost_price=cost_p,
                selling_price=sell_p
            )
            return product

        # Update existing product stock and weighted average cost price
        new_stock = product.current_stock + quantity
        new_cost_price = product.cost_price
        
        if unit_cost is not None and unit_cost > 0:
            # Weighted average cost calculation
            if product.current_stock > 0 and product.cost_price > 0:
                total_val = (product.current_stock * product.cost_price) + (quantity * unit_cost)
                new_cost_price = round(total_val / new_stock, 2)
            else:
                new_cost_price = unit_cost

        execute_db("""
            UPDATE products 
            SET current_stock = ?, cost_price = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_stock, new_cost_price, product.id), db_path=self.db_path)

        return self.get_product_by_id(product.id)

    def decrease_stock(self, product_name: str, quantity: float) -> Product:
        """
        Decrease product stock upon sale with strict negative stock prevention.
        Raises ValueError if current stock is insufficient.
        """
        if quantity <= 0:
            raise ValueError("Sale quantity must be greater than zero.")

        product = self.find_product_by_name(product_name)
        if not product:
            raise ValueError(f"Product '{product_name}' not found in inventory catalog.")

        # Strict validation: Never allow negative stock
        if product.current_stock < quantity:
            raise ValueError(
                f"Insufficient stock for '{product.name}'. "
                f"Available stock: {product.current_stock:g} {product.unit}, "
                f"requested: {quantity:g} {product.unit}."
            )

        new_stock = product.current_stock - quantity
        execute_db("""
            UPDATE products 
            SET current_stock = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_stock, product.id), db_path=self.db_path)

        return self.get_product_by_id(product.id)

    def get_stock_summary(self) -> Dict[str, Any]:
        """Compute aggregate stock metrics and low-stock warnings."""
        products = self.get_all_products()
        total_items = sum(p.current_stock for p in products)
        total_valuation = sum(p.current_stock * p.cost_price for p in products)
        potential_revenue = sum(p.current_stock * p.selling_price for p in products)
        
        low_stock = [p.to_dict() for p in products if p.current_stock <= p.min_stock_alert]

        return {
            "total_products": len(products),
            "total_items": round(total_items, 2),
            "total_valuation": round(total_valuation, 2),
            "potential_revenue": round(potential_revenue, 2),
            "low_stock_count": len(low_stock),
            "low_stock_items": low_stock
        }
