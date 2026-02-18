from pingpov_bet_bot.storage import AccessToken, ChallongeMatch, ChallongeTournament
import requests as req
from cachetools import TTLCache, cached

CACHE_MAXSIZE = 256

from .conf import CHALLONGE_APIV1_TOKEN

# Challonge api integration
API_BASE_URL = "https://api.challonge.com/v1"
COMMUNITY_SUBDOMAIN = "0111c8e6013cab705ee34590"

class ChallongeClient:
    """
    A wrapper for the Challonge API v1 using Python req.
    Documentation: https://challonge.apidog.io/
    """

    def __init__(self):
        """
        Initialize the client. Get's the api key from the environment variable
    
        """
        self.session = req.Session()
        
        # Standard headers required by Challonge v2.1 JSON:API spec
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/vnd.api+json",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def authenticate(self, *args) -> None|AccessToken:
        """
        Placeholder for v1, no authentication needed, just return None.
        """
        return None


    def refresh_token(self, old: AccessToken) -> None|AccessToken:
        return None

    def get_communities(self):
        return []
        
    @cached(cache=TTLCache(maxsize=CACHE_MAXSIZE, ttl=30))
    def get_tournaments(self) -> list[ChallongeTournament]:
        res = self.session.get(f"{API_BASE_URL}/tournaments.json", params={
            "api_key": CHALLONGE_APIV1_TOKEN,
            # "subdomain": COMMUNITY_SUBDOMAIN
            })
        # print res url
        print(f"Requesting tournaments with URL: {res.url}")
        if res.status_code == 200:
            return [ChallongeTournament(
                challonge_id=(t := tour['tournament'])['id'],
                name=t['name'],
                subscriptions_closed=t['started_at'] is not None,
                started=False, # computed only later
                finished=t['state'] == "ended"
            ) for tour in res.json()]
        else:
            print(f"Failed to fetch tournaments: {res.status_code} - {res.text}")
            return []

    @cached(cache={}) # tournament matches are fixed when the tournament starts (we use the tournament state as key too)
    def get_tournament_matches(self, tournament: ChallongeTournament) -> list[ChallongeMatch]:
        res = self.session.get(f"{API_BASE_URL}/tournaments/{tournament.challonge_id}/matches.json", params={
            "api_key": CHALLONGE_APIV1_TOKEN,
        })
        print(f"Requesting matches for tournament {tournament.name} with URL: {res.url}")
        if res.status_code == 200:
            return [ChallongeMatch(
                challonge_id=(m := match['match'])['id'],
                tournament_id=tournament.challonge_id,
                started=m['underway_at'] is not None,
                player1_id=m['player1_id'],
                player1_match_id=m['player1_prereq_match_id'],
                player1_is_match_loser=m['player1_is_prereq_match_loser'], # not available in v1
                player2_id=m['player2_id'],
                player2_match_id=m['player2_prereq_match_id'],
                player2_is_match_loser=m['player2_is_prereq_match_loser'], # not available in v1
                winner_id=m['winner_id']
            ) for match in res.json()]
        else:
            print(f"Failed to fetch matches for tournament {tournament.name}: {res.status_code} - {res.text}")
            return []
        
    @cached(cache={})
    def get_tournament_players(self, tournament: ChallongeTournament) -> dict[int, dict[str, str]]:
        res = self.session.get(f"{API_BASE_URL}/tournaments/{tournament.challonge_id}/participants.json", params={
            "api_key": CHALLONGE_APIV1_TOKEN,
        })
        print(f"Requesting players for tournament {tournament.name} with URL: {res.url}")
        if res.status_code == 200:
            return {(p := part['participant'])['id']: p for part in res.json()}
        else:
            print(f"Failed to fetch players for tournament {tournament.name}: {res.status_code} - {res.text}")
            return {}

    def get_user(self):
        return None