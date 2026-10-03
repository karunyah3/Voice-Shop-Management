"""
Transparent and Explainable Confidence Scoring and Slot Validation Module.
Provides academic explanations for why a score was assigned and identifies missing fields.
"""
from typing import Dict, Any, List, Tuple
from config import Config

def calculate_confidence(intent: str, entities: Dict[str, Any], raw_text: str) -> Tuple[float, str, List[str], List[str]]:
    """
    Calculate an explainable confidence score and slot completeness report.
    
    Args:
        intent: Detected intent string
        entities: Dict of extracted entities (product, quantity, unit, amount, etc.)
        raw_text: Original raw input string
        
    Returns:
        Tuple of (confidence_score_0_to_1, confidence_status, missing_slots, factor_explanations)
    """
    factors = []
    missing_slots = []
    score = 0.0

    # 1. Base Intent Match Score
    if intent in ("PURCHASE", "SALE"):
        score += 0.35
        factors.append(f"Intent recognized as '{intent}' (+35%)")
        
        # Check Product
        if entities.get("product"):
            score += 0.25
            factors.append(f"Product identified: '{entities['product']}' (+25%)")
        else:
            missing_slots.append("product")
            factors.append("Missing required field: product (-25%)")

        # Check Quantity
        if entities.get("quantity") is not None and entities.get("quantity") > 0:
            score += 0.20
            unit_str = f" {entities.get('unit')}" if entities.get('unit') else ""
            factors.append(f"Quantity parsed: {entities['quantity']}{unit_str} (+20%)")
            if entities.get("unit"):
                score += 0.05
                factors.append("Standard unit of measurement matched (+5%)")
        else:
            missing_slots.append("quantity")
            factors.append("Missing required field: quantity (-20%)")

        # Check Amount
        if entities.get("amount") is not None and entities.get("amount") > 0:
            score += 0.15
            factors.append(f"Total transaction amount: {Config.CURRENCY_SYMBOL}{entities['amount']} (+15%)")
        else:
            missing_slots.append("amount")
            factors.append("Missing required field: amount (-15%)")

        # Optional Party Bonus (Supplier / Customer)
        if entities.get("party_name"):
            score = min(0.98, score + 0.03)
            party_type = "Supplier" if intent == "PURCHASE" else "Customer"
            factors.append(f"{party_type} name noted: '{entities['party_name']}' (+3%)")

    elif intent == "EXPENSE":
        score += 0.35
        factors.append("Intent recognized as 'EXPENSE' (+35%)")
        
        # Category
        if entities.get("category"):
            score += 0.30
            factors.append(f"Expense category resolved: '{entities['category']}' (+30%)")
        else:
            missing_slots.append("category")
            factors.append("Missing expense category (-30%)")

        # Amount
        if entities.get("amount") is not None and entities.get("amount") > 0:
            score += 0.30
            factors.append(f"Expense amount parsed: {Config.CURRENCY_SYMBOL}{entities['amount']} (+30%)")
        else:
            missing_slots.append("amount")
            factors.append("Missing required field: amount (-30%)")

    elif intent in ("INVENTORY_QUERY", "SALES_QUERY", "PROFIT_QUERY"):
        score += 0.60
        factors.append(f"Query intent '{intent}' matched (+60%)")
        if intent == "INVENTORY_QUERY":
            if entities.get("product"):
                score += 0.35
                factors.append(f"Target product for inventory query: '{entities['product']}' (+35%)")
            else:
                score += 0.25
                factors.append("General inventory query for all items (+25%)")
        else:
            score += 0.30
            factors.append("Analytics query parameters validated (+30%)")

    elif intent in ("CONFIRMATION", "CANCELLATION", "CORRECTION"):
        score = 0.92
        factors.append(f"Context control command '{intent}' identified (+92%)")

    else:
        score = 0.20
        factors.append("Uncertain intent / no known keywords matched (+20%)")

    # Clean score range [0.05, 0.98] - Never claim 100% artificial certainty in academic prototype
    score = max(0.05, min(0.96, round(score, 2)))

    # Determine status level
    if score >= Config.CONFIDENCE_HIGH_THRESHOLD:
        status = "HIGH"
    elif score >= Config.CONFIDENCE_MEDIUM_THRESHOLD:
        status = "MEDIUM"
    else:
        status = "LOW"

    return score, status, missing_slots, factors
