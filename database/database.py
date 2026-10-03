"""
Database connection and lifecycle management for SQLite.
"""
import sqlite3
import os
from flask import g, current_app
from config import Config
from .models import SCHEMA_SQL

def get_db(db_path: str = None) -> sqlite3.Connection:
    """
    Get a database connection.
    If called within a Flask application context, cache connection in Flask `g`.
    Otherwise return a standalone connection.
    """
    if db_path is None:
        if current_app:
            db_path = current_app.config.get('DATABASE_PATH', Config.DATABASE_PATH)
        else:
            db_path = Config.DATABASE_PATH

    # Ensure parent directory exists
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    if current_app:
        if 'db' not in g:
            g.db = sqlite3.connect(db_path)
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db
    else:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

def close_db(e=None):
    """Close the database connection if open in Flask context."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db(db_path: str = None):
    """
    Initialize SQLite database tables using the schema definition.
    Safe to call multiple times (IF NOT EXISTS used).
    """
    if db_path is None:
        if current_app:
            db_path = current_app.config.get('DATABASE_PATH', Config.DATABASE_PATH)
        else:
            db_path = Config.DATABASE_PATH

    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    with conn:
        conn.executescript(SCHEMA_SQL)
    conn.close()

def query_db(query: str, args=(), one: bool = False, db_path: str = None):
    """
    Helper function to query the database and return dictionary rows.
    """
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute(query, args)
    rv = cur.fetchall()
    cur.close()
    if not current_app:
        conn.close()
    return (rv[0] if rv else None) if one else rv

def execute_db(query: str, args=(), db_path: str = None) -> int:
    """
    Helper function to execute an INSERT/UPDATE/DELETE query and return lastrowid.
    """
    conn = get_db(db_path)
    cur = conn.cursor()
    cur.execute(query, args)
    if not current_app:
        conn.commit()
        last_id = cur.lastrowid
        cur.close()
        conn.close()
        return last_id
    else:
        conn.commit()
        last_id = cur.lastrowid
        cur.close()
        return last_id
