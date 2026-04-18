import logging

from cachetools import TTLCache, cached
import requests as req

from .storage import AccessToken, ChallongeMatch, ChallongeTournament, TournamentState
from .conf import CONFIG

CACHE_MAXSIZE = 256

# Challonge api integration
API_BASE_URL = "https://api.challonge.com/v1"

logger = logging.getLogger(__name__)

class TimeoutSession(req.Session):
    def __init__(self, timeout=10, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._timeout = timeout
    def request(self, method, url, **kwargs):
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self._timeout
        return super().request(method, url, **kwargs)

class ChallongeClient:
    """
    A wrapper for the Challonge API v1 using Python req.
    Documentation: https://challonge.apidog.io/
    """

    def __init__(self):
        """
        Initialize the client. Get's the api key from the environment variable
    
        """
        self.session = TimeoutSession(timeout=10)
        
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


    def refresh_token(self, old: AccessToken) -> AccessToken:
        return None # type: ignore not used

    def get_communities(self):
        return []
        
    @cached(cache=TTLCache(maxsize=CACHE_MAXSIZE, ttl=60)) # takes even more than ttl for challonge to update
    def get_tournaments(self) -> list[ChallongeTournament]:
        res = self.session.get(f"{API_BASE_URL}/tournaments.json", params={
            "api_key": CONFIG.challonge_apiv1_token.get_secret_value(),
            **({"subdomain": CONFIG.challonge_community_subdomain} if CONFIG.challonge_community_subdomain else {})
            })
        # print res url
        logger.debug(f"Requesting tournaments with URL: {res.url}")
        if res.status_code == 200:
            return [ChallongeTournament(
                challonge_id=(t := tour['tournament'])['id'],
                name=t['name'],
                state = TournamentState.FINISHED if t['completed_at'] else
                    (TournamentState.LOCKED if t['started_at'] else TournamentState.CREATED),
            ) for tour in res.json()]
        else:
            logger.error(f"Failed to fetch tournaments: {res.status_code} - {res.text}")
            return []

    @cached(cache=TTLCache(maxsize=CACHE_MAXSIZE, ttl=60)) # ttl cache, maybe needs to be removed
    def get_tournament_matches(self, tournament: ChallongeTournament) -> list[ChallongeMatch]:
        res = self.session.get(f"{API_BASE_URL}/tournaments/{tournament.challonge_id}/matches.json", params={
            "api_key": CONFIG.challonge_apiv1_token.get_secret_value(),
        })
        logger.debug(f"Requesting matches for tournament {tournament.name} with URL: {res.url}")
        if res.status_code == 200:
            return [ChallongeMatch(
                challonge_id=(m := match['match'])['id'],
                tournament_id=tournament.challonge_id,
                started=m['underway_at'] is not None,
                optional=m['optional'] is not None and m['optional'],
                player1_id=m['player1_id'],
                player1_match_id=m['player1_prereq_match_id'],
                player1_is_match_loser=m['player1_is_prereq_match_loser'], # not available in v1
                player2_id=m['player2_id'],
                player2_match_id=m['player2_prereq_match_id'],
                player2_is_match_loser=m['player2_is_prereq_match_loser'], # not available in v1
                winner_id=m['winner_id']
            ) for match in res.json()]
        else:
            logger.error(f"Failed to fetch matches for tournament {tournament.name}: {res.status_code} - {res.text}")
            return []
        
    @cached(cache={}) # no ttl, use tournament state as key too
    def get_tournament_players(self, tournament: ChallongeTournament) -> dict[int, dict[str, str]]:
        res = self.session.get(f"{API_BASE_URL}/tournaments/{tournament.challonge_id}/participants.json", params={
            "api_key": CONFIG.challonge_apiv1_token.get_secret_value(),
        })
        logger.debug(f"Requesting players for tournament {tournament.name} with URL: {res.url}")
        if res.status_code == 200:
            return {(p := part['participant'])['id']: p for part in res.json()}
        else:
            logger.error(f"Failed to fetch players for tournament {tournament.name}: {res.status_code} - {res.text}")
            return {}

    def get_user(self):
        return None