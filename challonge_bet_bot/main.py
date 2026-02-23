import logging
import argparse

from telegram import BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, ConversationHandler, MessageHandler, filters, ChatMemberHandler

from .storage import Storage
from .api import ChallongeClient
from .conf import TELEGRAM_BOT_TOKEN, DB_PATH
from .commands import COMMANDS, bet, select_tournament, handle_prediction, handle_amount, STATE_AMOUNT, STATE_PREDICTING, STATE_TOURNAMENT
from .outcome_computer import check_finished_tournaments
from .broadcast import track_group_chats


async def update_token_job(context: ContextTypes.DEFAULT_TYPE):
    storage: Storage = context.bot_data['storage']
    api_client: ChallongeClient = context.bot_data['api_client']
    old = storage.get_access_token()
    assert old is not None, "No access token found in storage."
    updated = api_client.refresh_token(old)
    storage.save_access_token(updated)
    print("Access token updated in job.")

async def post_init(application):
    commands = [BotCommand(cmd.name, cmd.description) for cmd in COMMANDS]
    await application.bot.set_my_commands(commands)

def main():
    args = argparse.ArgumentParser(description="Challonge Bet Bot")
    args.add_argument("--debug", action="store_true", help="Enable debug logging")
    parsed_args = args.parse_args()
    log_level = logging.DEBUG if parsed_args.debug else logging.INFO

    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING) # lower ptb logging
    # Set log level for my loggers only
    for name in logging.root.manager.loggerDict:
        if name.startswith("challonge_bet_bot"):
            logging.getLogger(name).setLevel(log_level)

    storage = Storage(DB_PATH)
    api_client = ChallongeClient()

    # -5158183686
    storage.add_chat(-1003742761481, True) # TODO remove this, just for testing

    access_token = storage.get_access_token()
    updated_token = api_client.authenticate(access_token)

    # storage.save_access_token(updated_token)
    # print("Access token updated.")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    app.bot_data['storage'] = storage
    app.bot_data['api_client'] = api_client

    if not app.job_queue:
        print("Job queue is not available, cannot execute")
        return

    # app.job_queue.run_repeating(
    #     callback=update_token_job,
    #     interval=datetime.timedelta(days=6, hours=23), # a refres is needed every week
    #     first=updated_token.expires_at - datetime.timedelta(hours=1) # the token was just updated, no negative delay
    # )

    app.job_queue.run_repeating(
        callback=check_finished_tournaments,
        interval=300, # check every 5 minutes
        first=1, # run immediately (then probably disabled)
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
    for cmd in COMMANDS:
        app.add_handler(CommandHandler(cmd.name, cmd.handler, filters=cmd.filter))# type: ignore callback type is too complex

    app.run_polling()