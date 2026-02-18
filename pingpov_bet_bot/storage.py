import sqlite3
from datetime import datetime
from dataclasses import dataclass

INIT_QUERY = """
CREATE TABLE IF NOT EXISTS bets (
    user_id INTEGER NOT NULL,
    challonge_tournament_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    prediction TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bets_tournament 
ON bets(challonge_tournament_id);

CREATE TABLE IF NOT EXISTS match_bets (
    user_id INTEGER NOT NULL,
    challonge_tournament_id INTEGER NOT NULL,
    challonge_match_id INTEGER NOT NULL,
    challonge_winner_id INTEGER NOT NULL,
    challonge_loser_id INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_match_bets_tournament 
ON match_bets(challonge_tournament_id);

CREATE TABLE IF NOT EXISTS challonge_tournaments (
    challonge_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    bets_open BOOLEAN NOT NULL,
    started BOOLEAN NOT NULL,
    finished BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS challonge_matches (
    challonge_id INTEGER PRIMARY KEY,
    tournament_id INTEGER NOT NULL,
    player1_id INTEGER,
    player1_match_id INTEGER,
    player1_is_match_loser BOOLEAN,
    player2_id INTEGER,
    player2_match_id INTEGER,
    player2_is_match_loser BOOLEAN,
    winner_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_matches_tournament 
ON challonge_matches(tournament_id);

CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    username TEXT,
    balance REAL DEFAULT 0
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


@dataclass
class AccessToken:
    user: str
    access_token: str
    refresh_token: str
    expires_at: datetime

@dataclass
class User:
    telegram_id: int
    username: str
    balance: float

@dataclass
class Bet:
    user_id: int
    challonge_tournament_id: int
    amount: float
    prediction: str
    timestamp: datetime

@dataclass
class MatchBet:
    user_id: int
    challonge_tournament_id: int
    challonge_match_id: int
    challonge_winner_id: int
    challonge_loser_id: int # kept for easier access

@dataclass(unsafe_hash=True)
class ChallongeTournament:
    challonge_id: int
    name: str
    bets_open: bool
    started: bool
    finished: bool

@dataclass
class ChallongeMatch:
    challonge_id: int
    tournament_id: int
    player1_id: int|None
    player1_match_id: int|None
    player1_is_match_loser: bool|None
    player2_id: int|None
    player2_match_id: int|None
    player2_is_match_loser: bool|None
    winner_id: int|None

class Storage:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.init_db()

    def init_db(self):
        cursor = self.conn.cursor()
        cursor.executescript(INIT_QUERY)
        self.conn.commit()

    def get_user(self, telegram_id: int) -> User|None:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        result = cursor.fetchone()
        if result:
            return User(
                telegram_id=result[0],
                username=result[1],
                balance=result[2]
            )
        return None
    
    def add_user(self, user: User):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username, balance) VALUES (?, ?, ?)",
            (user.telegram_id, user.username, user.balance)
        )
        self.conn.commit()

    def update_user(self, user: User):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE users SET balance = ? WHERE telegram_id = ?",
            (user.balance, user.telegram_id)
        )
        self.conn.commit()

    def get_bets_for_tournament(self, challonge_tournament_id: int) -> list[Bet]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM bets WHERE challonge_tournament_id = ?", (challonge_tournament_id,)
        )
        results = cursor.fetchall()
        return [
            Bet(
                user_id=row[0],
                challonge_tournament_id=row[1],
                amount=row[2],
                prediction=row[3],
                timestamp=datetime.fromisoformat(row[4])
            ) for row in results
        ]
    
    def get_match_bets_for_tournament(self, challonge_tournament_id: int) -> list[MatchBet]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM match_bets WHERE challonge_tournament_id = ?", (challonge_tournament_id,)
        )
        results = cursor.fetchall()
        return [
            MatchBet(
                user_id=row[0],
                challonge_tournament_id=row[1],
                challonge_match_id=row[2],
                challonge_winner_id=row[3],
                challonge_loser_id=row[4]
            ) for row in results
        ]
    
    def add_bet(self, bet: Bet):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO bets (user_id, challonge_tournament_id, amount, prediction) VALUES (?, ?, ?, ?)",
            (bet.user_id, bet.challonge_tournament_id, bet.amount, bet.prediction)
        )
        self.conn.commit()

    def add_match_bets(self, match_bets: list[MatchBet]):
        cursor = self.conn.cursor()
        cursor.executemany(
            "INSERT INTO match_bets (user_id, challonge_tournament_id, challonge_match_id, challonge_winner_id, challonge_loser_id) VALUES (?, ?, ?, ?, ?)",
            [(mb.user_id, mb.challonge_tournament_id, mb.challonge_match_id, mb.challonge_winner_id, mb.challonge_loser_id) for mb in match_bets]
        )
        self.conn.commit()

    def get_challonge_tournament(self, challonge_id: int) -> ChallongeTournament|None:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM challonge_tournaments WHERE challonge_id = ?", (challonge_id,)
        )
        result = cursor.fetchone()
        if result:
            return ChallongeTournament(
                challonge_id=result[0],
                name=result[1],
                bets_open=bool(result[2]),
                started=bool(result[3]),
                finished=bool(result[4])
            )
        return None
    
    def get_challonge_matches_for_tournament(self, tournament_id: int) -> list[ChallongeMatch]:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM challonge_matches WHERE tournament_id = ?", (tournament_id,)
        )
        results = cursor.fetchall()
        return [
            ChallongeMatch(
                challonge_id=row[0],
                tournament_id=row[1],
                player1_id=row[2],
                player1_match_id=row[3],
                player1_is_match_loser=bool(row[4]) if row[4] is not None else None,
                player2_id=row[5],
                player2_match_id=row[6],
                player2_is_match_loser=bool(row[7]) if row[7] is not None else None,
                winner_id=row[8]
            ) for row in results
        ]
    
    def add_challonge_tournament(self, tournament: ChallongeTournament):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO challonge_tournaments (challonge_id, name, bets_open, started, finished) VALUES (?, ?, ?, ?, ?)",
            (tournament.challonge_id, tournament.name, int(tournament.bets_open), int(tournament.started), int(tournament.finished))
        )
        self.conn.commit()

    def update_challonge_tournament(self, tournament: ChallongeTournament):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE challonge_tournaments SET name = ?, bets_open = ?, started = ?, finished = ? WHERE challonge_id = ?",
            (tournament.name, int(tournament.bets_open), int(tournament.started), int(tournament.finished), tournament.challonge_id)
        )
        self.conn.commit()

    def add_challonge_matches(self, matches: list[ChallongeMatch]):
        cursor = self.conn.cursor()
        cursor.executemany(
            "INSERT OR REPLACE INTO challonge_matches (challonge_id, tournament_id, player1_id, player1_match_id, player1_is_match_loser, player2_id, player2_match_id, player2_is_match_loser, winner_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(m.challonge_id, m.tournament_id, m.player1_id, m.player1_match_id, int(m.player1_is_match_loser) if m.player1_is_match_loser is not None else None, m.player2_id, m.player2_match_id, int(m.player2_is_match_loser) if m.player2_is_match_loser is not None else None, m.winner_id) for m in matches]
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
