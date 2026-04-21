import os
import json
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
            raise RuntimeError("psycopg is not installed. Add psycopg[binary] to requirements.txt")
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
        text_unique = ""  # handled with explicit UNIQUE constraints below

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
                photo TEXT,
                UNIQUE(team, number)
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
                score TEXT,
                UNIQUE(team, match_id)
            )
        """)

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS attendance_daily (
                id {id_sql},
                team TEXT NOT NULL,
                date TEXT NOT NULL,
                player_number TEXT NOT NULL,
                present INTEGER NOT NULL,
                UNIQUE(team, date, player_number)
            )
        """)

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS attendance_monthly (
                id {id_sql},
                team TEXT NOT NULL,
                month_label TEXT NOT NULL,
                player_number TEXT NOT NULL,
                day INTEGER NOT NULL,
                status TEXT NOT NULL,
                UNIQUE(team, month_label, player_number, day)
            )
        """)

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS practice_schedule (
                id {id_sql},
                team TEXT NOT NULL,
                date TEXT NOT NULL,
                main TEXT,
                secondary TEXT,
                note_main_start TEXT,
                note_main_end TEXT,
                note_secondary_start TEXT,
                note_secondary_end TEXT,
                UNIQUE(team, date)
            )
        """)

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS microcycles (
                id {id_sql},
                team TEXT NOT NULL,
                from_date TEXT NOT NULL,
                meta_microcycle TEXT,
                meta_from TEXT,
                meta_to TEXT,
                meta_week TEXT,
                meta_period TEXT,
                content_json TEXT NOT NULL,
                UNIQUE(team, from_date)
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


def execute_many(statements):
    with get_connection() as conn:
        cur = conn.cursor()
        for query, params in statements:
            cur.execute(query, params)
        conn.commit()


def json_dumps(data):
    return json.dumps(data, ensure_ascii=False)


def json_loads(text):
    return json.loads(text) if text else {}
