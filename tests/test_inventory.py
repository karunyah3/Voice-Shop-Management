"""
Automated Test Suite for Inventory Management, Stock Updates,
and Negative Stock Prevention.
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
