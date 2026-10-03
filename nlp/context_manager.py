"""
Context Manager and Multi-Turn Dialogue State Machine.
Tracks pending transactions, fills missing slots across conversational turns,
and handles real-time corrections without creating duplicate records.
"""
import json
from typing import Optional, Dict, Any, List, Tuple
from database.database import get_db, execute_db, query_db
from database.models import PendingContext
from config import Config

class ContextState:
    IDLE = "IDLE"
    AWAITING_QUANTITY = "AWAITING_QUANTITY"
    AWAITING_AMOUNT = "AWAITING_AMOUNT"
    AWAITING_PRODUCT = "AWAITING_PRODUCT"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"

class ContextManager:
    """
    Manages session dialogue states and pending transaction memory in SQLite.
    """
    def __init__(self, session_id: str = "default_session", db_path: str = None):
        self.session_id = session_id
        self.db_path = db_path

    def get_context(self) -> PendingContext:
        """Fetch current context for session from database or initialize IDLE context."""
        row = query_db(
            "SELECT * FROM pending_contexts WHERE session_id = ?",
            (self.session_id,),
            one=True,
            db_path=self.db_path
        )
        if row:
            return PendingContext.from_row(row)
        
        # Create empty initial context
        ctx = PendingContext(session_id=self.session_id, state=ContextState.IDLE)
        self.save_context(ctx)
        return ctx

    def save_context(self, ctx: PendingContext):
        """Persist context state to SQLite."""
        missing_json = json.dumps(ctx.missing_slots or [])
        breakdown_json = json.dumps(ctx.confidence_breakdown or [])
        
        execute_db("""
            INSERT INTO pending_contexts 
                (session_id, state, intent, product, product_id, quantity, unit, amount, 
                 party_name, category, missing_slots, last_prompt, confidence, confidence_breakdown, raw_input, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id) DO UPDATE SET
                state=excluded.state,
                intent=excluded.intent,
                product=excluded.product,
                product_id=excluded.product_id,
                quantity=excluded.quantity,
                unit=excluded.unit,
                amount=excluded.amount,
                party_name=excluded.party_name,
                category=excluded.category,
                missing_slots=excluded.missing_slots,
                last_prompt=excluded.last_prompt,
                confidence=excluded.confidence,
                confidence_breakdown=excluded.confidence_breakdown,
                raw_input=excluded.raw_input,
                updated_at=CURRENT_TIMESTAMP
        """, (
            ctx.session_id, ctx.state, ctx.intent, ctx.product, ctx.product_id,
            ctx.quantity, ctx.unit, ctx.amount, ctx.party_name, ctx.category,
            missing_json, ctx.last_prompt, ctx.confidence, breakdown_json, ctx.raw_input
        ), db_path=self.db_path)

    def reset_context(self) -> PendingContext:
        """Reset session to clear IDLE state."""
        ctx = PendingContext(session_id=self.session_id, state=ContextState.IDLE)
        self.save_context(ctx)
        return ctx

    def update_slot(self, slot_name: str, value: Any, unit: Optional[str] = None) -> PendingContext:
        """Update a specific slot during conversation or correction."""
        ctx = self.get_context()
        if slot_name == "quantity":
            ctx.quantity = float(value) if value is not None else None
            if unit:
                ctx.unit = unit
        elif slot_name == "amount":
            ctx.amount = float(value) if value is not None else None
        elif slot_name == "product":
            ctx.product = str(value)
        elif slot_name == "party_name":
            ctx.party_name = str(value)
        elif slot_name == "category":
            ctx.category = str(value)
        elif slot_name == "unit":
            ctx.unit = str(value)

        # Remove from missing slots if present
        if ctx.missing_slots and slot_name in ctx.missing_slots:
            ctx.missing_slots.remove(slot_name)

        self.save_context(ctx)
        return ctx

    def apply_correction(self, correction_data: Dict[str, Any]) -> Tuple[PendingContext, str]:
        """
        Apply a user-requested correction to pending transaction fields.
        Returns updated context and explanatory message.
        """
        ctx = self.get_context()
        slot = correction_data.get("target_slot")
        val = correction_data.get("value")
        unit = correction_data.get("unit")

        if not slot or val is None:
            return ctx, "Could not identify what field to correct. Please say: 'Change quantity to 10' or 'Change amount to 500'."

        if slot == "quantity":
            ctx.quantity = float(val)
            if unit:
                ctx.unit = unit
            unit_str = f" {ctx.unit}" if ctx.unit else ""
            msg = f"Updated quantity to {ctx.quantity:g}{unit_str}."
        elif slot == "amount":
            ctx.amount = float(val)
            msg = f"Updated total amount to {Config.CURRENCY_SYMBOL}{ctx.amount:g}."
        elif slot == "product":
            ctx.product = str(val)
            msg = f"Updated product to {ctx.product}."
        elif slot == "party_name":
            ctx.party_name = str(val)
            party_type = "supplier" if ctx.intent == "PURCHASE" else "customer"
            msg = f"Updated {party_type} to {ctx.party_name}."
        else:
            msg = f"Updated {slot} to {val}."

        self.save_context(ctx)
        return ctx, msg
