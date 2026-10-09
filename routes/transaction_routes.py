"""
Transaction Management API routes.
Supports transaction retrieval with date/type/search filtering, single inspection,
safe reversals with stock synchronization, manual creation, and CSV report export.
"""
from datetime import datetime
from flask import Blueprint, request, jsonify, Response
from services.transaction_service import TransactionService
from database.models import Transaction

transaction_bp = Blueprint('transaction', __name__, url_prefix='/api/transactions')

@transaction_bp.route('', methods=['GET'])
def list_transactions():
    """Retrieve filtered transaction ledger records."""
    limit = int(request.args.get('limit', 100))
    tx_type = request.args.get('type')
    search = request.args.get('search')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    service = TransactionService()
    transactions = service.get_all_transactions(
        limit=limit,
        tx_type=tx_type,
        search=search,
        start_date=start_date,
        end_date=end_date
    )
    return jsonify([t.to_dict() for t in transactions])

@transaction_bp.route('/<int:tx_id>', methods=['GET'])
def get_transaction(tx_id: int):
    """Retrieve single transaction details by ID."""
    service = TransactionService()
    tx = service.get_transaction_by_id(tx_id)
    if not tx:
        return jsonify({"success": False, "message": f"Transaction #{tx_id} not found"}), 404
    return jsonify({"success": True, "transaction": tx.to_dict()})

@transaction_bp.route('/<int:tx_id>/reverse', methods=['POST'])
def reverse_transaction_endpoint(tx_id: int):
    """Safely reverse a transaction and restore stock."""
    service = TransactionService()
    try:
        res = service.reverse_transaction(tx_id)
        return jsonify(res)
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Server error reversing transaction: {str(e)}"}), 500

@transaction_bp.route('/<int:tx_id>', methods=['DELETE'])
def delete_transaction_endpoint(tx_id: int):
    """Delete and reverse a transaction record."""
    service = TransactionService()
    try:
        res = service.reverse_transaction(tx_id)
        return jsonify(res)
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500

@transaction_bp.route('/export-csv', methods=['GET'])
def export_transactions_csv():
    """Export transaction ledger records matching filters as downloadable CSV."""
    tx_type = request.args.get('type')
    search = request.args.get('search')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    service = TransactionService()
    csv_content = service.export_transactions_csv(
        tx_type=tx_type,
        search=search,
        start_date=start_date,
        end_date=end_date
    )

    filename = f"shop_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@transaction_bp.route('/manual', methods=['POST'])
def manual_transaction():
    """Manual entry endpoint."""
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
