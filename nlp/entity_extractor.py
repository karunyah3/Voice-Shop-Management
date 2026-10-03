"""
Entity Extraction Module using Rule-Based Tokenization, Regular Expressions, and Slot Parsing.
Extracts product, quantity, unit, amount, supplier, customer, category, and correction targets.
"""
import re
from typing import Dict, Any, Optional, List, Tuple
from config import Config

# Word numbers mapping
WORD_NUMBERS = {
    'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
    'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
    'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
    'eighty': 80, 'ninety': 90, 'hundred': 100, 'thousand': 1000,
    'half': 0.5, 'quarter': 0.25, 'a': 1, 'an': 1, 'one and a half': 1.5, 'two and a half': 2.5
}

# Unit normalizations
UNIT_MAP = {
    'kg': 'kg', 'kgs': 'kg', 'kilogram': 'kg', 'kilograms': 'kg', 'kilo': 'kg', 'kilos': 'kg',
    'g': 'g', 'gm': 'g', 'gms': 'g', 'gram': 'g', 'grams': 'g',
    'packet': 'packets', 'packets': 'packets', 'pkt': 'packets', 'pkts': 'packets', 'pack': 'packets', 'packs': 'packets',
    'box': 'boxes', 'boxes': 'boxes',
    'piece': 'pieces', 'pieces': 'pieces', 'pcs': 'pieces', 'pc': 'pieces', 'item': 'pieces', 'items': 'pieces',
    'liter': 'liters', 'liters': 'liters', 'litre': 'liters', 'litres': 'liters', 'l': 'liters', 'ltr': 'liters', 'ltrs': 'liters',
    'ml': 'ml', 'milliliter': 'ml', 'milliliters': 'ml',
    'bottle': 'bottles', 'bottles': 'bottles', 'btl': 'bottles',
    'can': 'cans', 'cans': 'cans',
    'bag': 'bags', 'bags': 'bags', 'sack': 'bags', 'sacks': 'bags',
    'carton': 'cartons', 'cartons': 'cartons',
    'dozen': 'dozens', 'dozens': 'dozens', 'dz': 'dozens'
}

# Common expense categories
EXPENSE_CATEGORIES = {
    'rent': 'Shop Rent',
    'electricity': 'Electricity Bill',
    'power': 'Electricity Bill',
    'tea': 'Tea & Refreshments',
    'coffee': 'Tea & Refreshments',
    'snacks': 'Tea & Refreshments',
    'cleaning': 'Cleaning & Sanitation',
    'sweep': 'Cleaning & Sanitation',
    'maintenance': 'Repairs & Maintenance',
    'repair': 'Repairs & Maintenance',
    'transport': 'Transportation & Logistics',
    'freight': 'Transportation & Logistics',
    'delivery': 'Transportation & Logistics',
    'salary': 'Staff Salary',
    'wages': 'Staff Wages',
    'packaging': 'Packaging Material',
    'stationery': 'Stationery & Printing',
    'water': 'Water Supply',
    'misc': 'Miscellaneous'
}

# Known common shop products for keyword fallback
COMMON_PRODUCTS = [
    "rice", "basmati rice", "sugar", "brown sugar", "biscuits", "sunflower oil",
    "mustard oil", "cooking oil", "oil", "tea powder", "tea", "coffee powder",
    "coffee", "wheat flour", "atta", "maida", "milk", "butter", "cheese", "paneer",
    "bath soap", "soap", "detergent", "washing powder", "salt", "black salt",
    "toor dal", "moong dal", "chana dal", "dal", "pulses", "shampoo", "toothpaste",
    "bread", "eggs", "matchbox", "noodles", "maggie", "chips", "cold drink",
    "spices", "turmeric", "chilli powder", "coriander powder", "garam masala"
]

def parse_word_number(text: str) -> Optional[float]:
    """Parse text that may contain spoken number words (e.g. 'twenty five', 'two and a half')."""
    cleaned = text.strip().lower()
    
    # Direct check
    if cleaned in WORD_NUMBERS:
        return float(WORD_NUMBERS[cleaned])
        
    # Compound numbers e.g. "twenty five"
    words = cleaned.split()
    total = 0.0
    found_any = False
    
    for i, w in enumerate(words):
        if w in WORD_NUMBERS:
            val = WORD_NUMBERS[w]
            found_any = True
            if val == 100 or val == 1000:
                if total == 0:
                    total = val
                else:
                    total *= val
            else:
                total += val
        elif w == "and":
            continue
        else:
            # Check if digit directly
            try:
                val = float(w)
                found_any = True
                total += val
            except ValueError:
                pass
                
    return total if found_any and total > 0 else None

def extract_amount(text: str) -> Optional[float]:
    """
    Extract transaction money amount from text.
    Patterns:
    - 'for 800 rupees', '₹800', 'rs 800', 'rs. 800', '800 rs', '800 inr', 'for 800', 'amount 800'
    """
    cleaned = text.lower()
    
    # Pattern 1: Currency symbols / prefixes: ₹800, rs 800, rs. 800, inr 800
    m = re.search(r'(?:₹|rs\.?|inr)\s*([0-9]+(?:\.[0-9]+)?)', cleaned, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass

    # Pattern 2: Suffix currency: 800 rupees, 800 rs, 800 rps, 800 bucks
    m = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(?:rupees|rupee|rs|rps|inr|bucks)', cleaned, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass

    # Pattern 3: 'for 800', 'at 800', 'paid 800', 'amount 800', 'cost 800'
    m = re.search(r'\b(?:for|at|paid|amount|cost|worth|price)\s+(?:of\s+)?([0-9]+(?:\.[0-9]+)?)\b', cleaned, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass

    # Pattern 4: When input is just an amount (e.g. answering slot: "800" or "800 rupees")
    m = re.match(r'^\s*([0-9]+(?:\.[0-9]+)?)\s*$', cleaned)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass

    # Word amount: e.g. "for seven hundred rupees", "seven hundred rupees", "paid five hundred"
    # 1. Prepositional word amount: for/at/worth/paid/cost/amount
    m = re.search(r'\b(?:for|at|worth|paid|cost|amount\s+of)\s+([a-z\s\-]+?)(?:\s*(?:rupees|rupee|rs|inr|bucks|\.|$))', cleaned)
    if m:
        num = parse_word_number(m.group(1))
        if num is not None and num > 0:
            return num

    # 2. Direct word amount preceding currency: "seven hundred rupees" (limit to last 1-4 words)
    m = re.search(r'((?:[a-z\-]+\s*){1,4})\s*(?:rupees|rupee|rs|inr|bucks)', cleaned)
    if m:
        num = parse_word_number(m.group(1))
        if num is not None and num > 0:
            return num

    return None

def extract_quantity_and_unit(text: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Extract quantity number and unit of measurement from text.
    Example: '20 kg', '5 packets', '10.5 liters', '10 pcs', 'twenty kg', '5'
    """
    cleaned = text.lower()
    unit_regex = r'(kg|kgs|kilograms?|g|grams?|gm|packets?|pkts?|packs?|boxes?|pieces?|pcs|liters?|litres?|ltrs?|l|ml|bottles?|cans?|bags?|cartons?|dozens?)'
    
    # Pattern 1: Digit + Unit (e.g. "20 kg", "5 packets", "10.5 liters")
    m = re.search(rf'([0-9]+(?:\.[0-9]+)?|\d+/\d+)\s*{unit_regex}\b', cleaned, re.IGNORECASE)
    if m:
        raw_qty = m.group(1)
        raw_unit = m.group(2).lower()
        
        # Handle fractions like 1/2
        if '/' in raw_qty:
            num, denom = raw_qty.split('/')
            qty = float(num) / float(denom)
        else:
            qty = float(raw_qty)
            
        unit = UNIT_MAP.get(raw_unit, raw_unit)
        return qty, unit

    # Pattern 2: Spoken number + Unit (e.g. "twenty kg", "five packets")
    m = re.search(rf'((?:[a-z\-]+\s*){{1,3}})\s+{unit_regex}\b', cleaned, re.IGNORECASE)
    if m:
        word_num = m.group(1).strip()
        raw_unit = m.group(2).lower()
        qty = parse_word_number(word_num)
        if qty is not None:
            unit = UNIT_MAP.get(raw_unit, raw_unit)
            return qty, unit

    # Pattern 3: Standalone number in slot filling (e.g. "20" or "5")
    # Avoid matching amounts if rupees is mentioned
    if not re.search(r'(rupee|rs|₹|inr)', cleaned):
        m = re.search(r'\b([0-9]+(?:\.[0-9]+)?)\b', cleaned)
        if m:
            qty = float(m.group(1))
            return qty, None

    return None, None

def extract_party_name(text: str, intent: str = "PURCHASE") -> Optional[str]:
    """
    Extract supplier or customer name.
    Purchase: 'from Kumar', 'from Ramesh Agencies'
    Sale: 'to Rahul', 'to Priya Sharma'
    """
    cleaned = text.strip()
    
    # Supplier patterns: 'from <Name>' (stop before for/at/rs/rupees/worth)
    if intent == "PURCHASE" or "from" in cleaned.lower():
        m = re.search(r'\bfrom\s+([A-Za-z\s\.\'\-]+?)(?=\s+(?:for|at|worth|on|amount|rs|₹|\d|$))', cleaned, re.IGNORECASE)
        if m:
            name = m.group(1).strip().strip(".,")
            # Filter out non-names like 'the shop' or 'supplier'
            if name and name.lower() not in ['supplier', 'vendor', 'market', 'wholesale']:
                return name.title()

    # Customer patterns: 'to <Name>' (stop before for/at/rs/rupees/worth)
    if intent == "SALE" or "to" in cleaned.lower():
        m = re.search(r'\b(?:to|for customer)\s+([A-Za-z\s\.\'\-]+?)(?=\s+(?:for|at|worth|on|amount|rs|₹|\d|$))', cleaned, re.IGNORECASE)
        if m:
            name = m.group(1).strip().strip(".,")
            if name and name.lower() not in ['customer', 'client', 'buyer']:
                return name.title()

    return None

def extract_expense_category(text: str) -> Tuple[str, Optional[str]]:
    """
    Extract category and description for an expense.
    E.g. 'paid 500 for shop electricity bill' -> ('Electricity Bill', 'shop electricity bill')
    """
    cleaned = text.lower()
    for keyword, category_name in EXPENSE_CATEGORIES.items():
        if re.search(rf'\b{keyword}\b', cleaned):
            return category_name, keyword.title()
            
    # Default fallback
    return "Miscellaneous Expense", "Shop Expense"

def extract_product_name(text: str, known_products: List[str] = None) -> Optional[str]:
    """
    Extract the product name from input text.
    Combines known product catalog matching with syntactic structural extraction.
    """
    cleaned = text.lower().strip()
    
    # 1. Check against known products from catalog / common products (longest match first)
    search_list = sorted((known_products or []) + COMMON_PRODUCTS, key=len, reverse=True)
    for p in search_list:
        p_clean = p.lower()
        pattern = rf'\b{re.escape(p_clean)}\b'
        if re.search(pattern, cleaned):
            return p.title()

    # 2. Syntactic Structural Extraction:
    # "Bought 20 kg [Product] from Kumar for 800"
    # "Sold 5 packets [Product] for 150"
    patterns = [
        # After unit: "20 kg rice for..." / "5 packets biscuits to..."
        r'(?:kg|kgs|kilograms?|packets?|pkts?|boxes?|pieces?|pcs|liters?|litres?|ml|bottles?|cans?|bags?|cartons?|dozens?)\s+([a-zA-Z\s]{2,30}?)(?=\s+(?:from|to|for|at|worth|amount|rs|₹|\d|$))',
        # After verb: "bought rice from..." / "sold sugar for..." / "bought sugar"
        r'\b(?:bought|buy|purchased|purchase|sold|sell|sale|stock of|stock|check)\s+([a-zA-Z\s]{2,30}?)(?=\s+(?:from|to|for|at|worth|amount|rs|₹|\d|$))',
        # Standalone product name in slot filling: "rice" or "basmati rice"
        r'^\s*([a-zA-Z\s]{2,30})\s*$'
    ]
    
    for pat in patterns:
        m = re.search(pat, cleaned, re.IGNORECASE)
        if m:
            cand = m.group(1).strip()
            # Filter stop words
            cand_words = [w for w in cand.split() if w not in ['the', 'a', 'an', 'some', 'of', 'for', 'from', 'to']]
            if cand_words:
                cand_clean = " ".join(cand_words).strip()
                if len(cand_clean) >= 2:
                    return cand_clean.title()

    return None

def extract_correction_target(text: str) -> Dict[str, Any]:
    """
    Extract target slot and value from correction commands.
    Examples:
    - 'Actually change the quantity to 15 kg'
    - 'Change amount to 750 rupees'
    - 'Change product to sugar'
    - 'Make it 10 packets'
    - 'No, price is 500'
    """
    cleaned = text.lower().strip()
    result = {"target_slot": None, "value": None, "unit": None}

    # Check for quantity correction
    if re.search(r'\b(quantity|qty|count|number of|packets|kg|liters|pcs)\b', cleaned) or re.search(r'\b(to|make it)\s+\d+\s*(kg|packets|pcs|liters|boxes|g)?', cleaned):
        qty, unit = extract_quantity_and_unit(cleaned)
        if qty is not None:
            result["target_slot"] = "quantity"
            result["value"] = qty
            result["unit"] = unit
            return result

    # Check for amount/price correction
    if re.search(r'\b(amount|price|cost|rate|rupees|rs|₹)\b', cleaned):
        amt = extract_amount(cleaned)
        if amt is not None:
            result["target_slot"] = "amount"
            result["value"] = amt
            return result

    # Check for product correction
    if re.search(r'\b(product|item|change product to|make product)\b', cleaned):
        prod = extract_product_name(cleaned)
        if prod:
            result["target_slot"] = "product"
            result["value"] = prod
            return result

    # Check for supplier/customer correction
    if re.search(r'\b(supplier|vendor|from|customer|to)\b', cleaned):
        party = extract_party_name(cleaned)
        if party:
            result["target_slot"] = "party_name"
            result["value"] = party
            return result

    # General number fallback in correction
    amt = extract_amount(cleaned)
    qty, unit = extract_quantity_and_unit(cleaned)
    if unit:
        result["target_slot"] = "quantity"
        result["value"] = qty
        result["unit"] = unit
    elif amt is not None:
        result["target_slot"] = "amount"
        result["value"] = amt

    return result

def extract_all_entities(text: str, intent: str = "PURCHASE", known_products: List[str] = None) -> Dict[str, Any]:
    """
    Comprehensive entity extractor returning a structured dictionary of all detected slots.
    """
    amount = extract_amount(text)
    qty, unit = extract_quantity_and_unit(text)
    party_name = extract_party_name(text, intent)
    
    product = None
    category = None
    
    if intent in ("PURCHASE", "SALE", "INVENTORY_QUERY"):
        product = extract_product_name(text, known_products)
    elif intent == "EXPENSE":
        category, _ = extract_expense_category(text)

    return {
        "product": product,
        "quantity": qty,
        "unit": unit,
        "amount": amount,
        "party_name": party_name,
        "category": category,
        "raw_text": text
    }
