import os
import sqlite3
from contextlib import contextmanager

try:
    import psycopg
except ImportError:
    psycopg = None


def using_postgres() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


@contextmanager
def get_connection():
    database_url = os.environ.get("DATABASE_URL")

    if database_url:
        if psycopg is None:
            raise RuntimeError("psycopg is not installed")
        conn = psycopg.connect(database_url)
        try:
            yield conn
        finally:
            conn.close()
    else:
        conn = sqlite3.connect("team_manager.db")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


def init_db():
    with get_connection() as conn:
        cur = conn.cursor()

        id_sql = "SERIAL PRIMARY KEY" if using_postgres() else "INTEGER PRIMARY KEY AUTOINCREMENT"

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS players (
                id {id_sql},
                team TEXT NOT NULL,
                number TEXT NOT NULL,
                name TEXT NOT NULL,
                height TEXT,
                weight TEXT,
                position TEXT,
                dob TEXT,
                comment TEXT,
                photo TEXT
            )
        """)

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS matches (
                id {id_sql},
                team TEXT NOT NULL,
                match_id TEXT NOT NULL,
                opponent TEXT,
                date TEXT,
                time TEXT,
                venue TEXT,
                competition TEXT,
                score TEXT
            )
        """)

        conn.commit()


def fetch_all_dicts(query, params=()):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        result = []
        for row in rows:
            if hasattr(row, "keys"):
                result.append(dict(row))
            else:
                result.append(dict(zip([d[0] for d in cur.description], row)))
        return result


def fetch_one_dict(query, params=()):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        row = cur.fetchone()
        if not row:
            return None
        if hasattr(row, "keys"):
            return dict(row)
        return dict(zip([d[0] for d in cur.description], row))


def execute(query, params=()):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
