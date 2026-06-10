import sqlite3
import re
import os
from contextlib import contextmanager
from app.config import DATABASE_URL

# Determine DB type
IS_POSTGRES = DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")

class RowDict(dict):
    """A dictionary that also supports index-based lookup to match sqlite3.Row and tuples."""
    def __init__(self, d, tup):
        super().__init__(d)
        self.tup = tup

    def __getitem__(self, key):
        if isinstance(key, int):
            return self.tup[key]
        return super().__getitem__(key)

class DictCursorWrapper:
    """A cursor wrapper that translates query syntax and implements dictionary rows."""
    def __init__(self, cursor, is_postgres):
        self.cursor = cursor
        self.is_postgres = is_postgres
        self._lastrowid = None

    def execute(self, query, params=None):
        if params is None:
            params = ()
            
        if self.is_postgres:
            # Replace SQLite "?" placeholders with PostgreSQL "%s" placeholders
            query = query.replace('?', '%s')
            
            # Translate SQLite key & index syntax to Postgres
            if "CREATE TABLE" in query.upper():
                query = query.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
                query = query.replace("TEXT UNIQUE", "VARCHAR(255) UNIQUE")
                
            query_upper = query.upper().strip()
            if query_upper.startswith("INSERT ") and " RETURNING " not in query_upper:
                query = query.rstrip().rstrip(';') + " RETURNING id"
                self.cursor.execute(query, params)
                try:
                    row = self.cursor.fetchone()
                    if row:
                        self._lastrowid = row[0]
                except Exception:
                    pass
                return self
                
        self.cursor.execute(query, params)
        if not self.is_postgres:
            self._lastrowid = self.cursor.lastrowid
        return self

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return RowDict({col[0]: row[idx] for idx, col in enumerate(self.cursor.description)}, row)

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [RowDict({col[0]: row[idx] for idx, col in enumerate(self.cursor.description)}, row) for row in rows]

    def __iter__(self):
        return iter(self.fetchall())

    @property
    def lastrowid(self):
        return self._lastrowid

    def __getattr__(self, name):
        return getattr(self.cursor, name)

class ConnectionWrapper:
    """A connection wrapper that automatically yields DictCursorWrapper."""
    def __init__(self, conn, is_postgres):
        self.conn = conn
        self.is_postgres = is_postgres

    def cursor(self):
        return DictCursorWrapper(self.conn.cursor(), self.is_postgres)

    def execute(self, query, params=None):
        return DictCursorWrapper(self.conn.cursor(), self.is_postgres).execute(query, params)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()

    def __getattr__(self, name):
        return getattr(self.conn, name)

def get_connection():
    if IS_POSTGRES:
        import psycopg2
        # Translate postgres:// to postgresql:// if needed for psycopg2 compatibility
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(url)
        return conn
    else:
        db_path = DATABASE_URL
        if db_path.startswith("sqlite:///"):
            db_path = db_path.replace("sqlite:///", "", 1)
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield ConnectionWrapper(conn, IS_POSTGRES)
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
            groq_key TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # Check if groq_key exists in users table
        has_groq_key = False
        if IS_POSTGRES:
            cursor.execute(
                "SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'groq_key';"
            )
            if cursor.fetchone():
                has_groq_key = True
        else:
            cursor.execute("PRAGMA table_info(users);")
            for row in cursor.fetchall():
                if row[1] == 'groq_key' or row.get('name') == 'groq_key':
                    has_groq_key = True
                    break
                    
        if not has_groq_key:
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN groq_key TEXT;")
                print("Added column groq_key to users table.")
            except Exception as e:
                print(f"Warning: Failed to add groq_key column: {str(e)}")
        
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
            chat_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        
        # Check if chat_json exists in reviews table
        has_chat_json = False
        if IS_POSTGRES:
            cursor.execute(
                "SELECT 1 FROM information_schema.columns WHERE table_name = 'reviews' AND column_name = 'chat_json';"
            )
            if cursor.fetchone():
                has_chat_json = True
        else:
            cursor.execute("PRAGMA table_info(reviews);")
            for row in cursor.fetchall():
                if row[1] == 'chat_json' or row.get('name') == 'chat_json':
                    has_chat_json = True
                    break
                    
        if not has_chat_json:
            try:
                cursor.execute("ALTER TABLE reviews ADD COLUMN chat_json TEXT;")
                print("Added column chat_json to reviews table.")
            except Exception as e:
                print(f"Warning: Failed to add chat_json column: {str(e)}")
        
        print("Database initialized successfully.")

if __name__ == "__main__":
    init_db()
