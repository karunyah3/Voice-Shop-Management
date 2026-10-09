"""
Comprehensive Automated Test Suite for Natural Language Processing, Intent Classification, Entity Extraction,
Multi-Turn Dialogue, Corrections, Stock Rejection, and Edge Cases.
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

def test_natural_purchase_variations(setup_test_db):
    """Test multiple natural phrasing variations for Purchase transactions."""
    processor = NLPProcessor(session_id="test_nlp_nat1", db_path=setup_test_db)

    # 1. "Bought 500 grams of sugar from Arun for 250."
    res1 = processor.process_input("Bought 500 grams of sugar from Arun for 250.")
    assert res1["success"] is True
    assert res1["intent"] == IntentType.PURCHASE
    assert res1["context"]["product"] == "Sugar"
    assert res1["context"]["quantity"] == 500.0
    assert res1["context"]["unit"] == "g"
    assert res1["context"]["amount"] == 250.0
    assert res1["context"]["party_name"] == "Arun"
    assert res1["requires_confirmation"] is True
    processor.context_mgr.reset_context()

    # 2. "Arun gave me 500 grams of sugar for 250 rupees."
    res2 = processor.process_input("Arun gave me 500 grams of sugar for 250 rupees.")
    assert res2["success"] is True
    assert res2["intent"] == IntentType.PURCHASE
    assert res2["context"]["product"] == "Sugar"
    assert res2["context"]["quantity"] == 500.0
    assert res2["context"]["unit"] == "g"
    assert res2["context"]["amount"] == 250.0
    assert res2["context"]["party_name"] == "Arun"
    processor.context_mgr.reset_context()

    # 3. "I got sugar from Arun, 500 grams, paid 250."
    res3 = processor.process_input("I got sugar from Arun, 500 grams, paid 250.")
    assert res3["success"] is True
    assert res3["intent"] == IntentType.PURCHASE
    assert res3["context"]["product"] == "Sugar"
    assert res3["context"]["quantity"] == 500.0
    assert res3["context"]["amount"] == 250.0
    assert res3["context"]["party_name"] == "Arun"
    processor.context_mgr.reset_context()

    # 4. "Today Arun supplied 500 grams of sugar and I paid him 250."
    res4 = processor.process_input("Today Arun supplied 500 grams of sugar and I paid him 250.")
    assert res4["success"] is True
    assert res4["intent"] == IntentType.PURCHASE
    assert res4["context"]["product"] == "Sugar"
    assert res4["context"]["quantity"] == 500.0
    assert res4["context"]["amount"] == 250.0
    assert res4["context"]["party_name"] == "Arun"
    processor.context_mgr.reset_context()

    # 5. "I purchased sugar from Arun for 250 rupees."
    res5 = processor.process_input("I purchased sugar from Arun for 250 rupees.")
    assert res5["success"] is True
    assert res5["intent"] == IntentType.PURCHASE
    assert res5["context"]["product"] == "Sugar"
    assert res5["context"]["amount"] == 250.0
    assert res5["context"]["party_name"] == "Arun"
    processor.context_mgr.reset_context()

    # 6. "500 grams of sugar came from Arun, cost me 250."
    res6 = processor.process_input("500 grams of sugar came from Arun, cost me 250.")
    assert res6["success"] is True
    assert res6["intent"] == IntentType.PURCHASE
    assert res6["context"]["product"] == "Sugar"
    assert res6["context"]["quantity"] == 500.0
    assert res6["context"]["amount"] == 250.0
    assert res6["context"]["party_name"] == "Arun"
    processor.context_mgr.reset_context()

def test_more_user_examples(setup_test_db):
    """Test all specific examples provided by the user."""
    processor = NLPProcessor(session_id="test_nlp_user_ex", db_path=setup_test_db)

    # 1. "Arun supplied me 500 kilos of rice for 20,000."
    res1 = processor.process_input("Arun supplied me 500 kilos of rice for 20,000.")
    assert res1["success"] is True
    assert res1["intent"] == IntentType.PURCHASE
    assert res1["context"]["product"] == "Rice"
    assert res1["context"]["quantity"] == 500.0
    assert res1["context"]["unit"] == "kg"
    assert res1["context"]["amount"] == 20000.0
    assert res1["context"]["party_name"] == "Arun"
    processor.context_mgr.reset_context()

    # 2. "Bought 5 kg rice from Arun for 300 rupees."
    res2 = processor.process_input("Bought 5 kg rice from Arun for 300 rupees.")
    assert res2["success"] is True
    assert res2["intent"] == IntentType.PURCHASE
    assert res2["context"]["product"] == "Rice"
    assert res2["context"]["quantity"] == 5.0
    assert res2["context"]["unit"] == "kg"
    assert res2["context"]["amount"] == 300.0
    assert res2["context"]["party_name"] == "Arun"
    processor.context_mgr.reset_context()

    # 3. "Arun supplied me 5 kg rice, paid 300."
    res3 = processor.process_input("Arun supplied me 5 kg rice, paid 300.")
    assert res3["success"] is True
    assert res3["intent"] == IntentType.PURCHASE
    assert res3["context"]["product"] == "Rice"
    assert res3["context"]["quantity"] == 5.0
    assert res3["context"]["amount"] == 300.0
    assert res3["context"]["party_name"] == "Arun"
    processor.context_mgr.reset_context()

    # 4. "Got rice from Arun, five kilos, three hundred."
    res4 = processor.process_input("Got rice from Arun, five kilos, three hundred.")
    assert res4["success"] is True
    assert res4["intent"] == IntentType.PURCHASE
    assert res4["context"]["product"] == "Rice"
    assert res4["context"]["quantity"] == 5.0
    assert res4["context"]["amount"] == 300.0
    assert res4["context"]["party_name"] == "Arun"
    processor.context_mgr.reset_context()

    # 5. "I purchased sugar for 500 from Arun."
    res5 = processor.process_input("I purchased sugar for 500 from Arun.")
    assert res5["success"] is True
    assert res5["intent"] == IntentType.PURCHASE
    assert res5["context"]["product"] == "Sugar"
    assert res5["context"]["amount"] == 500.0
    assert res5["context"]["party_name"] == "Arun"
    processor.context_mgr.reset_context()

    # 6. "Arun sold me 2 kg sugar for 200."
    res6 = processor.process_input("Arun sold me 2 kg sugar for 200.")
    assert res6["success"] is True
    assert res6["intent"] == IntentType.PURCHASE
    assert res6["context"]["product"] == "Sugar"
    assert res6["context"]["quantity"] == 2.0
    assert res6["context"]["amount"] == 200.0
    assert res6["context"]["party_name"] == "Arun"
    processor.context_mgr.reset_context()

def test_customer_sale_versus_purchase(setup_test_db):
    """Test distinction: 'Arun bought ...' (Sale) vs 'I bought from Arun' (Purchase)."""
    processor = NLPProcessor(session_id="test_distinction", db_path=setup_test_db)

    # Arun bought sugar -> Sale to Arun
    res_sale = processor.process_input("Arun bought 500 rupees worth of sugar.")
    assert res_sale["success"] is True
    assert res_sale["intent"] == IntentType.SALE
    assert res_sale["context"]["product"] == "Sugar"
    assert res_sale["context"]["amount"] == 500.0
    assert res_sale["context"]["party_name"] == "Arun"
    processor.context_mgr.reset_context()

    # I bought sugar from Arun -> Purchase from Arun
    res_purch = processor.process_input("I bought sugar from Arun for 500.")
    assert res_purch["success"] is True
    assert res_purch["intent"] == IntentType.PURCHASE
    assert res_purch["context"]["product"] == "Sugar"
    assert res_purch["context"]["amount"] == 500.0
    assert res_purch["context"]["party_name"] == "Arun"
    processor.context_mgr.reset_context()

    # Sugar from Arun, 500 rupees -> Purchase from Arun
    res_inward = processor.process_input("Sugar from Arun, 500 rupees.")
    assert res_inward["success"] is True
    assert res_inward["intent"] == IntentType.PURCHASE
    assert res_inward["context"]["product"] == "Sugar"
    assert res_inward["context"]["amount"] == 500.0
    assert res_inward["context"]["party_name"] == "Arun"
    processor.context_mgr.reset_context()

def test_missing_information_clarification(setup_test_db):
    """Test that missing info prompts a concise question without formulaic format instructions."""
    processor = NLPProcessor(session_id="test_clarify", db_path=setup_test_db)

    # 1. "Today I got 10 kg rice from Arun." (Price missing)
    turn1 = processor.process_input("Today I got 10 kg rice from Arun.")
    assert turn1["success"] is True
    assert turn1["state"] == ContextState.AWAITING_AMOUNT
    assert turn1["requires_confirmation"] is False
    assert "purchase price" in turn1["message"].lower() or "amount" in turn1["message"].lower()
    assert "please say" not in turn1["message"].lower()

    # 2. Answer price "300 rupees"
    turn2 = processor.process_input("300 rupees")
    assert turn2["success"] is True
    assert turn2["state"] == ContextState.AWAITING_CONFIRMATION
    assert turn2["requires_confirmation"] is True
    assert turn2["context"]["amount"] == 300.0
    assert turn2["context"]["quantity"] == 10.0
    assert turn2["context"]["product"] == "Rice"
    assert turn2["context"]["party_name"] == "Arun"

    # 3. Confirm
    turn3 = processor.process_input("confirm")
    assert turn3["success"] is True
    assert turn3["state"] == ContextState.IDLE
    assert turn3["transaction_data"]["product_name"] == "Rice"

def test_missing_price_slot_and_commit(setup_test_db):
    """Test 'Got 500 grams sugar from Arun.' -> prompts for price -> user enters 250 -> saves."""
    processor = NLPProcessor(session_id="test_slot_sugar", db_path=setup_test_db)

    # Turn 1: "Got 500 grams sugar from Arun."
    turn1 = processor.process_input("Got 500 grams sugar from Arun.")
    assert turn1["success"] is True
    assert turn1["state"] == ContextState.AWAITING_AMOUNT
    assert turn1["requires_confirmation"] is False

    # Turn 2: User responds "250"
    turn2 = processor.process_input("250")
    assert turn2["success"] is True
    assert turn2["state"] == ContextState.AWAITING_CONFIRMATION
    assert turn2["requires_confirmation"] is True
    assert turn2["context"]["amount"] == 250.0
    assert turn2["context"]["quantity"] == 500.0
    assert turn2["context"]["product"] == "Sugar"
    assert turn2["context"]["party_name"] == "Arun"

    # Turn 3: User says "Save it"
    turn3 = processor.process_input("Save it")
    assert turn3["success"] is True
    assert turn3["state"] == ContextState.IDLE
    assert turn3["transaction_data"]["product_name"] == "Sugar"

def test_context_corrections(setup_test_db):
    """Test real-time corrections to quantity, price, and supplier."""
    processor = NLPProcessor(session_id="test_corrections", db_path=setup_test_db)

    # Turn 1: Initial statement
    processor.process_input("Bought 20 kg sugar from Arun for 700 rupees")

    # Turn 2: Correction to quantity
    c1 = processor.process_input("Actually change the quantity to 15 kg")
    assert c1["success"] is True
    assert c1["context"]["quantity"] == 15.0
    assert c1["context"]["product"] == "Sugar"
    assert c1["context"]["amount"] == 700.0

    # Turn 3: Correction to amount
    c2 = processor.process_input("Change amount to 650 rupees")
    assert c2["success"] is True
    assert c2["context"]["amount"] == 650.0
    assert c2["context"]["quantity"] == 15.0

    # Turn 4: Correction to supplier
    c3 = processor.process_input("Change supplier to Ramesh")
    assert c3["success"] is True
    assert c3["context"]["party_name"] == "Ramesh"

    # Turn 5: Confirm
    c4 = processor.process_input("yes")
    assert c4["success"] is True
    assert c4["transaction_data"]["supplier"] == "Ramesh"
    assert c4["transaction_data"]["total_amount"] == 650.0

def test_insufficient_stock_rejection(setup_test_db):
    """Test that selling more than available stock is rejected cleanly."""
    processor = NLPProcessor(session_id="test_neg_stock", db_path=setup_test_db)
    res = processor.process_input("Sold 5000 packets biscuits for 50000 rupees")
    assert res["success"] is False
    assert "insufficient stock" in res["message"].lower()
    assert res["requires_confirmation"] is False

def test_expense_and_queries(setup_test_db):
    """Test expense recording and analytic queries."""
    processor = NLPProcessor(session_id="test_exp_queries", db_path=setup_test_db)

    # Expense
    exp = processor.process_input("Paid 450 for electricity bill")
    assert exp["success"] is True
    assert exp["intent"] == IntentType.EXPENSE
    assert exp["context"]["amount"] == 450.0
    processor.context_mgr.reset_context()

    # Stock Query
    inv = processor.process_input("What is the stock of rice?")
    assert inv["success"] is True
    assert inv["intent"] == IntentType.INVENTORY_QUERY
    assert "Rice" in inv["message"]

    # Sales Query
    sales = processor.process_input("What are the total sales?")
    assert sales["success"] is True
    assert sales["intent"] == IntentType.SALES_QUERY

    # Profit Query
    profit = processor.process_input("What is our profit?")
    assert profit["success"] is True
    assert profit["intent"] == IntentType.PROFIT_QUERY

def test_in_utterance_self_corrections(setup_test_db):
    """Test handling of self-corrections made within the exact same utterance."""
    processor = NLPProcessor(session_id="test_in_utterance", db_path=setup_test_db)

    # 1. "Sell 5 kg rice wait no 10 kg rice for 400."
    res1 = processor.process_input("Sell 5 kg rice wait no 10 kg rice for 400.")
    assert res1["success"] is True
    assert res1["intent"] == IntentType.SALE
    assert res1["context"]["product"] == "Rice"
    assert res1["context"]["quantity"] == 10.0
    assert res1["context"]["amount"] == 400.0
    processor.context_mgr.reset_context()

    # 2. "Bought 5 kg sugar actually 10 kg sugar for 400."
    res2 = processor.process_input("Bought 5 kg sugar actually 10 kg sugar for 400.")
    assert res2["success"] is True
    assert res2["intent"] == IntentType.PURCHASE
    assert res2["context"]["product"] == "Sugar"
    assert res2["context"]["quantity"] == 10.0
    assert res2["context"]["amount"] == 400.0
    processor.context_mgr.reset_context()

    # 3. "Sold 2 packets biscuits sorry 3 packets for 90."
    res3 = processor.process_input("Sold 2 packets biscuits sorry 3 packets for 90.")
    assert res3["success"] is True
    assert res3["intent"] == IntentType.SALE
    assert res3["context"]["product"] == "Biscuits"
    assert res3["context"]["quantity"] == 3.0
    assert res3["context"]["amount"] == 90.0
    processor.context_mgr.reset_context()

    # 4. "Arun supplied 5 kg rice no make that 10 kg for 400."
    res4 = processor.process_input("Arun supplied 5 kg rice no make that 10 kg for 400.")
    assert res4["success"] is True
    assert res4["intent"] == IntentType.PURCHASE
    assert res4["context"]["product"] == "Rice"
    assert res4["context"]["quantity"] == 10.0
    assert res4["context"]["amount"] == 400.0
    assert res4["context"]["party_name"] == "Arun"
    processor.context_mgr.reset_context()

def test_unit_rate_and_composite_spoken_numbers(setup_test_db):
    """Test unit rate auto-multiplication and composite spoken word numbers."""
    processor = NLPProcessor(session_id="test_rate_numbers", db_path=setup_test_db)

    # 1. Unit rate: "Sell 5 kg rice at 40 per kg to Rahul" -> Total = 5 * 40 = 200
    res1 = processor.process_input("Sell 5 kg rice at 40 per kg to Rahul")
    assert res1["success"] is True
    assert res1["intent"] == IntentType.SALE
    assert res1["context"]["product"] == "Rice"
    assert res1["context"]["quantity"] == 5.0
    assert res1["context"]["amount"] == 200.0
    assert res1["context"]["party_name"] == "Rahul"
    processor.context_mgr.reset_context()

    # 2. Fractions & spoken words: "Bought two and a half liters oil for three hundred"
    res2 = processor.process_input("Bought two and a half liters oil for three hundred")
    assert res2["success"] is True
    assert res2["intent"] == IntentType.PURCHASE
    assert res2["context"]["product"] == "Sunflower Oil"
    assert res2["context"]["quantity"] == 2.5
    assert res2["context"]["unit"] == "liters"
    assert res2["context"]["amount"] == 300.0
    processor.context_mgr.reset_context()

    # 3. Compound words: "Sold twenty five packets of biscuits for seven hundred and fifty rupees"
    res3 = processor.process_input("Sold twenty five packets of biscuits for seven hundred and fifty rupees")
    assert res3["success"] is True
    assert res3["intent"] == IntentType.SALE
    assert res3["context"]["product"] == "Biscuits"
    assert res3["context"]["quantity"] == 25.0
    assert res3["context"]["amount"] == 750.0
    processor.context_mgr.reset_context()

def test_word_orders_and_prepositions(setup_test_db):
    """Test various sentence structures and preposition placements."""
    processor = NLPProcessor(session_id="test_word_orders", db_path=setup_test_db)

    # 1. Destination-first: "To Sita sold 2 packets biscuits for 60"
    res1 = processor.process_input("To Sita sold 2 packets biscuits for 60")
    assert res1["success"] is True
    assert res1["intent"] == IntentType.SALE
    assert res1["context"]["party_name"] == "Sita"
    assert res1["context"]["product"] == "Biscuits"
    assert res1["context"]["quantity"] == 2.0
    assert res1["context"]["amount"] == 60.0
    processor.context_mgr.reset_context()

    # 2. Source-first: "From Arun bought 10 kg sugar for 400"
    res2 = processor.process_input("From Arun bought 10 kg sugar for 400")
    assert res2["success"] is True
    assert res2["intent"] == IntentType.PURCHASE
    assert res2["context"]["party_name"] == "Arun"
    assert res2["context"]["product"] == "Sugar"
    assert res2["context"]["quantity"] == 10.0
    assert res2["context"]["amount"] == 400.0
    processor.context_mgr.reset_context()

    # 3. Price-first: "For 300 rupees sold 5 kg rice to Rahul"
    res3 = processor.process_input("For 300 rupees sold 5 kg rice to Rahul")
    assert res3["success"] is True
    assert res3["intent"] == IntentType.SALE
    assert res3["context"]["product"] == "Rice"
    assert res3["context"]["quantity"] == 5.0
    assert res3["context"]["amount"] == 300.0
    assert res3["context"]["party_name"] == "Rahul"
    processor.context_mgr.reset_context()

    # 4. Product-first: "Sugar 5 kg sold to Ramesh for 225"
    res4 = processor.process_input("Sugar 5 kg sold to Ramesh for 225")
    assert res4["success"] is True
    assert res4["intent"] == IntentType.SALE
    assert res4["context"]["product"] == "Sugar"
    assert res4["context"]["quantity"] == 5.0
    assert res4["context"]["amount"] == 225.0
    assert res4["context"]["party_name"] == "Ramesh"
    processor.context_mgr.reset_context()

