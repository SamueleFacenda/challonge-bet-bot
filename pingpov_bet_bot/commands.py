import re
from .storage import Bet, MatchBet, User, Storage, ChallongeTournament, ChallongeMatch
from .api import ChallongeClient
from .broadcast import track_private_chats

from telegram import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Update
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

def command(func):
    """
    Decorator to apply common checks and setup for all command handlers.
    """
    func = ensure_user_registered(func)
    func = track_private_chats(func)
    return func

HELP_TEXT = (
    "/start - Start interacting with the bot\n"
    "/bet - Place a bet on an upcoming tournament\n"
    "/info - Check your current balance and stats\n"
    "/rank - View the current user rankings\n\n"
)

@command
async def start(update, context):
    # Check if this is a deep link (e.g., from bet_not_in_group)
    if context.args and context.args[0] == 'bet':
        return await bet(update, context)
    
    welcome_message = (
        f"👋 Welcome {update.effective_user.first_name}!\n\n"
        f"I'm a betting bot for PingPov tournaments.\n\n"
        f"{HELP_TEXT}"
        f"Get started by placing your first bet!"
    )
    
    await update.message.reply_text(welcome_message)

@command
async def help(update, context):
    help_message = (
        f"Here are the available commands:\n\n"
        f"{HELP_TEXT}"
        f"Feel free to explore and place your bets on upcoming tournaments!"
    )
    await update.message.reply_text(help_message)


@command
async def info(update, context):
    storage = context.bot_data['storage']
    user_balance = storage.get_user(update.message.from_user.id).balance
    await update.message.reply_text(f"Hello {update.message.from_user.first_name}, your current balance is: {user_balance}")

@command
async def rank(update, context):
    storage = context.bot_data['storage']
    top_users = storage.get_ranking()
    ranking_text = "Top Users:\n"
    for i, user in enumerate(top_users[:10], start=1):
        ranking_text += f"{i}. {user.username} - balance: {user.balance}\n"
    user_position = next((i for i, user in enumerate(top_users, start=1) if user.telegram_id == update.message.from_user.id), None)
    if user_position and user_position > 10:
        ranking_text += f"\nYour position: {user_position}. {update.message.from_user.username} - balance: {storage.get_user(update.message.from_user.id).balance}\n"

    await update.message.reply_text(ranking_text)

STATE_TOURNAMENT, STATE_PREDICTING, STATE_AMOUNT = range(3)

def update_tournaments(api: ChallongeClient, storage: Storage):
    tournaments = api.get_tournaments()
    for tournament in tournaments:
        current = storage.get_challonge_tournament(tournament.challonge_id)
        if not current or current.subscriptions_closed:
            matches = api.get_tournament_matches(tournament)
            tournament.started = any(match.started for match in matches)
            if (not current and tournament.subscriptions_closed) or (current and not current.subscriptions_closed and tournament.subscriptions_closed):
                # Store the matches when the tournament subscriptions are closed
                storage.add_challonge_matches(matches)

        tournament.finished = tournament.finished or (current.finished if current else False) # once a tournament is finished, it stays finished
        tournament.outcome_computed = tournament.outcome_computed or (current.outcome_computed if current else False) # once the outcome is computed, it stays computed

        if not current:
            storage.add_challonge_tournament(tournament)
        elif current != tournament:
            storage.update_challonge_tournament(tournament)

@command
async def bet_not_in_group(update, context):
    bot_username = context.bot.username
    deep_link = f"https://t.me/{bot_username}?start=bet"
    await update.message.reply_text(
        f"⚠️ The /bet command is only available in private chats with the bot.\n\n"
        f"Click here to start: {deep_link}"
    )

@command
async def bet(update, context):
    storage: Storage = context.bot_data['storage']
    api: ChallongeClient = context.bot_data['api_client']

    update_tournaments(api, storage)
    tournaments = storage.get_bettable_tournaments()
    if not tournaments:
        await update.message.reply_text("Sorry, there are currently no tournaments open for betting.")
        return ConversationHandler.END
    
    keyboard = [
        [InlineKeyboardButton(t.name, callback_data=str(t.challonge_id)) for t in tournaments]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Please select a tournament to bet on:", reply_markup=reply_markup)
    return STATE_TOURNAMENT

async def select_tournament(update: Update, context):
    storage: Storage = context.bot_data['storage']

    query: CallbackQuery = update.callback_query # type: ignore type is ensured by the handler
    await query.answer()
    tournament: ChallongeTournament = storage.get_challonge_tournament(int(query.data)) # type: ignore tournament exists because it's in the keyboard

    bets = storage.get_bets_for_tournament(tournament.challonge_id)
    if any(bet.user_id == query.from_user.id for bet in bets):
        await query.message.reply_text("Sorry, you have already placed a bet on this tournament.") # type: ignore
        return ConversationHandler.END

    context.user_data['selected_tournament'] = tournament
    context.user_data['predictions'] = [] # [MatchBet(...), ...]
    context.user_data['to_predict'] = storage.get_challonge_matches_for_tournament(tournament.challonge_id)
    return await ask_match(update, context)

async def ask_match(update, context) -> int:
    api: ChallongeClient = context.bot_data['api_client']
    matches: list[ChallongeMatch] = context.user_data['to_predict']
    n_predictions = len(context.user_data['predictions'])

    if not matches:
        await update.callback_query.edit_message_text("All predictions saved! Now, enter your bet amount (per match):")
        return STATE_AMOUNT
    
    match: ChallongeMatch = matches[0]

    players = api.get_tournament_players(context.user_data['selected_tournament'])
    player_one_name = players[match.player1_id]['display_name'] if match.player1_id in players else str(match.player1_id) # type: ignore id is propagated here
    player_two_name = players[match.player2_id]['display_name'] if match.player2_id in players else str(match.player2_id) # type: ignore

    keyboard = [
        [InlineKeyboardButton(player_one_name, callback_data=str(match.player1_id)),
            InlineKeyboardButton(player_two_name, callback_data=str(match.player2_id))]
    ]
    text = f"Match {n_predictions + 1}/{len(matches) + n_predictions}: who will win?"
    
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return STATE_PREDICTING
    
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
            match.player1_id = prediction.challonge_loser_id if match.player1_is_match_loser else prediction.challonge_winner_id
        if match.player2_match_id == prediction.challonge_match_id:
            match.player2_id = prediction.challonge_loser_id if match.player2_is_match_loser else prediction.challonge_winner_id

async def handle_amount(update, context) -> int:
    storage: Storage = context.bot_data['storage']
    api = context.bot_data['api_client']

    amount = update.message.text

    user: User = storage.get_user(update.message.from_user.id) # type: ignore there is ensure user before
    if not re.match(r'^\d+$', amount):
        await update.message.reply_text("Please enter a valid amount (positive integer).")
        return STATE_AMOUNT
    amount = int(amount) # the amount is per match, so later we multiply by the number of predictions

    # TODO take into account already placed bets too
    if amount * len(context.user_data['predictions']) > user.balance:
        await update.message.reply_text(f"You don't have enough balance to place this bet. Your current balance is {user.balance}. Please enter a valid amount.")
        return STATE_AMOUNT
    
    # check if the tournament started in the meantime
    update_tournaments(api, storage)
    updated = storage.get_challonge_tournament(context.user_data['selected_tournament'].challonge_id)
    if updated and updated.started:
        await update.message.reply_text("Sorry, the tournament is no longer open for betting.")
        return ConversationHandler.END
    
    predictions = context.user_data['predictions']
    bet = Bet(
        user_id=update.message.from_user.id,
        challonge_tournament_id=context.user_data['selected_tournament'].challonge_id,
        amount=amount
    )
    storage.add_bet(bet)
    storage.add_match_bets(predictions)

    await update.message.reply_text(f"Bet placed: {amount} on {len(context.user_data['predictions'])} matches!")
    return ConversationHandler.END