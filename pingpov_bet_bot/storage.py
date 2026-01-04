import sqlite3
from datetime import datetime

INIT_QUERY = """
CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    tournament_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    prediction TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL UNIQUE,
    username TEXT,
    balance REAL DEFAULT 0,
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS oauth_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user TEXT NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

class AccessToken:
    def __init__(self, user: str, access_token: str, refresh_token: str, expires_at: datetime):
        self.user = user
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at

class Storage:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        cursor.executescript(INIT_QUERY)
        self.conn.commit()

    def add_user(self, telegram_id, username):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username) VALUES (?, ?)",
            (telegram_id, username)
        )
        self.conn.commit()

    def get_user_balance(self, telegram_id):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT balance FROM users WHERE telegram_id = ?",
            (telegram_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else None

    def update_user_balance(self, telegram_id, amount):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE telegram_id = ?",
            (amount, telegram_id)
        )
        self.conn.commit()

    def get_access_token(self) -> AccessToken|None:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM oauth_tokens ORDER BY created_at DESC LIMIT 1"
        )
        result = cursor.fetchone()
        if result:
            return AccessToken(
                user=result[1],
                access_token=result[2],
                refresh_token=result[3],
                expires_at=result[4]
            )
        return None
    
    def save_access_token(self, token: AccessToken):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO oauth_tokens (user, access_token, refresh_token, expires_at) VALUES (?, ?, ?, ?)",
            (token.user, token.access_token, token.refresh_token, token.expires_at)
        )
        self.conn.commit()
