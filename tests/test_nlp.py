"""
Automated Test Suite for NLP, Intent Detection, Entity Extraction,
Context Multi-Turn Conversations, and Corrections.
"""
import pytest
import os
import sqlite3
from config import TestConfig
from database.database import init_db
from database.seed import seed_database
from nlp.processor import NLPProcessor
from nlp.intent import detect_intent, IntentType
from nlp.entity_extractor import extract_all_entities, extract_correction_target
from nlp.confidence import calculate_confidence
from nlp.context_manager import ContextState

@pytest.fixture(autouse=True)
def setup_test_db():
    """Create clean isolated test database before each test."""
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

def test_purchase_extraction(setup_test_db):
    """Scenario 1: Full Purchase extraction test."""
    text = "Bought 20 kg rice from Kumar for 800 rupees"
    processor = NLPProcessor(session_id="test_purchase", db_path=setup_test_db)
    res = processor.process_input(text)

    assert res["success"] is True
    assert res["intent"] == IntentType.PURCHASE
    assert res["context"]["product"] == "Rice"
    assert res["context"]["quantity"] == 20.0
    assert res["context"]["unit"] == "kg"
    assert res["context"]["amount"] == 800.0
    assert res["context"]["party_name"] == "Kumar"
    assert res["requires_confirmation"] is True
    assert res["state"] == ContextState.AWAITING_CONFIRMATION
    assert "Please confirm" in res["message"]
    # Check explainable confidence
    assert 0.80 <= res["confidence"] < 1.0

def test_sale_extraction(setup_test_db):
    """Scenario 2: Full Sale extraction test."""
    text = "Sold 5 packets biscuits for 150 rupees"
    processor = NLPProcessor(session_id="test_sale", db_path=setup_test_db)
    res = processor.process_input(text)

    assert res["success"] is True
    assert res["intent"] == IntentType.SALE
    assert res["context"]["product"] == "Biscuits"
    assert res["context"]["quantity"] == 5.0
    assert res["context"]["unit"] == "packets"
    assert res["context"]["amount"] == 150.0
    assert res["requires_confirmation"] is True
    assert res["state"] == ContextState.AWAITING_CONFIRMATION
    assert "Please confirm: Sale of 5 packets Biscuits for ₹150" in res["message"]

def test_expense_extraction(setup_test_db):
    """Scenario 3: Expense extraction test."""
    text = "Paid 450 for electricity bill"
    processor = NLPProcessor(session_id="test_expense", db_path=setup_test_db)
    res = processor.process_input(text)

    assert res["success"] is True
    assert res["intent"] == IntentType.EXPENSE
    assert res["context"]["amount"] == 450.0
    assert "Electricity Bill" in res["context"]["category"]
    assert res["requires_confirmation"] is True
    assert res["state"] == ContextState.AWAITING_CONFIRMATION

def test_incomplete_purchase_slot_filling(setup_test_db):
    """Scenario 4: Incomplete purchase must NOT save immediately, but ask for missing slots."""
    session_id = "test_slot_filling"
    processor = NLPProcessor(session_id=session_id, db_path=setup_test_db)

    # Turn 1: User says only "Bought rice"
    turn1 = processor.process_input("Bought rice")
    assert turn1["success"] is True
    assert turn1["intent"] == IntentType.PURCHASE
    assert turn1["context"]["product"] == "Rice"
    assert turn1["requires_confirmation"] is False
    assert turn1["state"] == ContextState.AWAITING_QUANTITY
    assert "quantity" in turn1["message"].lower()

    # Turn 2: User provides quantity "20 kg"
    turn2 = processor.process_input("20 kg")
    assert turn2["success"] is True
    assert turn2["context"]["quantity"] == 20.0
    assert turn2["context"]["unit"] == "kg"
    assert turn2["requires_confirmation"] is False
    assert turn2["state"] == ContextState.AWAITING_AMOUNT
    assert "amount" in turn2["message"].lower()

    # Turn 3: User provides amount "800 rupees"
    turn3 = processor.process_input("800 rupees")
    assert turn3["success"] is True
    assert turn3["context"]["amount"] == 800.0
    assert turn3["requires_confirmation"] is True
    assert turn3["state"] == ContextState.AWAITING_CONFIRMATION
    assert "Please confirm" in turn3["message"]

    # Turn 4: User says "Confirm" -> saves to SQLite
    turn4 = processor.process_input("Confirm")
    assert turn4["success"] is True
    assert turn4["state"] == ContextState.IDLE
    assert "Success" in turn4["message"]
    assert turn4["transaction_data"]["product_name"] == "Rice"

def test_context_correction_quantity(setup_test_db):
    """Scenario 5: Context correction - user updates quantity without duplicating transaction."""
    session_id = "test_correction_qty"
    processor = NLPProcessor(session_id=session_id, db_path=setup_test_db)

    # Turn 1: Initial command
    processor.process_input("Bought 20 kg sugar for 700 rupees")
    
    # Turn 2: Correction command
    corr = processor.process_input("Actually change the quantity to 15 kg")
    assert corr["success"] is True
    assert corr["context"]["product"] == "Sugar"
    assert corr["context"]["quantity"] == 15.0
    assert corr["context"]["amount"] == 700.0
    assert corr["state"] == ContextState.AWAITING_CONFIRMATION
    assert "Updated quantity to 15 kg" in corr["message"]
    assert "15 kg Sugar for ₹700" in corr["message"]

def test_context_correction_amount(setup_test_db):
    """Scenario 6: Context correction - user updates amount/price."""
    session_id = "test_correction_amt"
    processor = NLPProcessor(session_id=session_id, db_path=setup_test_db)

    processor.process_input("Bought 10 packets tea powder for 700 rupees")
    corr = processor.process_input("Change amount to 650 rupees")
    
    assert corr["success"] is True
    assert corr["context"]["amount"] == 650.0
    assert corr["context"]["quantity"] == 10.0
    assert corr["context"]["product"] == "Tea Powder"
    assert "Updated total amount to ₹650" in corr["message"]

def test_query_handling(setup_test_db):
    """Scenario 11: Stock query, Sales query, Profit query."""
    processor = NLPProcessor(session_id="test_queries", db_path=setup_test_db)

    # 1. Inventory Query
    inv_res = processor.process_input("What is the stock of rice?")
    assert inv_res["success"] is True
    assert inv_res["intent"] == IntentType.INVENTORY_QUERY
    assert "Rice" in inv_res["message"]
    assert "50" in inv_res["message"]

    # 2. Sales Query
    sales_res = processor.process_input("What are the total sales?")
    assert sales_res["success"] is True
    assert sales_res["intent"] == IntentType.SALES_QUERY
    assert "Sales Summary" in sales_res["message"]

    # 3. Profit Query
    profit_res = processor.process_input("What is the total profit?")
    assert profit_res["success"] is True
    assert profit_res["intent"] == IntentType.PROFIT_QUERY
    assert "Financial Status" in profit_res["message"]

def test_cancellation_flow(setup_test_db):
    """Scenario: User cancels a pending transaction."""
    processor = NLPProcessor(session_id="test_cancel", db_path=setup_test_db)
    
    # Start pending transaction
    processor.process_input("Bought 20 kg rice for 800 rupees")
    ctx_before = processor.context_mgr.get_context()
    assert ctx_before.state == ContextState.AWAITING_CONFIRMATION

    # Cancel command
    cancel_res = processor.process_input("Cancel")
    assert cancel_res["success"] is True
    assert "discarded" in cancel_res["message"]
    
    ctx_after = processor.context_mgr.get_context()
    assert ctx_after.state == ContextState.IDLE

def test_spoken_word_numbers_extraction(setup_test_db):
    """Scenario: Natural speech numbers like 'twenty kg' or 'five hundred rupees'."""
    processor = NLPProcessor(session_id="test_words", db_path=setup_test_db)
    res = processor.process_input("Bought twenty kg sugar for seven hundred rupees")
    assert res["success"] is True
    assert res["context"]["quantity"] == 20.0
    assert res["context"]["amount"] == 700.0
