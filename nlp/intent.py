"""
Intent Classification Module using Rule-Based Pattern Matching and Keyword Scoring.
Explainable and academic architecture without external LLM dependencies.
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
        (r"^(yes|yep|yeah|confirm|proceed|save|save it|correct|approve|sure|ok|okay|haan|theek hai|yes please)$", 0.95),
        (r"\b(confirm|save it|proceed with this|looks good|yes save)\b", 0.90),
    ],
    IntentType.CANCELLATION: [
        (r"^(no|nope|cancel|discard|abort|stop|don't save|do not save|forget it|nevermind|reject)$", 0.95),
        (r"\b(cancel transaction|discard this|don't save this|abort)\b", 0.90),
    ],
    IntentType.CORRECTION: [
        (r"\b(actually|change|correction|modify|instead of|make it|update|not \d+|replace)\b", 0.85),
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
        (r"\b(paid (rent|electricity|salary|maintenance|transport|tea|cleaning))\b", 0.92),
    ],
    IntentType.PURCHASE: [
        (r"\b(bought|buy|purchased|purchase|procured|got from|restocked|received stock|stock in|inward)\b", 0.90),
        (r"\b(bought from|purchased from|supplier)\b", 0.92),
    ],
    IntentType.SALE: [
        (r"\b(sold|sell|sale|customer bought|billed|dispatched|stock out|outward|order from|given to)\b", 0.90),
        (r"\b(sold to|sell to|customer)\b", 0.92),
    ]
}

def detect_intent(text: str, current_state: str = "IDLE") -> Tuple[str, float, str]:
    """
    Detect the user intent from natural language input.
    
    Args:
        text: Raw user voice or text input string
        current_state: Context manager state (e.g., AWAITING_CONFIRMATION, AWAITING_QUANTITY, etc.)
        
    Returns:
        Tuple of (intent_name, confidence_score, matched_rule_description)
    """
    cleaned = text.strip().lower()
    
    if not cleaned:
        return IntentType.UNKNOWN, 0.0, "Empty input"

    # Contextual priority: if we are waiting for confirmation, check confirmation/cancellation/correction first
    if current_state in ("AWAITING_CONFIRMATION", "AWAITING_QUANTITY", "AWAITING_AMOUNT", "AWAITING_PRODUCT"):
        for intent in [IntentType.CONFIRMATION, IntentType.CANCELLATION, IntentType.CORRECTION]:
            for pattern, weight in INTENT_PATTERNS[intent]:
                if re.search(pattern, cleaned, re.IGNORECASE):
                    return intent, weight, f"Context matched: {pattern}"

    # General intent pattern scan
    best_intent = IntentType.UNKNOWN
    best_score = 0.0
    best_rule = "No pattern matched"

    for intent, rules in INTENT_PATTERNS.items():
        for pattern, weight in rules:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match:
                # Add slight boost if match starts early in the sentence
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
            if any(w in cleaned for w in ["yes", "ok", "confirm", "proceed", "save"]):
                return IntentType.CONFIRMATION, 0.85, "Context keyword fallback: confirm"
            elif any(w in cleaned for w in ["no", "cancel", "stop", "abort"]):
                return IntentType.CANCELLATION, 0.85, "Context keyword fallback: cancel"

    return best_intent, best_score, best_rule
