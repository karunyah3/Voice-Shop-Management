"""
Dashboard, Inventory, and View Rendering Routes.
"""
from flask import Blueprint, render_template, request, jsonify, current_app
from services.profit_service import ProfitService
from services.inventory_service import InventoryService
from services.transaction_service import TransactionService
from database.seed import seed_database
from config import Config

dashboard_bp = Blueprint('dashboard', __name__)

# ----------------- HTML PAGE ROUTES -----------------

@dashboard_bp.route('/')
def home():
    """Render Voice Assistant interactive console page."""
    return render_template('index.html', active_page='voice', currency=Config.CURRENCY_SYMBOL)

@dashboard_bp.route('/dashboard')
def dashboard_view():
    """Render Financial KPIs & Analytics Dashboard page."""
    return render_template('dashboard.html', active_page='dashboard', currency=Config.CURRENCY_SYMBOL)

@dashboard_bp.route('/inventory')
def inventory_view():
    """Render Product Catalog & Stock Management page."""
    return render_template('inventory.html', active_page='inventory', currency=Config.CURRENCY_SYMBOL)

@dashboard_bp.route('/transactions')
def transactions_view():
    """Render Full Transaction History Ledger page."""
    return render_template('transactions.html', active_page='transactions', currency=Config.CURRENCY_SYMBOL)

# ----------------- DATA API ROUTES -----------------

@dashboard_bp.route('/api/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    """Return live financial metrics, inventory totals, and chart series."""
    profit_service = ProfitService()
    inv_service = InventoryService()
    tx_service = TransactionService()

    summary = profit_service.get_financial_summary()
    charts = profit_service.get_chart_data()
    inv_summary = inv_service.get_stock_summary()
    recent_txs = [t.to_dict() for t in tx_service.get_recent_transactions(limit=6)]

    return jsonify({
        "financials": summary,
        "inventory": inv_summary,
        "charts": charts,
        "recent_transactions": recent_txs
    })

@dashboard_bp.route('/api/inventory', methods=['GET'])
def get_inventory_api():
    """Return all products and stock summaries."""
    inv_service = InventoryService()
    products = [p.to_dict() for p in inv_service.get_all_products()]
    summary = inv_service.get_stock_summary()
    return jsonify({
        "products": products,
        "summary": summary
    })

@dashboard_bp.route('/api/inventory/add', methods=['POST'])
def add_product_api():
    """Add a new product manually."""
    data = request.get_json(force=True, silent=True) or {}
    inv_service = InventoryService()
    try:
        prod = inv_service.add_product(
            name=data.get('name'),
            category=data.get('category', 'General'),
            unit=data.get('unit', 'pcs'),
            current_stock=float(data.get('current_stock', 0)),
            cost_price=float(data.get('cost_price', 0)),
            selling_price=float(data.get('selling_price', 0)),
            min_stock_alert=float(data.get('min_stock_alert', 5))
        )
        return jsonify({"success": True, "product": prod.to_dict()})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@dashboard_bp.route('/api/system/reset-demo', methods=['POST'])
def reset_demo_database():
    """Endpoint for viva/examiner presentation to reset sample state with 1 click."""
    db_path = current_app.config.get('DATABASE_PATH', Config.DATABASE_PATH)
    seed_database(db_path=db_path, force_reset=True)
    return jsonify({"success": True, "message": "Shop inventory & sample transactions re-seeded successfully."})
