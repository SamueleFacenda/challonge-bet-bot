import dotenv
import os
dotenv.load_dotenv()  # take environment variables from .env.file


DB_PATH = os.getenv("DB_PATH", "db.sqlite3")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHALLONGE_CLIENT_ID = os.getenv("CHALLONGE_CLIENT_ID", "")
CHALLONGE_CLIENT_SECRET = os.getenv("CHALLONGE_CLIENT_SECRET", "")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is not set in environment variables.")
if not CHALLONGE_CLIENT_ID:
    raise ValueError("CHALLONGE_CLIENT_ID is not set in environment variables.")
if not CHALLONGE_CLIENT_SECRET:
    raise ValueError("CHALLONGE_CLIENT_SECRET is not set in environment variables.")