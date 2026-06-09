import sqlite3
import re
from contextlib import contextmanager
from app.config import DATABASE_URL

# Parse SQLite DB file path from DATABASE_URL
db_path = DATABASE_URL
if db_path.startswith("sqlite:///"):
    db_path = db_path.replace("sqlite:///", "", 1)

def get_connection():
    """Returns a standard sqlite3 connection."""
    conn = sqlite3.connect(db_path)
    # Enable foreign keys support
    conn.execute("PRAGMA foreign_keys = ON;")
    # Return rows as dict-like objects
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def get_db():
    """Context manager for sqlite3 connections to auto-commit and close."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_db():
    """Initializes the database schema if tables do not exist."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            gemini_key TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # Create reviews table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            language TEXT NOT NULL,
            original_code TEXT NOT NULL,
            optimized_code TEXT NOT NULL,
            review_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        
        print("Database initialized successfully.")

if __name__ == "__main__":
    init_db()
