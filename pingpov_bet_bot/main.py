from .storage import Storage
from .api import ChallongeClient
from .conf import TELEGRAM_BOT_TOKEN
from .commands import bet

from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

async def update_token_job(context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.bot_data['storage']
    api_client: ChallongeClient = context.bot_data['api_client']
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

    t = api_client.get_tournaments()[0]
    print(f"Matches for tournament {t.name}:", api_client.get_tournament_matches(t))

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.bot_data['storage'] = storage
    app.bot_data['api_client'] = api_client


    # app.job_queue.run_repeating(
    #     callback=update_token_job,
    #     interval=datetime.timedelta(days=6, hours=23), # a refres is needed every week
    #     first=updated_token.expires_at - datetime.timedelta(hours=1) # the token was just updated, no negative delay
    # )

    app.add_handler(CommandHandler("bet", bet))

    # app.run_polling()