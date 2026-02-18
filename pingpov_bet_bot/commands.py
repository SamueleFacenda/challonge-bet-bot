import re
from .storage import Bet, MatchBet, User, Storage, ChallongeTournament, ChallongeMatch
from .api import ChallongeClient

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import ConversationHandler

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

STATE_TOURNAMENT, STATE_PREDICTING, STATE_AMOUNT = range(3)

@ensure_user_registered
async def bet(update, context):
    storage: Storage = context.bot_data['storage']
    api: ChallongeClient = context.bot_data['api_client']

    tournaments = api.get_tournaments()
    tournaments = [t for t in tournaments if t.bets_open]
    if not tournaments:
        await update.message.reply_text("Sorry, there are currently no tournaments open for betting.")
        return
    
    keyboard = [
         [InlineKeyboardButton(t.name, callback_data=t) for t in tournaments]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Please select a tournament to bet on:", reply_markup=reply_markup)
    return STATE_TOURNAMENT

async def select_tournament(update: Update, context):
    api: ChallongeClient = context.bot_data['api_client']
    storage: Storage = context.bot_data['storage']

    query = update.callback_query
    await query.answer()
    tournament: ChallongeTournament = query.data

    bets = storage.get_bets_for_tournament(tournament.challonge_id)
    if any(bet.user_id == query.from_user.id for bet in bets):
        await update.message.reply_text("Sorry, you have already placed a bet on this tournament.")
        return ConversationHandler.END

    context.user_data['selected_tournament'] = tournament
    context.user_data['predictions'] = [] # [(match_id, winner_id, loser_id),...]
    context.user_data['to_predict'] = api.get_tournament_matches(tournament)
    return await ask_match(update, context)

async def ask_match(update, context) -> int:
    api: ChallongeClient = context.bot_data['api_client']
    matches: list[ChallongeMatch] = context.user_data['matches']
    n_predictions = len(context.user_data['predictions'])

    if len(matches):
        match: ChallongeMatch = matches[0]
        player_one: int|None = match.player1_id
        if player_one is None:
            for pred in context.user_data['predictions']:
                if pred.challonge_match_id == match.player1_match_id:
                    if match.player1_is_match_loser:
                        player_one = pred.challonge_loser_id
                    else:
                        player_one = pred.challonge_winner_id
                    break
        player_two: int|None = match.player2_id
        if player_two is None:
            for pred in context.user_data['predictions']:
                if pred.challonge_match_id == match.player2_match_id:
                    if match.player2_is_match_loser:
                        player_two = pred.challonge_loser_id
                    else:
                        player_two = pred.challonge_winner_id
                    break

        players = api.get_tournament_players(context.user_data['selected_tournament'])
        player_one_name = players[player_one]['name'] if player_one in players else str(player_one)
        player_two_name = players[player_two]['name'] if player_two in players else str(player_two)

        keyboard = [
            [InlineKeyboardButton(player_one_name, callback_data=str(player_one)),
             InlineKeyboardButton(player_two_name, callback_data=str(player_two))]
        ]
        text = f"Match {n_predictions + 1}/{len(matches) + n_predictions}: Who will win?\n{player_one_name} vs {player_two_name}"
        
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return STATE_PREDICTING
    else:
        await update.callback_query.edit_message_text("All predictions saved! Now, enter your bet amount:")
        return STATE_AMOUNT
    
async def handle_prediction(update, context) -> int:
    query = update.callback_query
    await query.answer()
    
    # Save selection
    current_match = context.user_data['matches'][0]
    winner_id = int(query.data)
    loser_id = current_match.player1_id if winner_id == current_match.player2_id else current_match.player2_id
    prediction = MatchBet(
        user_id=query.from_user.id,
        challonge_tournament_id=context.user_data['selected_tournament'].challonge_id,
        challonge_match_id=current_match.challonge_id,
        challonge_winner_id=winner_id,
        challonge_loser_id=loser_id
    )
    context.user_data['predictions'].append(prediction)
    
    # Move to next match
    context.user_data['matches'] = context.user_data['matches'][1:]
    return await ask_match(update, context)

async def handle_amount(update, context) -> int:
    storage: Storage = context.bot_data['storage']
    api = context.bot_data['api_client']

    # TODO check if the user has enough balance, if not ask again or end the conversation
    amount = update.message.text

    user: User = storage.get_user(update.message.from_user.id)
    if not re.match(r'^\d+$', amount):
        await update.message.reply_text("Please enter a valid amount (positive integer).")
        return STATE_AMOUNT
    amount = int(amount)

    if amount > user.balance:
        await update.message.reply_text(f"You don't have enough balance to place this bet. Your current balance is {user.balance}. Please enter a valid amount.")
        return STATE_AMOUNT
    
    # TODO check event didn't start

    
    predictions = context.user_data['predictions']
    bet = Bet(
        user_id=update.message.from_user.id,
        challonge_tournament_id=context.user_data['selected_tournament'],
        amount=amount
    )
    storage.add_bet(bet)
    storage.add_match_bets(predictions)



    await update.message.reply_text(f"Bet placed: {amount} on {len(context.user_data['predictions'])} matches!")
    return ConversationHandler.END