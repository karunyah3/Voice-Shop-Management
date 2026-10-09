"""
Automated Test Suite for Profit and Financial Calculations,
Multi-Period Summaries (Today, Month, All-Time), and Financial Reporting.
"""
import pytest
import os
from config import TestConfig
from database.database import init_db
from database.seed import seed_database
from services.inventory_service import InventoryService
from services.transaction_service import TransactionService
from services.profit_service import ProfitService

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

def test_sale_item_profit_calculation(setup_test_db):
    """
    Scenario 10A: Individual item sale profit calculation.
    Formula: Profit = (Selling Price per Unit - Cost Price per Unit) * Quantity
    """
    inv_service = InventoryService(db_path=setup_test_db)
    tx_service = TransactionService(db_path=setup_test_db)

    # Product Biscuits has cost_price = 20.0
    prod = inv_service.find_product_by_name("Biscuits")
    assert prod.cost_price == 20.0

    # Sell 5 packets for 150 rupees -> Unit selling price = 30.0
    # Expected profit = (30.0 - 20.0) * 5 = 50.0 rupees
    res = tx_service.record_sale(
        product_name="Biscuits",
        quantity=5.0,
        unit="packets",
        total_amount=150.0,
        customer_name="Anita"
    )

    assert res["unit_price"] == 30.0
    assert res["cost_price"] == 20.0
    assert res["profit"] == 50.0

def test_overall_financial_summary_profit(setup_test_db):
    """
    Scenario 10B: Overall Financial Summary.
    Net Profit = Total Sales Revenue - Total Purchase Cost - Total Expenses
    """
    profit_service = ProfitService(db_path=setup_test_db)
    summary = profit_service.get_financial_summary()

    # Verify fields exist
    assert "total_sales" in summary
    assert "total_purchases" in summary
    assert "total_expenses" in summary
    assert "net_profit" in summary
    assert "operating_profit" in summary
    assert "total_item_profit" in summary

    # Verify calculation consistency
    expected_net = round(summary["total_sales"] - summary["total_purchases"] - summary["total_expenses"], 2)
    assert summary["net_profit"] == expected_net

def test_multi_period_summary(setup_test_db):
    """Test comprehensive Today, Month, and All-Time financial breakdown."""
    profit_service = ProfitService(db_path=setup_test_db)
    tx_service = TransactionService(db_path=setup_test_db)

    # Record today's sale
    tx_service.record_sale("Rice", 2.0, "kg", 100.0, "Walk-in")

    comp = profit_service.get_comprehensive_summary()
    assert "today" in comp
    assert "month" in comp
    assert "all_time" in comp

    assert comp["today"]["total_sales"] >= 100.0
    assert comp["month"]["total_sales"] >= comp["today"]["total_sales"]
    assert comp["all_time"]["total_sales"] >= comp["month"]["total_sales"]
