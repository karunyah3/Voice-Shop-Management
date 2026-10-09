"""
Automated Test Suite for Inventory Management, Stock Updates,
Negative Stock Prevention, Safe Transaction Reversals, and CSV Export.
"""
import pytest
import os
from config import TestConfig
from database.database import init_db
from database.seed import seed_database
from services.inventory_service import InventoryService
from services.transaction_service import TransactionService
from nlp.processor import NLPProcessor

@pytest.fixture(autouse=True)
def setup_test_db():
    test_db = TestConfig.DATABASE_PATH
    if os.path.exists(test_db):
        os.remove(test_db)
    init_db(test_db)
    seed_database(test_db, force_reset=True)
    yield test_db
    if os.path.exists(test_db):
        try:
            os.remove(test_db)
        except Exception:
            pass

def test_inventory_increase_after_purchase(setup_test_db):
    """Scenario 7: Stock increases correctly after a purchase transaction."""
    inv_service = InventoryService(db_path=setup_test_db)
    tx_service = TransactionService(db_path=setup_test_db)

    # Initial stock of Rice is 50.0 kg from seed
    prod_before = inv_service.find_product_by_name("Rice")
    initial_stock = prod_before.current_stock
    assert initial_stock == 50.0

    # Record purchase of 20 kg
    res = tx_service.record_purchase(
        product_name="Rice",
        quantity=20.0,
        unit="kg",
        total_amount=800.0,
        supplier_name="Kumar"
    )

    prod_after = inv_service.find_product_by_name("Rice")
    assert prod_after.current_stock == initial_stock + 20.0
    assert res["new_stock"] == 70.0

def test_inventory_decrease_after_sale(setup_test_db):
    """Scenario 8: Stock decreases correctly after a valid sale transaction."""
    inv_service = InventoryService(db_path=setup_test_db)
    tx_service = TransactionService(db_path=setup_test_db)

    # Initial stock of Biscuits is 30.0 packets from seed
    prod_before = inv_service.find_product_by_name("Biscuits")
    initial_stock = prod_before.current_stock
    assert initial_stock == 30.0

    # Record sale of 5 packets
    res = tx_service.record_sale(
        product_name="Biscuits",
        quantity=5.0,
        unit="packets",
        total_amount=150.0,
        customer_name="Ramesh"
    )

    prod_after = inv_service.find_product_by_name("Biscuits")
    assert prod_after.current_stock == initial_stock - 5.0
    assert res["new_stock"] == 25.0

def test_negative_stock_prevention(setup_test_db):
    """Scenario 9: System strictly prevents negative inventory and rejects sale exceeding stock."""
    inv_service = InventoryService(db_path=setup_test_db)
    tx_service = TransactionService(db_path=setup_test_db)
    processor = NLPProcessor(session_id="test_neg_stock", db_path=setup_test_db)

    # 1. Test direct Service Level Validation
    prod = inv_service.find_product_by_name("Biscuits")
    current_stock = prod.current_stock # 30

    with pytest.raises(ValueError) as exc_info:
        # Attempt to sell 100 packets when only 30 exist
        tx_service.record_sale(
            product_name="Biscuits",
            quantity=100.0,
            unit="packets",
            total_amount=3000.0
        )
    assert "Insufficient stock" in str(exc_info.value)
    
    # Verify stock remained unchanged
    prod_check = inv_service.find_product_by_name("Biscuits")
    assert prod_check.current_stock == current_stock

    # 2. Test NLP Processor Rejection on Voice Input
    voice_res = processor.process_input("Sold 100 packets biscuits for 3000 rupees")
    assert voice_res["success"] is False
    assert "Insufficient stock" in voice_res["message"]
    assert voice_res["is_insufficient_stock"] is True
    assert voice_res["available_stock"] == current_stock
    assert voice_res["requires_confirmation"] is False

def test_safe_transaction_reversals(setup_test_db):
    """Test that deleting/reversing transactions restores and syncs stock safely."""
    inv_service = InventoryService(db_path=setup_test_db)
    tx_service = TransactionService(db_path=setup_test_db)

    # 1. Sale Reversal: Selling 5 kg Rice decreases stock to 45. Reversing restores it to 50.
    rice_init = inv_service.find_product_by_name("Rice").current_stock # 50
    sale_tx = tx_service.record_sale("Rice", 5.0, "kg", 250.0, "Customer A")
    assert inv_service.find_product_by_name("Rice").current_stock == rice_init - 5.0

    rev_res = tx_service.reverse_transaction(sale_tx["transaction_id"])
    assert rev_res["success"] is True
    assert inv_service.find_product_by_name("Rice").current_stock == rice_init

    # 2. Purchase Reversal: Purchasing 10 kg Sugar increases stock to 50. Reversing deducts it back to 40.
    sugar_init = inv_service.find_product_by_name("Sugar").current_stock # 40
    purch_tx = tx_service.record_purchase("Sugar", 10.0, "kg", 350.0, "Supplier B")
    assert inv_service.find_product_by_name("Sugar").current_stock == sugar_init + 10.0

    rev_purch = tx_service.reverse_transaction(purch_tx["transaction_id"])
    assert rev_purch["success"] is True
    assert inv_service.find_product_by_name("Sugar").current_stock == sugar_init

def test_csv_export(setup_test_db):
    """Test CSV report generation matching database transactions."""
    tx_service = TransactionService(db_path=setup_test_db)
    csv_str = tx_service.export_transactions_csv()

    assert "Transaction ID,Type,Product / Category,Quantity" in csv_str
    assert "PURCHASE" in csv_str
    assert "SALE" in csv_str
