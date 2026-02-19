from .storage import Storage
from .api import ChallongeClient
from .conf import TELEGRAM_BOT_TOKEN
from .commands import start, help, bet_not_in_group, bet, info, rank, select_tournament, handle_prediction, handle_amount, STATE_AMOUNT, STATE_PREDICTING, STATE_TOURNAMENT
from .outcome_computer import check_finished_tournaments
from .broadcast import track_group_chats

from telegram import BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, ConversationHandler, MessageHandler, filters, ChatMemberHandler

COMMANDS = [
    # command, handler, description, filter
    ("start", start, "Start the bot and get a welcome message", None),
    ("bet", bet_not_in_group, "Place a bet on a tournament", ~filters.ChatType.PRIVATE),
    ("help", help, "Get a list of available commands and how to use them", None),
    ("info", info, "Get your current balance and info", None),
    ("rank", rank, "Get the current user rankings", None),
]

async def update_token_job(context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.bot_data['storage']
    api_client: ChallongeClient = context.bot_data['api_client']
    old = storage.get_access_token()
    assert old is not None, "No access token found in storage."
    updated = api_client.refresh_token(old)
    storage.save_access_token(updated)
    print("Access token updated in job.")

async def post_init(application):
    commands = [BotCommand(command, description) for command, _, description, _ in COMMANDS]
    await application.bot.set_my_commands(commands)

def main():
    storage = Storage("db.sqlite3")
    api_client = ChallongeClient()

    storage.add_chat(-5158183686, True) # TODO remove this, just for testing

    access_token = storage.get_access_token()
    updated_token = api_client.authenticate(access_token)

    # storage.save_access_token(updated_token)
    # print("Access token updated.")

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
        interval=10, # check every minute for finished tournaments TODO make configurable
    )

    app.add_handler(ChatMemberHandler(track_group_chats, ChatMemberHandler.MY_CHAT_MEMBER))

    bet_handler = ConversationHandler(
        entry_points=[CommandHandler("bet", bet, filters=filters.ChatType.PRIVATE)],
        states={
            STATE_TOURNAMENT: [CallbackQueryHandler(select_tournament)],
            STATE_PREDICTING: [CallbackQueryHandler(handle_prediction)],
            STATE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_amount)],
        },
        fallbacks=[] # do nothing, transaction is finalized only at the end
    )

    app.add_handler(bet_handler)
    for command, handler, _, filter in COMMANDS:
        app.add_handler(CommandHandler(command, handler, filters=filter))

    app.run_polling()