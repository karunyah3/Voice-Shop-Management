"""
Data models and database schema definitions for Voice Shop Management.
"""
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
import json
from datetime import datetime

# Database Schema SQL definitions
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL COLLATE NOCASE,
    category TEXT NOT NULL DEFAULT 'General',
    unit TEXT NOT NULL DEFAULT 'pcs',
    current_stock REAL NOT NULL DEFAULT 0,
    cost_price REAL NOT NULL DEFAULT 0,
    selling_price REAL NOT NULL DEFAULT 0,
    min_stock_alert REAL NOT NULL DEFAULT 5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('PURCHASE', 'SALE', 'EXPENSE')),
    product_id INTEGER,
    product_name TEXT,
    quantity REAL,
    unit TEXT,
    unit_price REAL,
    total_amount REAL NOT NULL,
    party_name TEXT,
    category TEXT,
    profit REAL DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS pending_contexts (
    session_id TEXT PRIMARY KEY,
    state TEXT NOT NULL DEFAULT 'IDLE',
    intent TEXT,
    product TEXT,
    product_id INTEGER,
    quantity REAL,
    unit TEXT,
    amount REAL,
    party_name TEXT,
    category TEXT,
    missing_slots TEXT DEFAULT '[]',
    last_prompt TEXT,
    confidence REAL DEFAULT 0.0,
    confidence_breakdown TEXT DEFAULT '[]',
    raw_input TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type);
CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at);
"""

@dataclass
class Product:
    id: Optional[int]
    name: str
    category: str = "General"
    unit: str = "pcs"
    current_stock: float = 0.0
    cost_price: float = 0.0
    selling_price: float = 0.0
    min_stock_alert: float = 5.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row) -> "Product":
        if row is None:
            return None
        return cls(
            id=row['id'],
            name=row['name'],
            category=row['category'],
            unit=row['unit'],
            current_stock=float(row['current_stock']),
            cost_price=float(row['cost_price']),
            selling_price=float(row['selling_price']),
            min_stock_alert=float(row['min_stock_alert']),
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

@dataclass
class Transaction:
    id: Optional[int]
    type: str # 'PURCHASE', 'SALE', 'EXPENSE'
    total_amount: float
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    party_name: Optional[str] = None
    category: Optional[str] = None
    profit: float = 0.0
    notes: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row) -> "Transaction":
        if row is None:
            return None
        return cls(
            id=row['id'],
            type=row['type'],
            total_amount=float(row['total_amount']),
            product_id=row['product_id'],
            product_name=row['product_name'],
            quantity=float(row['quantity']) if row['quantity'] is not None else None,
            unit=row['unit'],
            unit_price=float(row['unit_price']) if row['unit_price'] is not None else None,
            party_name=row['party_name'],
            category=row['category'],
            profit=float(row['profit']) if row['profit'] is not None else 0.0,
            notes=row['notes'],
            created_at=row['created_at']
        )

@dataclass
class PendingContext:
    session_id: str
    state: str = "IDLE"
    intent: Optional[str] = None
    product: Optional[str] = None
    product_id: Optional[int] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    amount: Optional[float] = None
    party_name: Optional[str] = None
    category: Optional[str] = None
    missing_slots: Optional[List[str]] = None
    last_prompt: Optional[str] = None
    confidence: float = 0.0
    confidence_breakdown: Optional[List[str]] = None
    raw_input: Optional[str] = None
    updated_at: Optional[str] = None

    def __post_init__(self):
        if self.missing_slots is None:
            self.missing_slots = []
        if self.confidence_breakdown is None:
            self.confidence_breakdown = []

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_row(cls, row) -> "PendingContext":
        if row is None:
            return None
        missing = []
        if row['missing_slots']:
            try:
                missing = json.loads(row['missing_slots'])
            except Exception:
                missing = []
        breakdown = []
        if row['confidence_breakdown']:
            try:
                breakdown = json.loads(row['confidence_breakdown'])
            except Exception:
                breakdown = []

        return cls(
            session_id=row['session_id'],
            state=row['state'],
            intent=row['intent'],
            product=row['product'],
            product_id=row['product_id'],
            quantity=float(row['quantity']) if row['quantity'] is not None else None,
            unit=row['unit'],
            amount=float(row['amount']) if row['amount'] is not None else None,
            party_name=row['party_name'],
            category=row['category'],
            missing_slots=missing,
            last_prompt=row['last_prompt'],
            confidence=float(row['confidence']) if row['confidence'] is not None else 0.0,
            confidence_breakdown=breakdown,
            raw_input=row['raw_input'],
            updated_at=row['updated_at']
        )
