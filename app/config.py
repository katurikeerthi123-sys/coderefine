import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def load_dotenv_manually(filepath: Path):
    """
    Manually parses a simple .env file and updates os.environ.
    This eliminates the python-dotenv package dependency.
    """
    if filepath.exists() and filepath.is_file():
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments or empty lines
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, val = line.split('=', 1)
                        # Remove quotes if present
                        val = val.strip().strip('"').strip("'")
                        os.environ[key.strip()] = val
        except Exception as e:
            print(f"Warning: Failed to load .env manually: {str(e)}")

# Load environment file
load_dotenv_manually(BASE_DIR / ".env")

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/app.db")

# Security configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "coderefine-secret-key-super-secure-12345!")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

# Default Gemini configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_GEMINI_MODEL = os.getenv("DEFAULT_GEMINI_MODEL", "gemini-2.5-flash")
