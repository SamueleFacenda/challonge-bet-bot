from collections import defaultdict
import logging

from .api import ChallongeClient
from .storage import ChallongeTournament, Storage, TournamentState
from .broadcast import send_to_all_group_chats

logger = logging.getLogger(__name__)

async def check_finished_tournaments(context):
    storage: Storage = context.bot_data['storage']
    update_tournaments(context) # update tournaments to get the latest status
    for tour in storage.get_tournaments_by_state(TournamentState.FINISHED):
        logger.info(f"Tournament {tour.name} just finished, computing outcomes...")
        tour.state = TournamentState.FINALIZED # set here to avoid match api cache

        await handle_tournament_finished(context, tour)

        storage.update_challonge_tournament(tour)
    
        logger.info(f"Tournament {tour.name} outcomes computed and finalized!")

def update_tournaments(context):
    """
    Updates the tournaments storage, plus some business logic:
    - store tournament matches (only one time per tournament)
    - starts and stops the finished tournament checker job when needed
    """
    storage: Storage = context.bot_data['storage']
    api: ChallongeClient = context.bot_data['api_client']

    tournaments = api.get_tournaments()
    check_job_needed = False
    for updated in tournaments:
        stored = storage.get_challonge_tournament(updated.challonge_id)

        if updated.state == TournamentState.LOCKED and (not stored or stored.state < TournamentState.RUNNING): # skip if already running
            # When locked check if states changes to running
            matches = api.get_tournament_matches(updated)
            if any(match.started for match in matches):
                updated.state = TournamentState.RUNNING

            if not stored or stored.state < TournamentState.LOCKED:
                # Transition check, enters here only one time per tournament
                # When gets locked store the matches, only here and one time
                storage.add_challonge_matches(matches)

            check_job_needed = True # someone might have bet, poll to check when it finishes

        if updated.state == TournamentState.FINISHED and (not stored or stored.state < TournamentState.FINALIZED): # check if wasn't already finalized
            check_job_needed = True # schedule a check to compute outcome of this tournament

        if stored and stored.state == TournamentState.RUNNING:
            check_job_needed = True # poll to check when it finishes

        if not stored:
            storage.add_challonge_tournament(updated)
        elif updated.state > stored.state: # only update if the state goes forward
            storage.update_challonge_tournament(updated)

    jobs = context.job_queue.get_jobs_by_name(check_finished_tournaments.__name__)
    assert len(jobs) == 1, "There should be exactly one scheduled job for checking finished tournaments."
    prev = jobs[0].enabled
    jobs[0].enabled = check_job_needed
    if prev != check_job_needed:
        logger.info(f"{'Enabled' if check_job_needed else 'Disabled'} finished tournament checker job.")

async def handle_tournament_finished(context, tournament: ChallongeTournament):
    storage: Storage = context.bot_data['storage']
    api: ChallongeClient = context.bot_data['api_client']

    quotes = get_quotes_for_tournament(tournament, storage)
    match_bets = storage.get_match_bets_for_tournament(tournament.challonge_id)
    if not match_bets:
        logger.info(f"No bets found for tournament {tournament.name}, skipping outcome computation.")
        return

    amount = {b.user_id : b.amount for b in storage.get_bets_for_tournament(tournament.challonge_id)}
    results = {m.challonge_id:m for m in api.get_tournament_matches(tournament)}
    user_messages = {user_id: "" for user_id in amount.keys()}

    tournament_players = api.get_tournament_players(tournament)

    player_results = defaultdict(float)
    for bet in match_bets:
        match = results[bet.challonge_match_id]
        assert(match.winner_id is not None), f"Match {match.challonge_id} in tournament {tournament.name} does not have a winner yet, but the tournament is marked as finished."
        assert(match.player1_id is not None and match.player2_id is not None), f"Match {match.challonge_id} in tournament {tournament.name} does not have both players set."

        players = (match.player1_id, match.player2_id)
        if bet.challonge_winner_id not in players or bet.challonge_loser_id not in players:
            continue # happens when a player did the wrong prediction on a previous match, no money lost
        
        if bet.challonge_winner_id == match.winner_id:
            same_bet = quotes[bet.challonge_winner_id][bet.challonge_loser_id]
            against_bet = quotes[bet.challonge_loser_id][bet.challonge_winner_id]
            earning = amount[bet.user_id] * against_bet / same_bet
            player_results[bet.user_id] += earning
            user_messages[bet.user_id] += f"✅ You won {earning:.2f} coins on match "
        else:
            player_results[bet.user_id] -= amount[bet.user_id]
            user_messages[bet.user_id] += f"❌ You lost {amount[bet.user_id]} coins on match "
        user_messages[bet.user_id] += f"'{tournament_players[match.player1_id]['display_name']} vs {tournament_players[match.player2_id]['display_name']}'.\n"

    # Update user balances
    for user_id, result in player_results.items():
        logger.info(f"User {user_id} has a result of {result} coins for tournament {tournament.name}.")
        user: User = storage.get_user(user_id) # type: ignore user exists because they placed a bet
        user.balance += result
        storage.update_user(user)
        await context.bot.send_message(chat_id=user_id, text=f"🏆 Tournament '{tournament.name}' has finished!\n\n{user_messages[user_id]}\nYour new balance is {user.balance:.2f} coins, delta is {result:.2f}.")
    
    await send_group_messages(context, tournament)

def get_quotes_for_tournament(tournament: ChallongeTournament, storage: Storage):
    """
    Dict of winner -> loser -> amount, number of bets on this result.
    """
    quotes = storage.get_tournament_quotes(tournament.challonge_id)
    quote_mapping = defaultdict(dict)
    for winner, loser, amount in quotes:
        quote_mapping[winner][loser] = amount
    return quote_mapping

async def send_group_messages(context, tournament: ChallongeTournament):
    message = f"🏆 Tournament '{tournament.name}' has finished!\n\nQuotes:\n"
    quotes = get_quotes_for_tournament(tournament, context.bot_data['storage'])
    players = context.bot_data['api_client'].get_tournament_players(tournament)
    for winner, losers in quotes.items():
        for loser, amount in losers.items():
            against = quotes[loser][winner]
            quote = against / amount
            message += f"{quote:.2f} for {players[winner]['display_name']} to beat {players[loser]['display_name']}\n"

    await send_to_all_group_chats(context, message)