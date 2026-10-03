"""
Entity Extraction Module using Robust Natural Language Tokenization, Regular Expressions, and Slot Parsing.
Extracts product, quantity, unit, amount, supplier, customer, category, and correction targets
from flexible, natural conversational speech.
"""
import re
from typing import Dict, Any, Optional, List, Tuple
from config import Config

# Spoken number word mapping
WORD_NUMBERS = {
    'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
    'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
    'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
    'eighty': 80, 'ninety': 90, 'hundred': 100, 'thousand': 1000, 'lakh': 100000,
    'half': 0.5, 'quarter': 0.25, 'a': 1, 'an': 1
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

# Known common shop products for fallback
COMMON_PRODUCTS = [
    "basmati rice", "rice", "brown sugar", "sugar", "sunflower oil", "mustard oil",
    "cooking oil", "oil", "tea powder", "tea", "coffee powder", "coffee",
    "wheat flour", "atta", "maida", "paneer", "cheese", "butter", "milk",
    "bath soap", "soap", "washing powder", "detergent", "black salt", "salt",
    "toor dal", "moong dal", "chana dal", "dal", "pulses", "shampoo", "toothpaste",
    "biscuits", "biscuit", "bread", "eggs", "egg", "matchbox", "noodles", "maggie",
    "chips", "cold drink", "turmeric", "chilli powder", "coriander powder", "garam masala",
    "spices"
]

NON_PARTY_WORDS = {
    'me', 'us', 'him', 'her', 'them', 'my', 'the shop', 'shop', 'supplier',
    'customer', 'vendor', 'market', 'wholesale', 'today', 'yesterday', 'now',
    'stock', 'store', 'paid', 'cost', 'bought', 'sold', 'item', 'items', 'goods',
    'i', 'we', 'you', 'he', 'she', 'they', 'it'
}

def parse_word_number(text: str) -> Optional[float]:
    """Parse text that may contain spoken number words (e.g. 'twenty five', 'three hundred', 'twenty thousand')."""
    cleaned = text.strip().lower().rstrip('.!?;:').replace('-', ' ')
    if not cleaned:
        return None

    # Handle special fractions
    if cleaned in ('one and a half', '1 and a half', '1.5'):
        return 1.5
    if cleaned in ('two and a half', '2 and a half', '2.5'):
        return 2.5
    if cleaned in ('half', 'half a'):
        return 0.5
    if cleaned in ('quarter', 'a quarter'):
        return 0.25

    # Direct single word match
    if cleaned in WORD_NUMBERS:
        return float(WORD_NUMBERS[cleaned])

    # Try standard digit parsing
    try:
        return float(cleaned.replace(',', ''))
    except ValueError:
        pass

    words = [w for w in cleaned.split() if w != 'and']
    total = 0.0
    current = 0.0
    found_any = False

    for w in words:
        w_clean = w.replace(',', '')
        val = None
        try:
            val = float(w_clean)
        except ValueError:
            if w in WORD_NUMBERS:
                val = float(WORD_NUMBERS[w])

        if val is not None:
            found_any = True
            if val in (1000, 100000):
                current = (current if current > 0 else 1) * val
                total += current
                current = 0.0
            elif val == 100:
                current = (current if current > 0 else 1) * val
            else:
                current += val

    total += current
    return total if found_any and total > 0 else None

def extract_amount(text: str) -> Optional[float]:
    """
    Extract transaction money amount from natural speech.
    Supports:
    - '₹800', 'rs 800', 'rs. 800', 'inr 800', '800 rupees', '800 rs', '20,000'
    - 'for 800', 'at 800', 'paid 800', 'paid him 800', 'paid Arun 250', 'cost 800', 'cost me 250', 'worth 500'
    - Spoken numbers: 'three hundred', 'five hundred rupees', 'twenty thousand'
    - Comma numbers: '20,000', '1,500'
    """
    cleaned = text.strip().rstrip('.!?;:')

    # Pattern 1: Currency symbols / prefixes: ₹800, ₹ 20,000, rs 800, rs. 800, inr 800
    m = re.search(r'(?:₹|rs\.?|inr)\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)', cleaned, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(',', ''))
        except ValueError:
            pass

    # Pattern 2: Suffix currency: 800 rupees, 20,000 rs, 800 bucks, 250 rupee
    m = re.search(r'\b([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)\s*(?:rupees|rupee|rs|rps|inr|bucks)\b', cleaned, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(',', ''))
        except ValueError:
            pass

    # Pattern 3: Prepositions with optional pronoun/name and price:
    # 'for 250', 'for 20,000', 'paid 250', 'paid him 250', 'paid Arun 250', 'cost 250', 'cost me 250', 'worth 500'
    m = re.search(r'\b(?:for|at|paid(?:\s+[a-z]+)?|cost(?:\s+[a-z]+)?|worth|price|rate|amount\s+(?:is|of)?)\s+([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)\b', cleaned, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(',', ''))
        except ValueError:
            pass

    # Pattern 4: Spoken words with currency: "five hundred rupees", "twenty thousand rs", "three hundred rupees"
    m = re.search(r'\b((?:[a-z\-]+\s*){1,4})\s*(?:rupees|rupee|rs|inr|bucks)\b', cleaned, re.IGNORECASE)
    if m:
        num = parse_word_number(m.group(1))
        if num is not None and num > 0:
            return num

    # Pattern 5: Spoken words after price trigger: "paid five hundred", "cost me three hundred", "for two thousand"
    m = re.search(r'\b(?:for|at|worth|paid(?:\s+[a-z]+)?|cost(?:\s+[a-z]+)?|amount\s+(?:is|of)?)\s+([a-z\s\-]+?)(?:\s*(?:rupees|rupee|rs|inr|bucks|\.|$|,))', cleaned, re.IGNORECASE)
    if m:
        num = parse_word_number(m.group(1))
        if num is not None and num > 0:
            return num

    # Pattern 6: Standalone number at end of comma-separated or speech list (e.g., "Got rice from Arun, five kilos, 300")
    m = re.search(r'(?:,\s*|\s+)([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)\s*$', cleaned)
    if m:
        try:
            val = float(m.group(1).replace(',', ''))
            after = cleaned[m.end(1):].strip()
            unit_words = ('kg', 'kgs', 'kilo', 'kilos', 'gram', 'grams', 'g', 'gm', 'packet', 'packets', 'pkt', 'box', 'boxes', 'piece', 'pieces', 'pcs', 'liter', 'liters', 'litre', 'litres', 'l', 'ml')
            if not any(after.lower().startswith(u) for u in unit_words):
                return val
        except ValueError:
            pass

    # Pattern 7: Trailing spoken number at end of phrase (e.g. "Got rice from Arun, five kilos, three hundred")
    m = re.search(r'(?:,\s*|\s+)([a-z\-]+(?:\s+[a-z\-]+)?)\s*$', cleaned, re.IGNORECASE)
    if m:
        cand = m.group(1).strip().lower()
        if cand not in ('rice', 'sugar', 'oil', 'tea', 'atta', 'dal', 'milk', 'arun', 'kumar', 'rahul', 'yes', 'no', 'confirm', 'cancel'):
            num = parse_word_number(cand)
            if num is not None and num >= 10:
                return num

    # Pattern 8: Exact numeric input in slot answering: "250" or "₹250"
    m = re.match(r'^\s*(?:₹|rs\.?)?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)\s*$', cleaned, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(',', ''))
        except ValueError:
            pass

    return None

def extract_quantity_and_unit(text: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Extract quantity number and unit of measurement from natural speech.
    Supports:
    - '500 grams', '500g', '500 gm', '5 kg', '20 kgs', '5 packets', '10.5 liters', '10 pcs'
    - 'five hundred grams', 'five kilos', '500 kilos', 'twenty kg', 'five packets', 'half kilo'
    - '1/2 kg', '1.5 kg', '2.5 liters'
    """
    cleaned = text.lower().strip().rstrip('.!?;:')
    unit_regex = r'(kg|kgs|kilograms?|kilos?|g|grams?|gm|gms|packets?|pkts?|packs?|boxes?|pieces?|pcs|pc|items?|liters?|litres?|ltrs?|l|ml|milliliters?|bottles?|cans?|bags?|sacks?|cartons?|dozens?)'

    # Pattern 1: Fractions like "1/2 kg", "1/4 kg"
    m = re.search(rf'(\d+/\d+)\s*{unit_regex}\b', cleaned, re.IGNORECASE)
    if m:
        raw_frac = m.group(1)
        raw_unit = m.group(2).lower()
        num, denom = raw_frac.split('/')
        qty = float(num) / float(denom)
        unit = UNIT_MAP.get(raw_unit, raw_unit)
        return qty, unit

    # Pattern 2: Digit + Unit (e.g. "500 grams", "500g", "5 kg", "20 kgs", "5 packets")
    m = re.search(rf'([0-9]+(?:\.[0-9]+)?)\s*{unit_regex}\b', cleaned, re.IGNORECASE)
    if m:
        raw_qty = m.group(1)
        raw_unit = m.group(2).lower()
        qty = float(raw_qty)
        unit = UNIT_MAP.get(raw_unit, raw_unit)
        return qty, unit

    # Pattern 3: Spoken number words + Unit (e.g. "five hundred grams", "five kilos", "500 kilos", "twenty kg", "half kilo")
    m = re.search(rf'\b((?:[a-z\-]+\s*){{1,3}})\s+{unit_regex}\b', cleaned, re.IGNORECASE)
    if m:
        word_num = m.group(1).strip()
        raw_unit = m.group(2).lower()
        qty = parse_word_number(word_num)
        if qty is not None:
            unit = UNIT_MAP.get(raw_unit, raw_unit)
            return qty, unit

    # Pattern 4: Standalone number without unit in slot filling (e.g. "20" or "5")
    if not re.search(r'(rupee|rs|₹|inr|bucks|cost|paid|worth)', cleaned):
        m = re.search(r'^\s*([0-9]+(?:\.[0-9]+)?)\s*$', cleaned)
        if m:
            qty = float(m.group(1))
            return qty, None

        num = parse_word_number(cleaned)
        if num is not None:
            return num, None

    return None, None

def extract_party_name(text: str, intent: str = "PURCHASE") -> Optional[str]:
    """
    Extract supplier or customer name from natural language.
    Handles:
    - Prepositional: 'from Arun', 'to Rahul', 'from Ramesh Agencies'
    - Subject as Supplier: 'Arun supplied me...', 'Arun gave me...', 'Arun sold me...', 'Arun brought...', 'came from Arun'
    - Subject as Customer: 'Arun bought...', 'Arun took...', 'Arun ordered...', 'Arun purchased...'
    """
    cleaned = text.strip()

    # Pattern 1: Supplier - "from <Name>" (e.g. "bought from Arun", "got sugar from Arun, 500 grams", "came from Arun.")
    m = re.search(r'\bfrom\s+([A-Za-z\s\.\'\-]+?)(?=\s+(?:for|at|worth|on|paid|cost|amount|rs|₹|\d)|[,;.!?]|$)', cleaned, re.IGNORECASE)
    if m:
        name = m.group(1).strip().strip(".,;:!?")
        if name and name.lower() not in NON_PARTY_WORDS:
            return name.title()

    # Pattern 2: Supplier as Subject (e.g. "Arun supplied me...", "Arun gave me...", "Arun sold me...", "Arun brought...")
    m = re.search(r'(?:^|today\s+|yesterday\s+)([A-Za-z]+)\s+(?:supplied|gave(?:\s+me)?|sold(?:\s+me)?|brought|delivered|provided)', cleaned, re.IGNORECASE)
    if m:
        name = m.group(1).strip().strip(".,;:!?")
        if name and name.lower() not in NON_PARTY_WORDS:
            return name.title()

    # Pattern 3: Customer - "to <Name>" or "for customer <Name>" (e.g. "sold to Rahul", "given to Priya")
    m = re.search(r'\b(?:to|for\s+customer)\s+([A-Za-z\s\.\'\-]+?)(?=\s+(?:for|at|worth|on|paid|cost|amount|rs|₹|\d)|[,;.!?]|$)', cleaned, re.IGNORECASE)
    if m:
        name = m.group(1).strip().strip(".,;:!?")
        if name and name.lower() not in NON_PARTY_WORDS:
            return name.title()

    # Pattern 4: Customer as Subject (e.g. "Arun bought 500 rupees worth of sugar", "Rahul took 2 kg rice", "Priya ordered...")
    m = re.search(r'(?:^|today\s+|yesterday\s+)([A-Za-z]+)\s+(?:bought|purchased|took|ordered|got|wanted|collected)', cleaned, re.IGNORECASE)
    if m:
        name = m.group(1).strip().strip(".,;:!?")
        if name and name.lower() not in NON_PARTY_WORDS and name.lower() not in ('i', 'we', 'he', 'she', 'they'):
            return name.title()

    return None

def extract_expense_category(text: str) -> Tuple[str, Optional[str]]:
    """
    Extract category and description for an expense.
    E.g. 'paid 500 for shop electricity bill' -> ('Electricity Bill', 'Electricity')
    """
    cleaned = text.lower()
    for keyword, category_name in EXPENSE_CATEGORIES.items():
        if re.search(rf'\b{keyword}\b', cleaned):
            return category_name, keyword.title()

    return "Miscellaneous Expense", "Shop Expense"

def extract_product_name(text: str, known_products: List[str] = None) -> Optional[str]:
    """
    Extract the product name from natural language.
    Combines active database catalog matching with syntactic structural extraction.
    Handles variations:
    - "500 grams of sugar", "500 grams sugar", "5 kg rice", "sugar from Arun"
    - "Arun supplied me 500 kilos of rice", "Arun sold me sugar"
    - "Got rice from Arun, five kilos, three hundred"
    - "Sugar from Arun, 500 rupees"
    """
    cleaned = text.strip().rstrip('.!?;:')
    lower = cleaned.lower()

    # 1. Match against known catalog and common product list (longest match first)
    search_list = sorted((known_products or []) + COMMON_PRODUCTS, key=len, reverse=True)
    for p in search_list:
        p_clean = p.lower()
        pattern = rf'\b{re.escape(p_clean)}\b'
        if re.search(pattern, lower):
            return p.title()

    # 2. Syntactic Structural Extraction:
    unit_words = r'(?:kg|kgs|kilograms?|kilos?|g|grams?|gm|gms|packets?|pkts?|packs?|boxes?|pieces?|pcs|pc|items?|liters?|litres?|ltrs?|l|ml|bottles?|cans?|bags?|sacks?|cartons?|dozens?)'
    verb_words = r'(?:bought|buy|purchased|purchase|procured|got|received|supplied|sold|sell|sale|order|ordered|stock\s+of|stock|check|restocked)'

    patterns = [
        # Pattern A: Quantity + Unit + [of] + Product -> "500 grams of sugar", "20 kg rice", "5 packets biscuits"
        rf'{unit_words}\s+(?:of\s+)?([a-zA-Z\s]{{2,30}}?)(?=\s+(?:from|to|for|at|worth|paid|cost|amount|rs|₹|\d)|[,;.!?]|$)',
        # Pattern B: Verb + [me/us] + Product -> "bought sugar", "got rice from Arun", "Arun supplied me rice", "Arun sold me sugar"
        rf'\b{verb_words}(?:\s+(?:me|us|him|her|them))?\s+(?:of\s+)?([a-zA-Z\s]{{2,30}}?)(?=\s+(?:from|to|for|at|worth|paid|cost|amount|rs|₹|\d)|[,;.!?]|$)',
        # Pattern C: Fronted product -> "Sugar from Arun, 500 rupees"
        rf'^\s*([a-zA-Z\s]{{2,30}}?)(?=\s+(?:from|to|for|at|worth|paid|cost|amount|rs|₹|\d|,))',
        # Pattern D: Standalone product slot response -> "rice" or "basmati rice"
        r'^\s*([a-zA-Z\s]{2,30})\s*$'
    ]

    for pat in patterns:
        m = re.search(pat, cleaned, re.IGNORECASE)
        if m:
            cand = m.group(1).strip().strip(".,;:!?")
            cand_words = [w for w in cand.split() if w.lower() not in ('the', 'a', 'an', 'some', 'of', 'for', 'from', 'to', 'today', 'and', 'worth', 'me', 'us', 'him', 'her')]
            if cand_words:
                cand_clean = " ".join(cand_words).strip()
                if len(cand_clean) >= 2 and cand_clean.lower() not in NON_PARTY_WORDS:
                    return cand_clean.title()

    return None

def extract_correction_target(text: str) -> Dict[str, Any]:
    """
    Extract target slot and new value from natural language correction commands.
    Examples:
    - 'Actually change the quantity to 15 kg'
    - 'Change amount to 750 rupees'
    - 'Change product to sugar'
    - 'Make it 10 packets'
    - 'No, price is 500'
    """
    cleaned = text.lower().strip().rstrip('.!?;:')
    result = {"target_slot": None, "value": None, "unit": None}

    # 1. Quantity correction
    if re.search(r'\b(quantity|qty|count|number of|packets|kg|liters|pcs|boxes|grams)\b', cleaned) or re.search(r'\b(to|make it)\s+\d+\s*(kg|packets|pcs|liters|boxes|g|grams)?', cleaned):
        qty, unit = extract_quantity_and_unit(cleaned)
        if qty is not None:
            result["target_slot"] = "quantity"
            result["value"] = qty
            result["unit"] = unit
            return result

    # 2. Amount / Price correction
    if re.search(r'\b(amount|price|cost|rate|rupees|rs|₹)\b', cleaned):
        amt = extract_amount(cleaned)
        if amt is not None:
            result["target_slot"] = "amount"
            result["value"] = amt
            return result

    # 3. Product correction
    if re.search(r'\b(product|item|change product to|make product)\b', cleaned):
        prod = extract_product_name(cleaned)
        if prod:
            result["target_slot"] = "product"
            result["value"] = prod
            return result

    # 4. Supplier / Customer correction
    if re.search(r'\b(supplier|vendor|from|customer|to)\b', cleaned):
        party = extract_party_name(cleaned)
        if party:
            result["target_slot"] = "party_name"
            result["value"] = party
            return result

    # Fallback
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
