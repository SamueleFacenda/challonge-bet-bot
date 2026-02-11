from time import sleep
from pingpov_bet_bot.storage import AccessToken
import requests as req

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
        

    def get_tournaments(self):
        res = self.session.get(f"{API_BASE_URL}/tournaments.json", params={
            "api_key": CHALLONGE_APIV1_TOKEN,
            "subdomain": COMMUNITY_SUBDOMAIN
            })
        # print res url
        print(f"Requesting tournaments with URL: {res.url}")
        if res.status_code == 200:
            return res.json()
        else:
            print(f"Failed to fetch tournaments: {res.status_code} - {res.text}")
            return []

    def get_user(self):
        return None