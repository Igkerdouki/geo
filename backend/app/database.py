import os
from app.config import BACKEND_ROOT  # load backend/.env before resolving connections

DB_CONFIG = {
    'dbname': os.environ.get('DB_NAME', 'geo'),
    'user': os.environ.get('DB_USER', os.environ.get('USER', 'ioannagkerdouki')),
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': os.environ.get('DB_PORT', '5432'),
}

def get_connection():
    import psycopg2
    from psycopg2.extras import RealDictCursor
    url = os.getenv('PUR_DATABASE_URL')
    if url:
        return psycopg2.connect(url, cursor_factory=RealDictCursor, connect_timeout=8)
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor, connect_timeout=8)


def get_pur_connection():
    """Monthly PUR import may share the Neon database used for evidence storage."""
    import psycopg2
    from psycopg2.extras import RealDictCursor
    url = os.getenv('PUR_DATABASE_URL') or os.getenv('DATABASE_URL')
    if not url:
        return get_connection()
    return psycopg2.connect(url, cursor_factory=RealDictCursor, connect_timeout=8)
