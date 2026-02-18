import re
from .storage import User

from telegram import InlineKeyboardMarkup, InlineKeyboardButton

START_BALANCE = 1000 # TODO make this configurable

def ensure_user_registered(func):
        """
        Decorator to ensure the user is registered in the database before executing the command.
        """
        async def wrapper(update, context):
            storage = context.bot_data['storage']
            user_id = update.message.from_user.id
            if not storage.get_user(user_id):
                print(f"Registering new user with Telegram ID: {user_id}")
                user = User(
                    telegram_id=user_id,
                    username=update.message.from_user.username or "",
                    balance=START_BALANCE  # Starting balance for new users
                )
                storage.add_user(user)
            return await func(update, context)
        return wrapper


@ensure_user_registered
async def bet(update, context):
    storage = context.bot_data['storage']
    api = context.bot_data['api_client']

    tournaments = api.get_tournaments()
    tournaments = [t for t in tournaments if t.bets_open]
    if not tournaments:
        await update.message.reply_text("Sorry, there are currently no tournaments open for betting.")
        return
    
    keyboard = [
         [InlineKeyboardButton(t.name, callback_data=f"bet_{t.challonge_id}") for t in tournaments]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)


@ensure_user_registered
async def info(update, context):
    storage = context.bot_data['storage']
    user_balance = storage.get_user(update.message.from_user.id).balance
    await update.message.reply_text(f"Hello {update.message.from_user.first_name}, your current balance is: {user_balance}")

@ensure_user_registered
async def rank(update, context):
    storage = context.bot_data['storage']
    top_users = storage.get_ranking()
    ranking_text = "Top Users:\n"
    for i, user in enumerate(top_users[:10], start=1):
        ranking_text += f"{i}. {user.username} - Balance: {user.balance}\n"
    user_position = next((i for i, user in enumerate(top_users, start=1) if user.telegram_id == update.message.from_user.id), None)
    if user_position and user_position > 10:
        ranking_text += f"\nYour position: {user_position}. {update.message.from_user.username} - Balance: {storage.get_user(update.message.from_user.id).balance}\n"

    await update.message.reply_text(ranking_text)