import sqlite3
import os

db_path = "app.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check users table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if cursor.fetchone():
        cursor.execute("SELECT id, username, gemini_key FROM users")
        users = cursor.fetchall()
        print("Users:")
        for u in users:
            key = u[2]
            masked = f"sk-...{key[-4:]}" if key and len(key) > 4 else key
            print(f"  ID: {u[0]}, Username: {u[1]}, Gemini Key: {masked}")
    else:
        print("Table 'users' does not exist")
        
    # Check reviews table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reviews'")
    if cursor.fetchone():
        cursor.execute("SELECT id, user_id, title, created_at FROM reviews")
        reviews = cursor.fetchall()
        print("\nReviews:")
        for r in reviews:
            print(f"  ID: {r[0]}, User ID: {r[1]}, Title: {r[2]}, Created: {r[3]}")
    else:
        print("Table 'reviews' does not exist")
        
    conn.close()
else:
    print(f"DB not found at {os.path.abspath(db_path)}")
