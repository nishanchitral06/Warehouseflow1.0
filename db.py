"""
StockBridge - Database Connection Helper
==========================================
This module makes the rest of the app work with EITHER:
  1. Turso (cloud database) - used automatically when TURSO_DATABASE_URL and
     TURSO_AUTH_TOKEN are set (e.g. in Streamlit Cloud's "Secrets"). Data
     persists forever, across app restarts and redeploys.
  2. Local SQLite file (warehouseflow.db) - used automatically as a fallback
     when no Turso credentials are found (e.g. running on your own laptop).

You don't need to change any code elsewhere - just set the two secrets and
this module switches automatically.
"""
import os
import pandas as pd


class DBIntegrityError(Exception):
    """Raised when a unique/primary key constraint is violated, regardless
    of whether we're talking to Turso or local SQLite."""
    pass


def _get_turso_credentials():
    # Try Streamlit secrets first (this is how Streamlit Cloud provides them)
    try:
        import streamlit as st
        if "TURSO_DATABASE_URL" in st.secrets and "TURSO_AUTH_TOKEN" in st.secrets:
            return st.secrets["TURSO_DATABASE_URL"], st.secrets["TURSO_AUTH_TOKEN"]
    except Exception:
        pass
    # Fall back to plain environment variables (useful for scripts / local testing)
    url = os.environ.get("TURSO_DATABASE_URL")
    token = os.environ.get("TURSO_AUTH_TOKEN")
    if url and token:
        return url, token
    return None, None


class DBConnection:
    """
    A small wrapper so the rest of the app can call the same methods
    (execute, read_df, commit, close) no matter which backend is active.
    """

    def __init__(self):
        url, token = _get_turso_credentials()
        self.mode = "turso" if (url and token) else "sqlite"

        if self.mode == "turso":
            import libsql_client
            # Turso's regional hostnames (e.g. aws-ap-south-1.turso.io) can
            # reject the WebSocket/Hrana handshake used by the default
            # libsql:// scheme (WSServerHandshakeError: 400). Using the
            # plain HTTPS scheme instead connects over regular HTTP calls
            # and avoids that bug entirely - same database, same data.
            https_url = url.replace("libsql://", "https://")
            self.client = libsql_client.create_client_sync(url=https_url, auth_token=token)
        else:
            import sqlite3
            self.conn = sqlite3.connect("warehouseflow.db")

    def execute(self, sql, params=None):
        params = params or []
        try:
            if self.mode == "turso":
                self.client.execute(sql, params)
            else:
                self.conn.execute(sql, params)
        except Exception as e:
            msg = str(e).upper()
            if "UNIQUE" in msg or "PRIMARY KEY" in msg or "CONSTRAINT" in msg:
                raise DBIntegrityError(str(e))
            raise

    def executescript(self, script):
        """Only used for schema setup (multiple CREATE TABLE statements)."""
        if self.mode == "turso":
            for stmt in [s.strip() for s in script.split(";") if s.strip()]:
                self.client.execute(stmt)
        else:
            self.conn.executescript(script)

    def executemany(self, sql, rows):
        if self.mode == "turso":
            for row in rows:
                self.client.execute(sql, list(row))
        else:
            self.conn.executemany(sql, rows)

    def read_df(self, sql, params=None):
        params = params or []
        if self.mode == "turso":
            rs = self.client.execute(sql, params)
            return pd.DataFrame([list(r) for r in rs.rows], columns=rs.columns)
        else:
            return pd.read_sql(sql, self.conn, params=params)

    def commit(self):
        if self.mode == "sqlite":
            self.conn.commit()
        # Turso's client commits each statement over HTTP automatically -
        # nothing extra needed here.

    def close(self):
        if self.mode == "turso":
            self.client.close()
        else:
            self.conn.close()


def get_conn():
    return DBConnection()
