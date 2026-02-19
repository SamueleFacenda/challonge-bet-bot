from .api import ChallongeClient
from .storage import ChallongeTournament, Storage
from .commands import update_tournaments
from .broadcast import send_to_all_group_chats, send_to_all_private_chats

from collections import defaultdict

async def check_finished_tournaments(context):
    storage: Storage = context.bot_data['storage']
    api: ChallongeClient = context.bot_data['api_client']
    update_tournaments(api, storage) # update tournaments to get the latest status
    for tour in storage.get_tournaments_not_finalized():
        if tour.finished and not tour.outcome_computed:
            handle_tournament_finished(context, tour)

            tour.outcome_computed = True
            storage.update_challonge_tournament(tour)

def handle_tournament_finished(context, tournament: ChallongeTournament):
    storage: Storage = context.bot_data['storage']
    api: ChallongeClient = context.bot_data['api_client']
    quotes = get_quotes_for_tournament(tournament, storage)
    match_bets = storage.get_match_bets_for_tournament(tournament.challonge_id)
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
            continue # happens when a player did the wrong prediction on a previous match
        
        if bet.challonge_winner_id == match.winner_id:
            same_bet = quotes[bet.challonge_winner_id][bet.challonge_loser_id]
            against_bet = quotes[bet.challonge_loser_id][bet.challonge_winner_id]
            player_results[bet.user_id] += amount[bet.user_id] * against_bet / same_bet
            user_messages[bet.user_id] += (
                f"✅ You won {amount[bet.user_id] * against_bet / same_bet:.2f} coins on match "
                f"'{tournament_players[match.player1_id]['display_name']} vs {tournament_players[match.player2_id]['display_name']}'.\n"
            )
        else:
            player_results[bet.user_id] -= amount[bet.user_id]
            user_messages[bet.user_id] += (
                f"❌ You lost {amount[bet.user_id]} coins on match "
                f"'{tournament_players[match.player1_id]['display_name']} vs {tournament_players[match.player2_id]['display_name']}'.\n"
            )

    # Update user balances
    for user_id, result in player_results.items():
        print(f"User {user_id} has a result of {result} coins for tournament {tournament.name}.")
        user: User = storage.get_user(user_id) # type: ignore user exists because they placed a bet
        user.balance += result
        storage.update_user(user)
        context.bot.send_message(chat_id=user_id, text=f"🏆 Tournament '{tournament.name}' has finished!\n\n{user_messages[user_id]}Your new balance is {user.balance:.2f} coins, delta is {result:.2f}.")
        

def get_quotes_for_tournament(tournament: ChallongeTournament, storage: Storage):
    quotes = storage.get_tournament_quotes(tournament.challonge_id)
    quote_mapping = defaultdict(dict)
    for winner, loser, amount in quotes:
        quote_mapping[winner][loser] = amount
    return quote_mapping