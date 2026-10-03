"""
Transaction Management API routes.
"""
from flask import Blueprint, request, jsonify
from services.transaction_service import TransactionService
from database.models import Transaction

transaction_bp = Blueprint('transaction', __name__, url_prefix='/api/transactions')

@transaction_bp.route('', methods=['GET'])
def list_transactions():
    """Retrieve filtered transaction ledger records."""
    limit = int(request.args.get('limit', 100))
    tx_type = request.args.get('type')
    search = request.args.get('search')

    service = TransactionService()
    transactions = service.get_all_transactions(limit=limit, tx_type=tx_type, search=search)
    return jsonify([t.to_dict() for t in transactions])

@transaction_bp.route('/manual', methods=['POST'])
def manual_transaction():
    """Fallback manual entry endpoint."""
    data = request.get_json(force=True, silent=True) or {}
    tx_type = data.get('type', '').upper()
    total_amount = float(data.get('total_amount', 0))
    notes = data.get('notes', 'Manual UI entry')

    service = TransactionService()
    try:
        if tx_type == 'PURCHASE':
            res = service.record_purchase(
                product_name=data.get('product_name'),
                quantity=float(data.get('quantity', 0)),
                unit=data.get('unit', 'pcs'),
                total_amount=total_amount,
                supplier_name=data.get('party_name'),
                notes=notes
            )
        elif tx_type == 'SALE':
            res = service.record_sale(
                product_name=data.get('product_name'),
                quantity=float(data.get('quantity', 0)),
                unit=data.get('unit', 'pcs'),
                total_amount=total_amount,
                customer_name=data.get('party_name'),
                notes=notes
            )
        elif tx_type == 'EXPENSE':
            res = service.record_expense(
                category=data.get('category', 'Miscellaneous'),
                total_amount=total_amount,
                notes=notes
            )
        else:
            return jsonify({"success": False, "message": "Invalid transaction type"}), 400

        return jsonify({"success": True, "transaction": res})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@transaction_bp.route('/<int:tx_id>', methods=['DELETE'])
def delete_transaction_endpoint(tx_id: int):
    """Delete a transaction record."""
    service = TransactionService()
    success = service.delete_transaction(tx_id)
    return jsonify({"success": success, "message": f"Transaction #{tx_id} deleted."})
