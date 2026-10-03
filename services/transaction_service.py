"""
Transaction Ledger Service.
Coordinates purchase, sale, and expense recording, inventory balance synchronization,
and profit calculation on individual sales.
"""
from typing import List, Optional, Dict, Any
from database.database import get_db, query_db, execute_db
from database.models import Transaction
from services.inventory_service import InventoryService
from config import Config

class TransactionService:
    def __init__(self, db_path: str = None):
        self.db_path = db_path
        self.inventory_service = InventoryService(db_path=self.db_path)

    def record_purchase(self, product_name: str, quantity: float, unit: str,
                        total_amount: float, supplier_name: Optional[str] = None,
                        notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Record a stock purchase transaction and increase available inventory.
        """
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        if total_amount <= 0:
            raise ValueError("Total amount must be greater than zero.")

        unit_cost = round(total_amount / quantity, 2)
        
        # Increase inventory and retrieve updated product record
        product = self.inventory_service.increase_stock(
            product_name=product_name,
            quantity=quantity,
            unit=unit,
            unit_cost=unit_cost
        )

        # Record transaction in database
        tx_id = execute_db("""
            INSERT INTO transactions (type, product_id, product_name, quantity, unit, unit_price, total_amount, party_name, category, profit, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            "PURCHASE", product.id, product.name, quantity, unit or product.unit,
            unit_cost, total_amount, supplier_name, product.category, 0.0, notes
        ), db_path=self.db_path)

        return {
            "transaction_id": tx_id,
            "type": "PURCHASE",
            "product_name": product.name,
            "quantity": quantity,
            "unit": unit or product.unit,
            "unit_price": unit_cost,
            "total_amount": total_amount,
            "supplier": supplier_name,
            "new_stock": product.current_stock,
            "cost_price": product.cost_price
        }

    def record_sale(self, product_name: str, quantity: float, unit: str,
                    total_amount: float, customer_name: Optional[str] = None,
                    notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Record a product sale transaction, validate & decrease inventory,
        and calculate sale profit: (Selling Price/Unit - Cost Price/Unit) * Quantity.
        """
        if quantity <= 0:
            raise ValueError("Sale quantity must be greater than zero.")
        if total_amount <= 0:
            raise ValueError("Sale amount must be greater than zero.")

        # Find product and calculate profit
        product = self.inventory_service.find_product_by_name(product_name)
        if not product:
            raise ValueError(f"Product '{product_name}' does not exist in inventory.")

        unit_selling_price = round(total_amount / quantity, 2)
        cost_price_unit = product.cost_price
        profit = round((unit_selling_price - cost_price_unit) * quantity, 2)

        # Decrease inventory (validates stock availability)
        updated_product = self.inventory_service.decrease_stock(product.name, quantity)

        # Record transaction in database
        tx_id = execute_db("""
            INSERT INTO transactions (type, product_id, product_name, quantity, unit, unit_price, total_amount, party_name, category, profit, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            "SALE", updated_product.id, updated_product.name, quantity,
            unit or updated_product.unit, unit_selling_price, total_amount,
            customer_name, updated_product.category, profit, notes
        ), db_path=self.db_path)

        return {
            "transaction_id": tx_id,
            "type": "SALE",
            "product_name": updated_product.name,
            "quantity": quantity,
            "unit": unit or updated_product.unit,
            "unit_price": unit_selling_price,
            "cost_price": cost_price_unit,
            "total_amount": total_amount,
            "customer": customer_name,
            "profit": profit,
            "new_stock": updated_product.current_stock
        }

    def record_expense(self, category: str, total_amount: float,
                       notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Record an operational overhead expense (rent, electricity, tea, etc.).
        """
        if total_amount <= 0:
            raise ValueError("Expense amount must be greater than zero.")

        tx_id = execute_db("""
            INSERT INTO transactions (type, product_id, product_name, quantity, unit, unit_price, total_amount, party_name, category, profit, notes, created_at)
            VALUES (?, NULL, NULL, NULL, NULL, NULL, ?, NULL, ?, 0.0, ?, CURRENT_TIMESTAMP)
        """, ("EXPENSE", total_amount, category, notes), db_path=self.db_path)

        return {
            "transaction_id": tx_id,
            "type": "EXPENSE",
            "category": category,
            "total_amount": total_amount,
            "notes": notes
        }

    def get_all_transactions(self, limit: int = 100, tx_type: Optional[str] = None, search: Optional[str] = None) -> List[Transaction]:
        """Retrieve filtered transaction history."""
        query = "SELECT * FROM transactions WHERE 1=1"
        params = []

        if tx_type and tx_type.upper() in ('PURCHASE', 'SALE', 'EXPENSE'):
            query += " AND type = ?"
            params.append(tx_type.upper())

        if search:
            query += " AND (product_name LIKE ? OR party_name LIKE ? OR category LIKE ? OR notes LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term, term])

        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)

        rows = query_db(query, tuple(params), db_path=self.db_path)
        return [Transaction.from_row(r) for r in rows]

    def get_recent_transactions(self, limit: int = 10) -> List[Transaction]:
        """Fetch latest transactions for the dashboard."""
        return self.get_all_transactions(limit=limit)

    def delete_transaction(self, tx_id: int) -> bool:
        """Delete transaction record by ID."""
        execute_db("DELETE FROM transactions WHERE id = ?", (tx_id,), db_path=self.db_path)
        return True
