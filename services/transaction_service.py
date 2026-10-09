"""
Transaction Ledger Service.
Coordinates purchase, sale, and expense recording, inventory balance synchronization,
profit calculation on individual sales, safe reversals with stock restoration,
advanced date/type filtering, and CSV report export.
"""
import io
import csv
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from database.database import get_db, query_db, execute_db
from database.models import Transaction, Product
from services.inventory_service import InventoryService
from config import Config

class TransactionService:
    def __init__(self, db_path: str = None):
        self.db_path = db_path
        self.inventory_service = InventoryService(db_path=self.db_path)

    def get_transaction_by_id(self, tx_id: int) -> Optional[Transaction]:
        """Find transaction by primary key ID."""
        row = query_db("SELECT * FROM transactions WHERE id = ?", (tx_id,), one=True, db_path=self.db_path)
        return Transaction.from_row(row) if row else None

    def record_purchase(self, product_name: str, quantity: float, unit: str,
                        total_amount: float, supplier_name: Optional[str] = None,
                        notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Record a stock purchase transaction and increase available inventory.
        Includes duplicate submission protection (2-second idempotency window).
        """
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")
        if total_amount <= 0:
            raise ValueError("Total amount must be greater than zero.")

        # Duplicate submission protection
        dup_check = query_db("""
            SELECT id, product_name, quantity, unit, unit_price, total_amount, party_name
            FROM transactions
            WHERE type = 'PURCHASE' AND product_name = ? COLLATE NOCASE AND quantity = ? AND total_amount = ?
              AND created_at >= datetime('now', '-2 seconds')
            ORDER BY id DESC LIMIT 1
        """, (product_name, quantity, total_amount), one=True, db_path=self.db_path)
        if dup_check:
            prod = self.inventory_service.find_product_by_name(product_name)
            return {
                "transaction_id": dup_check['id'],
                "type": "PURCHASE",
                "product_name": dup_check['product_name'],
                "quantity": dup_check['quantity'],
                "unit": dup_check['unit'],
                "unit_price": dup_check['unit_price'],
                "total_amount": dup_check['total_amount'],
                "supplier": dup_check['party_name'],
                "new_stock": prod.current_stock if prod else quantity,
                "is_duplicate": True
            }

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
        Includes duplicate submission protection.
        """
        if quantity <= 0:
            raise ValueError("Sale quantity must be greater than zero.")
        if total_amount <= 0:
            raise ValueError("Sale amount must be greater than zero.")

        # Find product and calculate profit
        product = self.inventory_service.find_product_by_name(product_name)
        if not product:
            raise ValueError(f"Product '{product_name}' does not exist in inventory.")

        # Duplicate submission protection
        dup_check = query_db("""
            SELECT id, product_name, quantity, unit, unit_price, total_amount, party_name, profit
            FROM transactions
            WHERE type = 'SALE' AND product_name = ? COLLATE NOCASE AND quantity = ? AND total_amount = ?
              AND created_at >= datetime('now', '-2 seconds')
            ORDER BY id DESC LIMIT 1
        """, (product.name, quantity, total_amount), one=True, db_path=self.db_path)
        if dup_check:
            return {
                "transaction_id": dup_check['id'],
                "type": "SALE",
                "product_name": dup_check['product_name'],
                "quantity": dup_check['quantity'],
                "unit": dup_check['unit'],
                "unit_price": dup_check['unit_price'],
                "cost_price": product.cost_price,
                "total_amount": dup_check['total_amount'],
                "customer": dup_check['party_name'],
                "profit": dup_check['profit'],
                "new_stock": product.current_stock,
                "is_duplicate": True
            }

        unit_selling_price = round(total_amount / quantity, 2)
        cost_price_unit = product.cost_price
        profit = round((unit_selling_price - cost_price_unit) * quantity, 2)

        # Decrease inventory (validates stock availability, raises ValueError on negative stock)
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

    def get_all_transactions(self, limit: int = 100, tx_type: Optional[str] = None,
                             search: Optional[str] = None, start_date: Optional[str] = None,
                             end_date: Optional[str] = None) -> List[Transaction]:
        """Retrieve filtered transaction history with optional date range."""
        query = "SELECT * FROM transactions WHERE 1=1"
        params = []

        if tx_type and tx_type.upper() in ('PURCHASE', 'SALE', 'EXPENSE'):
            query += " AND type = ?"
            params.append(tx_type.upper())

        if search:
            query += " AND (product_name LIKE ? OR party_name LIKE ? OR category LIKE ? OR notes LIKE ? OR CAST(id AS TEXT) LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term, term, term])

        if start_date:
            query += " AND DATE(created_at) >= DATE(?)"
            params.append(start_date)

        if end_date:
            query += " AND DATE(created_at) <= DATE(?)"
            params.append(end_date)

        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)

        rows = query_db(query, tuple(params), db_path=self.db_path)
        return [Transaction.from_row(r) for r in rows]

    def get_recent_transactions(self, limit: int = 10) -> List[Transaction]:
        """Fetch latest transactions for the dashboard."""
        return self.get_all_transactions(limit=limit)

    def reverse_transaction(self, tx_id: int) -> Dict[str, Any]:
        """
        Safely reverse a transaction with accurate stock adjustment:
        - If SALE: restores sold stock back to inventory (+quantity).
        - If PURCHASE: safely checks if enough stock is available. If so, decreases stock (-quantity).
          If removing the purchase would cause negative inventory (because stock was already sold), rejects reversal.
        - If EXPENSE: removes the overhead expense.
        """
        tx = self.get_transaction_by_id(tx_id)
        if not tx:
            raise ValueError(f"Transaction #{tx_id} not found.")

        updated_stock = None
        reversal_details = ""

        if tx.type == "SALE":
            if tx.product_name and tx.quantity:
                # Restoring sold quantity to inventory
                prod = self.inventory_service.find_product_by_name(tx.product_name)
                if prod:
                    new_stock = prod.current_stock + tx.quantity
                    execute_db("UPDATE products SET current_stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                               (new_stock, prod.id), db_path=self.db_path)
                    updated_stock = new_stock
                    reversal_details = f"Restored {tx.quantity:g} {tx.unit or prod.unit} to '{prod.name}' stock (now {new_stock:g} {prod.unit})."

        elif tx.type == "PURCHASE":
            if tx.product_name and tx.quantity:
                prod = self.inventory_service.find_product_by_name(tx.product_name)
                if prod:
                    if prod.current_stock < tx.quantity:
                        raise ValueError(
                            f"Cannot reverse Purchase #{tx_id}: Product '{prod.name}' only has {prod.current_stock:g} {prod.unit} in stock, "
                            f"but {tx.quantity:g} {tx.unit} were purchased. Reversing would cause negative inventory."
                        )
                    new_stock = prod.current_stock - tx.quantity
                    execute_db("UPDATE products SET current_stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                               (new_stock, prod.id), db_path=self.db_path)
                    updated_stock = new_stock
                    reversal_details = f"Deducted {tx.quantity:g} {tx.unit or prod.unit} from '{prod.name}' stock (now {new_stock:g} {prod.unit})."

        elif tx.type == "EXPENSE":
            reversal_details = f"Cancelled expense of {Config.CURRENCY_SYMBOL}{tx.total_amount:g} for '{tx.category}'."

        # Delete transaction record
        execute_db("DELETE FROM transactions WHERE id = ?", (tx_id,), db_path=self.db_path)

        return {
            "success": True,
            "reversed_id": tx_id,
            "type": tx.type,
            "product_name": tx.product_name,
            "quantity": tx.quantity,
            "amount": tx.total_amount,
            "updated_stock": updated_stock,
            "message": f"Transaction #{tx_id} reversed successfully. {reversal_details}".strip()
        }

    def delete_transaction(self, tx_id: int) -> bool:
        """Alias for reverse_transaction."""
        res = self.reverse_transaction(tx_id)
        return res["success"]

    def export_transactions_csv(self, tx_type: Optional[str] = None, search: Optional[str] = None,
                                start_date: Optional[str] = None, end_date: Optional[str] = None) -> str:
        """
        Generate CSV export report matching the database records.
        """
        transactions = self.get_all_transactions(limit=10000, tx_type=tx_type, search=search,
                                                 start_date=start_date, end_date=end_date)
        output = io.StringIO()
        writer = csv.writer(output)

        # Write Header Row
        writer.writerow([
            "Transaction ID",
            "Type",
            "Product / Category",
            "Quantity",
            "Unit",
            "Unit Price (INR)",
            "Total Amount (INR)",
            "Party Name (Supplier / Customer)",
            "Profit (INR)",
            "Notes / Speech Input",
            "Date & Time"
        ])

        for t in transactions:
            writer.writerow([
                t.id,
                t.type,
                t.product_name or t.category or "",
                f"{t.quantity:g}" if t.quantity is not None else "",
                t.unit or "",
                f"{t.unit_price:.2f}" if t.unit_price is not None else "",
                f"{t.total_amount:.2f}",
                t.party_name or "",
                f"{t.profit:.2f}" if t.type == "SALE" else "0.00",
                t.notes or "",
                t.created_at or ""
            ])

        return output.getvalue()
