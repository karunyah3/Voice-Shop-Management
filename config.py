import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Base configuration for Voice Shop Management application."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'voice-shop-mgmt-secret-2026')
    DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(BASE_DIR, 'database', 'shop.db'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Shop Settings
    CURRENCY_SYMBOL = "₹"
    CURRENCY_CODE = "INR"
    LOW_STOCK_THRESHOLD = 5
    
    # NLP & Confidence Thresholds
    CONFIDENCE_HIGH_THRESHOLD = 0.80
    CONFIDENCE_MEDIUM_THRESHOLD = 0.55
    
    # Default units
    SUPPORTED_UNITS = [
        'kg', 'kgs', 'kilogram', 'kilograms',
        'g', 'gram', 'grams',
        'packet', 'packets', 'pkt', 'pkts',
        'box', 'boxes',
        'piece', 'pieces', 'pcs',
        'liter', 'liters', 'litre', 'litres', 'l',
        'ml', 'milliliter',
        'bottle', 'bottles',
        'can', 'cans',
        'bag', 'bags',
        'carton', 'cartons',
        'dozen', 'dozens'
    ]

class TestConfig(Config):
    """Testing configuration with temporary database."""
    TESTING = True
    DATABASE_PATH = os.path.join(BASE_DIR, 'database', 'test_shop.db')
