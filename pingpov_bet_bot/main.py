from .storage import Storage
from .api import ChallongeClient
from .conf import TELEGRAM_BOT_TOKEN
from .commands import bet

from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import BotCommand

import datetime

async def update_token_job(context: ContextTypes.DEFAULT_TYPE, storage: Storage, api_client: ChallongeClient):
    old = storage.get_access_token()
    assert old is not None, "No access token found in storage."
    updated = api_client.refresh_token(old)
    # storage.save_access_token(updated)
    print("Access token updated in job.")

def main():
    storage = Storage("db.sqlite3")
    api_client = ChallongeClient()

    access_token = storage.get_access_token()
    updated_token = api_client.authenticate(access_token)

    # storage.save_access_token(updated_token)
    print("Access token updated.")

    print("Logged in as:", api_client.get_user())
    print("Available communities:", api_client.get_communities())
    print("Available tournaments:", api_client.get_tournaments())

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # app.job_queue.run_repeating(
    #     callback=lambda context: update_token_job(context, storage, api_client),
    #     interval=datetime.timedelta(days=6, hours=23), # a refres is needed every week
    #     first=updated_token.expires_at - datetime.timedelta(hours=1) # the token was just updated, no negative delay
    # )

    app.add_handler(CommandHandler("bet", bet))

    # app.run_polling()