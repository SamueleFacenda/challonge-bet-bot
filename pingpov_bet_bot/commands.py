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

def update_tournaments(api: ChallongeClient, storage: Storage):
    tournaments = api.get_tournaments()
    for tournament in tournaments:
        current = storage.get_challonge_tournament(tournament.challonge_id)
        if not current:
            storage.add_challonge_tournament(tournament)
        elif current != tournament:
            storage.update_challonge_tournament(tournament)

@ensure_user_registered
async def bet(update, context):
    storage: Storage = context.bot_data['storage']
    api: ChallongeClient = context.bot_data['api_client']

    update_tournaments(api, storage)
    tournaments = api.get_tournaments()
    tournaments = [t for t in tournaments if t.bets_open]
    if not tournaments:
        await update.message.reply_text("Sorry, there are currently no tournaments open for betting.")
        return
    
    keyboard = [
         [InlineKeyboardButton(t.name, callback_data=str(t.challonge_id)) for t in tournaments]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Please select a tournament to bet on:", reply_markup=reply_markup)
    return STATE_TOURNAMENT

async def select_tournament(update: Update, context):
    api: ChallongeClient = context.bot_data['api_client']
    storage: Storage = context.bot_data['storage']

    query = update.callback_query
    await query.answer()
    tournament: ChallongeTournament = storage.get_challonge_tournament(int(query.data))

    bets = storage.get_bets_for_tournament(tournament.challonge_id)
    if any(bet.user_id == query.from_user.id for bet in bets):
        await update.message.reply_text("Sorry, you have already placed a bet on this tournament.")
        return ConversationHandler.END

    context.user_data['selected_tournament'] = tournament
    context.user_data['predictions'] = [] # [MatchBet(...), ...]
    context.user_data['to_predict'] = api.get_tournament_matches(tournament)
    return await ask_match(update, context)

async def ask_match(update, context) -> int:
    api: ChallongeClient = context.bot_data['api_client']
    matches: list[ChallongeMatch] = context.user_data['to_predict']
    n_predictions = len(context.user_data['predictions'])

    if len(matches):
        match: ChallongeMatch = matches[0]

        players = api.get_tournament_players(context.user_data['selected_tournament'])
        player_one_name = players[match.player1_id]['display_name'] if match.player1_id in players else str(match.player1_id)
        player_two_name = players[match.player2_id]['display_name'] if match.player2_id in players else str(match.player2_id)

        keyboard = [
            [InlineKeyboardButton(player_one_name, callback_data=str(match.player1_id)),
             InlineKeyboardButton(player_two_name, callback_data=str(match.player2_id))]
        ]
        text = f"Match {n_predictions + 1}/{len(matches) + n_predictions}: who will win?"
        
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return STATE_PREDICTING
    else:
        await update.callback_query.edit_message_text("All predictions saved! Now, enter your bet amount:")
        return STATE_AMOUNT
    
async def handle_prediction(update, context) -> int:
    query = update.callback_query
    await query.answer()
    
    # Save selection
    current_match = context.user_data['to_predict'][0]
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
    propagate_prediction_to_dependent_matches(context.user_data['to_predict'], prediction)
    
    # Move to next match
    context.user_data['to_predict'] = context.user_data['to_predict'][1:]
    return await ask_match(update, context)

def propagate_prediction_to_dependent_matches(matches: list[ChallongeMatch], prediction: MatchBet):
    for match in matches:
        if match.player1_match_id == prediction.challonge_match_id:
            if match.player1_is_match_loser:
                match.player1_id = prediction.challonge_loser_id
            else:
                match.player1_id = prediction.challonge_winner_id
        elif match.player2_match_id == prediction.challonge_match_id:
            if match.player2_is_match_loser:
                match.player2_id = prediction.challonge_loser_id
            else:
                match.player2_id = prediction.challonge_winner_id

async def handle_amount(update, context) -> int:
    storage: Storage = context.bot_data['storage']
    api = context.bot_data['api_client']

    amount = update.message.text

    user: User = storage.get_user(update.message.from_user.id)
    if not re.match(r'^\d+$', amount):
        await update.message.reply_text("Please enter a valid amount (positive integer).")
        return STATE_AMOUNT
    amount = int(amount)

    if amount > user.balance:
        await update.message.reply_text(f"You don't have enough balance to place this bet. Your current balance is {user.balance}. Please enter a valid amount.")
        return STATE_AMOUNT
    
    update_tournaments(api, storage)
    updated = storage.get_challonge_tournament(context.user_data['selected_tournament'].challonge_id)
    if not updated or not updated.bets_open:
        await update.message.reply_text("Sorry, the tournament is no longer open for betting.")
        return ConversationHandler.END
    
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