from .storage import Storage
from .api import ChallongeClient
from .conf import TELEGRAM_BOT_TOKEN
from .commands import bet, info, rank, select_tournament, handle_prediction, handle_amount, STATE_AMOUNT, STATE_PREDICTING, STATE_TOURNAMENT
from .outcome_computer import check_finished_tournaments

from telegram import BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, ConversationHandler, MessageHandler, filters

async def update_token_job(context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.bot_data['storage']
    api_client: ChallongeClient = context.bot_data['api_client']
    old = storage.get_access_token()
    assert old is not None, "No access token found in storage."
    updated = api_client.refresh_token(old)
    # storage.save_access_token(updated)
    print("Access token updated in job.")

async def post_init(application):
    await application.bot.set_my_commands([
        BotCommand("bet", "Place a bet on a tournament"),
        BotCommand("info", "Get your current balance and info"),
        BotCommand("rank", "Get the current user rankings"),
    ])

async def bet_not_in_group(update, context):
    bot_username = context.bot.username
    deep_link = f"https://t.me/{bot_username}?start=bet"
    await update.message.reply_text(
        f"⚠️ The /bet command is only available in private chats with the bot.\n\n"
        f"Click here to start: {deep_link}"
    )

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

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    app.bot_data['storage'] = storage
    app.bot_data['api_client'] = api_client

    # app.job_queue.run_repeating(
    #     callback=update_token_job,
    #     interval=datetime.timedelta(days=6, hours=23), # a refres is needed every week
    #     first=updated_token.expires_at - datetime.timedelta(hours=1) # the token was just updated, no negative delay
    # )

    app.job_queue.run_repeating(
        callback=check_finished_tournaments,
        interval=60, # check every minute for finished tournaments
    )

    bet_handler = ConversationHandler(
        entry_points=[CommandHandler("bet", bet, filters=filters.ChatType.PRIVATE)],
        states={
            STATE_TOURNAMENT: [CallbackQueryHandler(select_tournament)],
            STATE_PREDICTING: [CallbackQueryHandler(handle_prediction)],
            STATE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)],
        },
        fallbacks=[]
    )
    app.add_handler(CommandHandler("bet", bet_not_in_group, filters=~filters.ChatType.PRIVATE))

    app.add_handler(bet_handler)
    app.add_handler(CommandHandler("info", info))
    app.add_handler(CommandHandler("rank", rank))

    app.run_polling()