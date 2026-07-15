import os

import psycopg2
import psycopg2.extras

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


class Connection:
    """Thin wrapper so call sites can keep using sqlite3-style conn.execute(...)."""

    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, params=()):
        cur = self._raw.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return cur

    def executescript(self, sql):
        cur = self._raw.cursor()
        cur.execute(sql)
        cur.close()

    def commit(self):
        self._raw.commit()

    def close(self):
        self._raw.close()


def get_connection():
    database_url = os.environ["DATABASE_URL"]
    raw = psycopg2.connect(database_url)
    return Connection(raw)


def init_db():
    conn = get_connection()
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
