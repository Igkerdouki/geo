"""Load server-only credentials once, before importing integrations."""
from pathlib import Path
from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / '.env')
