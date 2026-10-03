"""
Central NLP Processor Orchestrator.
Coordinates Intent Detection, Entity Extraction, Context State Transitions,
Confidence Scoring, Inventory Validation, and Natural Language Response Generation.
"""
from typing import Dict, Any, List, Optional
import json
from config import Config
from .intent import detect_intent, IntentType
from .entity_extractor import (
    extract_all_entities,
    extract_correction_target,
    extract_quantity_and_unit,
    extract_amount,
    extract_product_name
)
from .confidence import calculate_confidence
from .context_manager import ContextManager, ContextState
from database.models import PendingContext

class NLPProcessor:
    def __init__(self, session_id: str = "default_session", db_path: str = None):
        self.session_id = session_id
        self.db_path = db_path
        self.context_mgr = ContextManager(session_id=session_id, db_path=db_path)

    def _get_known_product_names(self) -> List[str]:
        """Fetch list of active products from database to aid entity matching."""
        from services.inventory_service import InventoryService
        inv_service = InventoryService(db_path=self.db_path)
        products = inv_service.get_all_products()
        return [p.name for p in products]

    def _get_product_by_name(self, name: str):
        from services.inventory_service import InventoryService
        inv_service = InventoryService(db_path=self.db_path)
        return inv_service.find_product_by_name(name)

    def process_input(self, raw_text: str) -> Dict[str, Any]:
        """
        Main entry point for processing natural language voice / text commands.
        """
        text = raw_text.strip()
        if not text:
            return {
                "success": False,
                "message": "Please speak or type a transaction command.",
                "state": ContextState.IDLE,
                "confidence": 0.0,
                "confidence_status": "LOW",
                "confidence_factors": ["No audio or text input received"],
                "context": None,
                "requires_confirmation": False
            }

        ctx = self.context_mgr.get_context()
        known_products = self._get_known_product_names()
        
        # 1. Detect Intent
        intent, intent_score, match_rule = detect_intent(text, current_state=ctx.state)

        # 2. Process Intent based on dialogue state
        # ----------------------------------------------------
        # CASE A: CONFIRMATION ("yes", "confirm", "proceed", "save it")
        # ----------------------------------------------------
        if intent == IntentType.CONFIRMATION:
            if ctx.state == ContextState.AWAITING_CONFIRMATION and ctx.intent:
                return self._execute_confirmed_transaction(ctx)
            elif ctx.state in (ContextState.AWAITING_QUANTITY, ContextState.AWAITING_AMOUNT, ContextState.AWAITING_PRODUCT):
                # Prompt for the missing info instead of confirming prematurely
                missing_str = ", ".join(ctx.missing_slots or [])
                return {
                    "success": False,
                    "message": f"Cannot confirm yet. Missing required details: {missing_str}. {ctx.last_prompt}",
                    "state": ctx.state,
                    "confidence": ctx.confidence,
                    "confidence_status": "MEDIUM",
                    "confidence_factors": ctx.confidence_breakdown or [],
                    "context": ctx.to_dict(),
                    "requires_confirmation": False
                }
            else:
                return {
                    "success": False,
                    "message": "There is no pending transaction to confirm. Try saying: 'Bought 20 kg rice for 800 rupees'.",
                    "state": ContextState.IDLE,
                    "confidence": 0.90,
                    "confidence_status": "HIGH",
                    "confidence_factors": ["Confirmation received but no pending transaction in context"],
                    "context": None,
                    "requires_confirmation": False
                }

        # ----------------------------------------------------
        # CASE B: CANCELLATION ("cancel", "no", "discard", "abort")
        # ----------------------------------------------------
        if intent == IntentType.CANCELLATION:
            if ctx.state != ContextState.IDLE:
                self.context_mgr.reset_context()
                return {
                    "success": True,
                    "message": "Pending transaction was discarded.",
                    "state": ContextState.IDLE,
                    "confidence": 0.95,
                    "confidence_status": "HIGH",
                    "confidence_factors": ["Cancellation command received, context cleared"],
                    "context": None,
                    "requires_confirmation": False
                }
            else:
                return {
                    "success": True,
                    "message": "No active transaction to cancel.",
                    "state": ContextState.IDLE,
                    "confidence": 0.95,
                    "confidence_status": "HIGH",
                    "confidence_factors": ["System already in idle state"],
                    "context": None,
                    "requires_confirmation": False
                }

        # ----------------------------------------------------
        # CASE C: CORRECTION ("Actually change quantity to 15 kg", "Change amount to 700")
        # ----------------------------------------------------
        if intent == IntentType.CORRECTION or (ctx.state != ContextState.IDLE and any(w in text.lower() for w in ["change", "actually", "make it", "instead"])):
            if ctx.intent in (IntentType.PURCHASE, IntentType.SALE, IntentType.EXPENSE):
                correction = extract_correction_target(text)
                ctx, update_msg = self.context_mgr.apply_correction(correction)
                return self._evaluate_and_respond(ctx, text, prefix_message=update_msg)
            else:
                return {
                    "success": False,
                    "message": "No pending transaction to modify. Please initiate a new transaction.",
                    "state": ContextState.IDLE,
                    "confidence": 0.80,
                    "confidence_status": "MEDIUM",
                    "confidence_factors": ["Correction intent received without active transaction context"],
                    "context": None,
                    "requires_confirmation": False
                }

        # ----------------------------------------------------
        # CASE D: ANALYTICS QUERIES (INVENTORY, SALES, PROFIT)
        # ----------------------------------------------------
        if intent == IntentType.INVENTORY_QUERY:
            return self._handle_inventory_query(text, known_products)
        elif intent == IntentType.SALES_QUERY:
            return self._handle_sales_query()
        elif intent == IntentType.PROFIT_QUERY:
            return self._handle_profit_query()

        # ----------------------------------------------------
        # CASE E: MULTI-TURN SLOT FILLING (When waiting for a missing slot)
        # ----------------------------------------------------
        if ctx.state in (ContextState.AWAITING_QUANTITY, ContextState.AWAITING_AMOUNT, ContextState.AWAITING_PRODUCT):
            # Check if this input fills the missing slot
            filled = False
            if ctx.state == ContextState.AWAITING_QUANTITY:
                qty, unit = extract_quantity_and_unit(text)
                if qty is not None:
                    ctx.quantity = qty
                    if unit:
                        ctx.unit = unit
                    if "quantity" in (ctx.missing_slots or []):
                        ctx.missing_slots.remove("quantity")
                    filled = True

            elif ctx.state == ContextState.AWAITING_AMOUNT:
                amt = extract_amount(text)
                if amt is not None:
                    ctx.amount = amt
                    if "amount" in (ctx.missing_slots or []):
                        ctx.missing_slots.remove("amount")
                    filled = True

            elif ctx.state == ContextState.AWAITING_PRODUCT:
                prod = extract_product_name(text, known_products)
                if prod:
                    ctx.product = prod
                    if "product" in (ctx.missing_slots or []):
                        ctx.missing_slots.remove("product")
                    filled = True

            if filled:
                self.context_mgr.save_context(ctx)
                return self._evaluate_and_respond(ctx, text)

        # ----------------------------------------------------
        # CASE F: NEW TRANSACTION (PURCHASE, SALE, EXPENSE)
        # ----------------------------------------------------
        if intent in (IntentType.PURCHASE, IntentType.SALE, IntentType.EXPENSE):
            entities = extract_all_entities(text, intent=intent, known_products=known_products)
            
            # If product exists in database, use product's default unit if not mentioned
            if entities.get("product") and not entities.get("unit"):
                prod_obj = self._get_product_by_name(entities["product"])
                if prod_obj:
                    entities["unit"] = prod_obj.unit

            # Calculate confidence and missing fields
            conf_score, conf_status, missing_slots, factors = calculate_confidence(intent, entities, text)
            
            # Create fresh pending context
            ctx = PendingContext(
                session_id=self.session_id,
                state=ContextState.IDLE,
                intent=intent,
                product=entities.get("product"),
                quantity=entities.get("quantity"),
                unit=entities.get("unit"),
                amount=entities.get("amount"),
                party_name=entities.get("party_name"),
                category=entities.get("category"),
                missing_slots=missing_slots,
                confidence=conf_score,
                confidence_breakdown=factors,
                raw_input=text
            )
            self.context_mgr.save_context(ctx)
            return self._evaluate_and_respond(ctx, text)

        # ----------------------------------------------------
        # CASE G: UNKNOWN INTENT FALLBACK
        # ----------------------------------------------------
        return {
            "success": False,
            "message": "I didn't quite catch that. You can say commands like:\n• 'Bought 20 kg rice from Kumar for 800 rupees'\n• 'Sold 5 packets biscuits for 150 rupees'\n• 'Paid 400 for electricity bill'\n• 'Check stock of rice' or 'What is our profit?'",
            "state": ContextState.IDLE,
            "intent": IntentType.UNKNOWN,
            "confidence": 0.20,
            "confidence_status": "LOW",
            "confidence_factors": ["No recognized keywords for Purchase, Sale, Expense, or Queries."],
            "context": None,
            "requires_confirmation": False
        }

    def _evaluate_and_respond(self, ctx: PendingContext, current_input: str, prefix_message: str = "") -> Dict[str, Any]:
        """
        Evaluate current context completeness and inventory availability,
        then determine whether to ask for missing slots or request confirmation.
        """
        from services.inventory_service import InventoryService
        inv_service = InventoryService(db_path=self.db_path)
        
        # Check missing slots for the transaction type
        missing = []
        if ctx.intent in (IntentType.PURCHASE, IntentType.SALE):
            if not ctx.product:
                missing.append("product")
            if ctx.quantity is None or ctx.quantity <= 0:
                missing.append("quantity")
            if ctx.amount is None or ctx.amount <= 0:
                missing.append("amount")
        elif ctx.intent == IntentType.EXPENSE:
            if not ctx.category:
                missing.append("category")
            if ctx.amount is None or ctx.amount <= 0:
                missing.append("amount")

        ctx.missing_slots = missing

        # Recalculate explainable confidence
        entities = {
            "product": ctx.product,
            "quantity": ctx.quantity,
            "unit": ctx.unit,
            "amount": ctx.amount,
            "party_name": ctx.party_name,
            "category": ctx.category
        }
        conf_score, conf_status, _, factors = calculate_confidence(ctx.intent, entities, current_input)
        ctx.confidence = conf_score
        ctx.confidence_breakdown = factors

        # If missing information, transition state to slot question
        if missing:
            next_missing = missing[0]
            if next_missing == "product":
                ctx.state = ContextState.AWAITING_PRODUCT
                prompt = "Which product is this transaction for?"
            elif next_missing == "quantity":
                ctx.state = ContextState.AWAITING_QUANTITY
                action_word = "purchase" if ctx.intent == IntentType.PURCHASE else "sell"
                prod_name = f" of {ctx.product}" if ctx.product else ""
                prompt = f"What quantity{prod_name} did you {action_word}?"
            elif next_missing == "amount":
                ctx.state = ContextState.AWAITING_AMOUNT
                action_word = "purchase" if ctx.intent == IntentType.PURCHASE else "sale"
                prompt = f"What was the total {action_word} amount in rupees?"
            elif next_missing == "category":
                prompt = "What is the expense category or description?"

            ctx.last_prompt = prompt
            self.context_mgr.save_context(ctx)

            full_msg = f"{prefix_message} {prompt}".strip() if prefix_message else prompt
            return {
                "success": True,
                "message": full_msg,
                "state": ctx.state,
                "intent": ctx.intent,
                "confidence": ctx.confidence,
                "confidence_status": conf_status,
                "confidence_factors": factors,
                "context": ctx.to_dict(),
                "requires_confirmation": False
            }

        # If SALE, check stock availability before asking for confirmation!
        if ctx.intent == IntentType.SALE and ctx.product and ctx.quantity:
            prod_obj = self._get_product_by_name(ctx.product)
            if not prod_obj:
                msg = f"Product '{ctx.product}' does not exist in inventory. Please add or purchase stock first."
                ctx.state = ContextState.IDLE
                self.context_mgr.save_context(ctx)
                return {
                    "success": False,
                    "message": msg,
                    "state": ContextState.IDLE,
                    "intent": ctx.intent,
                    "confidence": ctx.confidence,
                    "confidence_status": conf_status,
                    "confidence_factors": factors + [f"Inventory check failed: '{ctx.product}' not found"],
                    "context": ctx.to_dict(),
                    "requires_confirmation": False
                }
            
            # Stock check
            if prod_obj.current_stock < ctx.quantity:
                msg = f"Insufficient stock. Available stock: {prod_obj.current_stock} {prod_obj.unit}, requested: {ctx.quantity} {ctx.unit or prod_obj.unit}."
                # Keep context open so user can say "Actually change quantity to 5"
                ctx.state = ContextState.AWAITING_CONFIRMATION
                ctx.missing_slots = ["quantity"] # mark quantity as invalid
                self.context_mgr.save_context(ctx)
                return {
                    "success": False,
                    "message": f"{msg} Say 'Change quantity to {int(prod_obj.current_stock)}' or 'Cancel'.",
                    "state": ContextState.AWAITING_CONFIRMATION,
                    "intent": ctx.intent,
                    "confidence": 0.65,
                    "confidence_status": "MEDIUM",
                    "confidence_factors": factors + [f"Negative stock prevention triggered: stock={prod_obj.current_stock}"],
                    "context": ctx.to_dict(),
                    "requires_confirmation": False,
                    "is_insufficient_stock": True,
                    "available_stock": prod_obj.current_stock
                }

        # All required fields present and valid! Formulate smart confirmation prompt
        ctx.state = ContextState.AWAITING_CONFIRMATION
        
        unit_str = f" {ctx.unit}" if ctx.unit else ""
        if ctx.intent == IntentType.PURCHASE:
            party_str = f" from {ctx.party_name}" if ctx.party_name else ""
            confirm_msg = f"Please confirm: Purchase {ctx.quantity:g}{unit_str} {ctx.product} for {Config.CURRENCY_SYMBOL}{ctx.amount:g}{party_str}?"
        elif ctx.intent == IntentType.SALE:
            party_str = f" to {ctx.party_name}" if ctx.party_name else ""
            confirm_msg = f"Please confirm: Sale of {ctx.quantity:g}{unit_str} {ctx.product} for {Config.CURRENCY_SYMBOL}{ctx.amount:g}{party_str}?"
        else: # EXPENSE
            confirm_msg = f"Please confirm: Expense of {Config.CURRENCY_SYMBOL}{ctx.amount:g} for '{ctx.category}'?"

        ctx.last_prompt = confirm_msg
        self.context_mgr.save_context(ctx)

        full_msg = f"{prefix_message} {confirm_msg}".strip() if prefix_message else confirm_msg

        return {
            "success": True,
            "message": full_msg,
            "state": ctx.state,
            "intent": ctx.intent,
            "confidence": ctx.confidence,
            "confidence_status": conf_status,
            "confidence_factors": factors,
            "context": ctx.to_dict(),
            "requires_confirmation": True
        }

    def _execute_confirmed_transaction(self, ctx: PendingContext) -> Dict[str, Any]:
        """Commit the pending transaction into SQLite database and update inventory & profit."""
        from services.transaction_service import TransactionService
        tx_service = TransactionService(db_path=self.db_path)

        try:
            if ctx.intent == IntentType.PURCHASE:
                res = tx_service.record_purchase(
                    product_name=ctx.product,
                    quantity=ctx.quantity,
                    unit=ctx.unit or "pcs",
                    total_amount=ctx.amount,
                    supplier_name=ctx.party_name,
                    notes=ctx.raw_input
                )
                success_msg = f"Success! Recorded Purchase of {ctx.quantity:g} {ctx.unit or 'pcs'} {ctx.product} for {Config.CURRENCY_SYMBOL}{ctx.amount:g}. Stock updated: {res['new_stock']} {res['unit']}."

            elif ctx.intent == IntentType.SALE:
                res = tx_service.record_sale(
                    product_name=ctx.product,
                    quantity=ctx.quantity,
                    unit=ctx.unit or "pcs",
                    total_amount=ctx.amount,
                    customer_name=ctx.party_name,
                    notes=ctx.raw_input
                )
                profit_str = f" (Profit: {Config.CURRENCY_SYMBOL}{res['profit']:g})" if res.get('profit') is not None else ""
                success_msg = f"Success! Recorded Sale of {ctx.quantity:g} {ctx.unit or 'pcs'} {ctx.product} for {Config.CURRENCY_SYMBOL}{ctx.amount:g}{profit_str}. Remaining stock: {res['new_stock']} {res['unit']}."

            elif ctx.intent == IntentType.EXPENSE:
                res = tx_service.record_expense(
                    category=ctx.category or "Miscellaneous",
                    total_amount=ctx.amount,
                    notes=ctx.raw_input
                )
                success_msg = f"Success! Recorded Expense of {Config.CURRENCY_SYMBOL}{ctx.amount:g} for '{ctx.category}'."

            else:
                return {
                    "success": False,
                    "message": f"Unsupported transaction intent: {ctx.intent}",
                    "state": ContextState.IDLE,
                    "confidence": 0.50,
                    "confidence_status": "LOW",
                    "confidence_factors": ["Unknown intent"],
                    "context": None,
                    "requires_confirmation": False
                }

            # Transaction successful, reset context to IDLE
            self.context_mgr.reset_context()

            return {
                "success": True,
                "message": success_msg,
                "state": ContextState.IDLE,
                "intent": ctx.intent,
                "confidence": 0.96,
                "confidence_status": "HIGH",
                "confidence_factors": ["Transaction confirmed by user and committed to SQLite"],
                "context": None,
                "transaction_data": res,
                "requires_confirmation": False
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Transaction error: {str(e)}",
                "state": ctx.state,
                "intent": ctx.intent,
                "confidence": ctx.confidence,
                "confidence_status": "MEDIUM",
                "confidence_factors": [f"Database error: {str(e)}"],
                "context": ctx.to_dict(),
                "requires_confirmation": False
            }

    def _handle_inventory_query(self, text: str, known_products: List[str]) -> Dict[str, Any]:
        """Handle stock and inventory natural language queries."""
        from services.inventory_service import InventoryService
        inv_service = InventoryService(db_path=self.db_path)

        product_name = extract_product_name(text, known_products)
        if product_name:
            prod = inv_service.find_product_by_name(product_name)
            if prod:
                status_note = " (LOW STOCK ALERT!)" if prod.current_stock <= prod.min_stock_alert else ""
                msg = f"Current stock of {prod.name}: {prod.current_stock:g} {prod.unit} (Selling price: {Config.CURRENCY_SYMBOL}{prod.selling_price:g}){status_note}."
            else:
                msg = f"Product '{product_name}' was not found in inventory catalog."
        else:
            summary = inv_service.get_stock_summary()
            msg = f"Inventory Summary: {summary['total_products']} products in catalog. Total items: {summary['total_items']:g}. Low stock alerts: {summary['low_stock_count']}."

        return {
            "success": True,
            "message": msg,
            "state": ContextState.IDLE,
            "intent": IntentType.INVENTORY_QUERY,
            "confidence": 0.92,
            "confidence_status": "HIGH",
            "confidence_factors": ["Stock query executed against product database"],
            "context": None,
            "requires_confirmation": False
        }

    def _handle_sales_query(self) -> Dict[str, Any]:
        """Handle sales total and summary query."""
        from services.profit_service import ProfitService
        profit_service = ProfitService(db_path=self.db_path)
        summary = profit_service.get_financial_summary()
        
        msg = f"Sales Summary: Total Sales Revenue is {Config.CURRENCY_SYMBOL}{summary['total_sales']:g} across {summary['sales_count']} transactions."
        return {
            "success": True,
            "message": msg,
            "state": ContextState.IDLE,
            "intent": IntentType.SALES_QUERY,
            "confidence": 0.94,
            "confidence_status": "HIGH",
            "confidence_factors": ["Sales query calculated from transaction ledger"],
            "context": None,
            "requires_confirmation": False
        }

    def _handle_profit_query(self) -> Dict[str, Any]:
        """Handle profit & loss query."""
        from services.profit_service import ProfitService
        profit_service = ProfitService(db_path=self.db_path)
        summary = profit_service.get_financial_summary()
        
        profit = summary['net_profit']
        status_text = "Net Profit" if profit >= 0 else "Net Loss"
        msg = f"Financial Status: {status_text} is {Config.CURRENCY_SYMBOL}{abs(profit):g} (Sales: {Config.CURRENCY_SYMBOL}{summary['total_sales']:g}, Purchases: {Config.CURRENCY_SYMBOL}{summary['total_purchases']:g}, Expenses: {Config.CURRENCY_SYMBOL}{summary['total_expenses']:g})."

        return {
            "success": True,
            "message": msg,
            "state": ContextState.IDLE,
            "intent": IntentType.PROFIT_QUERY,
            "confidence": 0.94,
            "confidence_status": "HIGH",
            "confidence_factors": ["Profit calculated: Total Sales - Total Purchases - Total Expenses"],
            "context": None,
            "requires_confirmation": False
        }
