import os
import sys

# Ensure UTF-8 output encoding for Windows terminal
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from flask import Flask, render_template, jsonify
from config import Config
from database.database import init_db, close_db
from database.seed import seed_database
from routes import voice_bp, transaction_bp, dashboard_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Register blueprints
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(voice_bp)
    app.register_blueprint(transaction_bp)

    # Teardown database connection
    app.teardown_appcontext(close_db)

    # Initialize and seed database if not already initialized
    with app.app_context():
        init_db()
        seed_database()

    # Custom Error Handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template('base.html', error="404 - Page Not Found"), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"success": False, "error": "Internal server error", "details": str(e)}), 500

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
    print(f"\n========================================================")
    print(f"  VOICE SHOP MANAGEMENT SYSTEM RUNNING")
    print(f"  Access Web UI at: http://127.0.0.1:{port}/")
    print(f"========================================================\n")
    app.run(host=host, port=port, debug=True)
