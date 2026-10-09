"""
Intent Classification Module using Rule-Based Natural Language Pattern Matching and Keyword Scoring.
Supports flexible, natural spoken expressions across active, passive, supplier-first, and customer-first sentence structures.
"""
import re
from typing import Tuple, Dict, Any

class IntentType:
    PURCHASE = "PURCHASE"
    SALE = "SALE"
    EXPENSE = "EXPENSE"
    INVENTORY_QUERY = "INVENTORY_QUERY"
    SALES_QUERY = "SALES_QUERY"
    PROFIT_QUERY = "PROFIT_QUERY"
    CORRECTION = "CORRECTION"
    CONFIRMATION = "CONFIRMATION"
    CANCELLATION = "CANCELLATION"
    UNKNOWN = "UNKNOWN"

# Primary keyword and regex pattern rules with weighted scores
INTENT_PATTERNS = {
    IntentType.CONFIRMATION: [
        (r"^(yes|yep|yeah|confirm|proceed|save|save it|correct|approve|approved|sure|ok|okay|haan|theek hai|yes please|done|all good)$", 0.95),
        (r"\b(confirm|save it|proceed with this|looks good|yes save|save transaction)\b", 0.90),
    ],
    IntentType.CANCELLATION: [
        (r"^(no|nope|cancel|discard|abort|stop|don't save|do not save|forget it|nevermind|reject)$", 0.95),
        (r"\b(cancel transaction|discard this|don't save this|abort|cancel it)\b", 0.90),
    ],
    IntentType.CORRECTION: [
        (r"\b(actually|change|correction|modify|instead of|make it|update|replace)\b", 0.85),
        (r"\b(change (the )?(quantity|amount|price|rate|product|supplier|customer) to)\b", 0.95),
        (r"\b(make (it|quantity|amount|price) \d+)\b", 0.90),
    ],
    IntentType.PROFIT_QUERY: [
        (r"\b(what is (the )?(total )?profit|how much profit|profit or loss|net profit|show profit|check profit|our profit|today'?s profit|earnings)\b", 0.90),
        (r"\b(profit margin|are we in profit|loss)\b", 0.80),
    ],
    IntentType.SALES_QUERY: [
        (r"\b(what (are|is) (the )?(total )?sales|how much sales|show sales|check sales|today'?s sales|total revenue|sales today|how much (did we sell|sold today))\b", 0.90),
        (r"\b(sales report|sales summary)\b", 0.85),
    ],
    IntentType.INVENTORY_QUERY: [
        (r"\b(what is (the )?stock of|how much .* (is left|in stock|available)|check stock of|show inventory|check inventory|available stock|stock level|do we have .* in stock)\b", 0.90),
        (r"\b(stock of|inventory of|how many .* left)\b", 0.85),
    ],
    IntentType.EXPENSE: [
        (r"\b(paid|spent|expense|bill|charges|salary|rent|electricity|maintenance|repair|transport|tea|cleaning|packaging)\b", 0.80),
        (r"\b(paid (rs|rupees|₹)?\s*\d+ for|spent \d+ on|expense of \d+)\b", 0.90),
        (r"\b(paid (rent|electricity|salary|maintenance|transport|tea|cleaning|water))\b", 0.92),
    ],
    # Purchase patterns:
    # 1. "bought ... from ...", "purchased ... from ...", "got ... from ..."
    # 2. Supplier as subject: "Arun supplied me...", "Arun gave me...", "Arun sold me...", "Arun brought..."
    # 3. Inward items: "Sugar from Arun, 500 rupees", "came from Arun", "today got 10 kg rice from Arun"
    IntentType.PURCHASE: [
        (r"\b(bought|buy|purchased|purchase|procured|got from|restocked|received stock|stock in|inward|got)\b", 0.90),
        (r"\b(bought from|purchased from|supplier|got .* from|came from|received from)\b", 0.92),
        (r"\b[A-Za-z]+\s+(supplied|gave me|gave|sold me|brought|delivered)\b", 0.92),
        (r"\b(from\s+[A-Za-z]+)\b", 0.85),
    ],
    # Sale patterns:
    # 1. "sold ... to ...", "sell ...", "billed to ..."
    # 2. Customer as subject: "Arun bought 500 rupees worth...", "Rahul took 2 kg...", "Customer bought..."
    IntentType.SALE: [
        (r"\b(sold|sell|sale|customer bought|billed|dispatched|stock out|outward|given to)\b", 0.90),
        (r"\b(sold to|sell to|customer|billed to)\b", 0.92),
        (r"(?<!\bfrom\s)\b[A-Za-z]+\s+(bought|purchased|took|ordered)\s+(?:for|\d+|rupees|worth|kg|packets|sugar|rice|oil|dal|tea|soap|atta)\b", 0.92),
    ]
}

from .entity_extractor import resolve_in_utterance_corrections

def detect_intent(text: str, current_state: str = "IDLE") -> Tuple[str, float, str]:
    """
    Detect the user intent from flexible natural language input.
    
    Args:
        text: Raw user voice or text input string
        current_state: Context manager state (e.g., AWAITING_CONFIRMATION, AWAITING_QUANTITY, etc.)
        
    Returns:
        Tuple of (intent_name, confidence_score, matched_rule_description)
    """
    raw_cleaned = text.strip().lower()
    if not raw_cleaned:
        return IntentType.UNKNOWN, 0.0, "Empty input"

    # Resolve in-utterance self-correction if present (e.g. "Sell 5 kg wait no 10 kg")
    effective_text, _ = resolve_in_utterance_corrections(text)
    cleaned = effective_text.strip().lower()

    # Contextual priority: if we are waiting for confirmation/slots, check control commands first
    if current_state in ("AWAITING_CONFIRMATION", "AWAITING_QUANTITY", "AWAITING_AMOUNT", "AWAITING_PRODUCT"):
        for intent in [IntentType.CONFIRMATION, IntentType.CANCELLATION, IntentType.CORRECTION]:
            for pattern, weight in INTENT_PATTERNS[intent]:
                if re.search(pattern, cleaned, re.IGNORECASE):
                    return intent, weight, f"Context matched: {pattern}"

    # Specific distinction between "Supplier sold me" (PURCHASE) and "Sold to customer" (SALE)
    # If phrase contains "sold me" or "gave me" or "supplied me" -> PURCHASE
    if re.search(r'\b(sold me|gave me|supplied|brought|delivered to me|came from|got .* from)\b', cleaned):
        return IntentType.PURCHASE, 0.93, "Natural language purchase indicator"

    # If phrase contains "<Name> bought ... worth of ..." or "<Name> took ... from shop" -> SALE
    # e.g., "Arun bought 500 rupees worth of sugar", but NOT "From Arun bought..." or "I bought from Arun"
    if re.search(r'\b[a-z]+\s+bought\b', cleaned) and not re.search(r'\b(i bought|we bought|bought from|from\s+[a-z]+\s+bought)\b', cleaned) and not re.search(r'^\s*from\s+', cleaned):
        return IntentType.SALE, 0.92, "Customer bought pattern -> Sale"

    # If phrase contains "from <Name>" and a product name, but no explicit verb -> PURCHASE
    # e.g. "Sugar from Arun, 500 rupees" or "Got 500 grams sugar from Arun" or "From Arun bought 10 kg sugar"
    if re.search(r'\bfrom\s+[a-z]+\b', cleaned) and not re.search(r'\b(sold|sell|sale)\b', cleaned):
        return IntentType.PURCHASE, 0.88, "Inward source 'from <party>' matched -> Purchase"

    # If phrase has "to <Name>" and no explicit purchase verb -> SALE
    # e.g. "5 kg rice to Rahul for 300"
    if re.search(r'\bto\s+[a-z]+\b', cleaned) and not re.search(r'\b(bought|purchase|got from|came from)\b', cleaned):
        return IntentType.SALE, 0.88, "Outward destination 'to <party>' matched -> Sale"

    # General intent pattern scan
    best_intent = IntentType.UNKNOWN
    best_score = 0.0
    best_rule = "No pattern matched"

    for intent, rules in INTENT_PATTERNS.items():
        for pattern, weight in rules:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match:
                score = weight
                if match.start() == 0:
                    score = min(1.0, score + 0.05)
                if score > best_score:
                    best_score = score
                    best_intent = intent
                    best_rule = f"Pattern match: '{pattern}'"

    # Fallback heuristic: single word answers when waiting for slots
    if best_intent == IntentType.UNKNOWN:
        if current_state == "AWAITING_CONFIRMATION":
            if any(w in cleaned for w in ["yes", "ok", "confirm", "proceed", "save", "sure", "haan", "correct"]):
                return IntentType.CONFIRMATION, 0.85, "Context keyword fallback: confirm"
            elif any(w in cleaned for w in ["no", "cancel", "stop", "abort", "discard"]):
                return IntentType.CANCELLATION, 0.85, "Context keyword fallback: cancel"

    return best_intent, best_score, best_rule
