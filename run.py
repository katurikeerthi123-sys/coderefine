import sys
import os

# Ensure the root of the project is in the Python path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.append(BASE_DIR)

from app.main import run_server

if __name__ == "__main__":
    print("=" * 60)
    print("  CodeRefine Generative AI Code Review & Optimization Engine  ")
    print("  Running with zero-dependency pure Python HTTP architecture  ")
    print("=" * 60)
    print("Web User Interface: http://127.0.0.1:8000/")
    print("Local SQLite file:  app.db")
    print("=" * 60)
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    run_server(host=host, port=port)
