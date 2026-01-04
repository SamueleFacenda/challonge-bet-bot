from time import sleep
from wsgiref import headers
import requests as req
from functools import cache
import json
from datetime import datetime, timedelta

from .conf import CHALLONGE_CLIENT_ID, CHALLONGE_CLIENT_SECRET
from .storage import AccessToken

# Challonge api integration
API_BASE_URL = "https://api.challonge.com/v2.1"
OAUTH_BASE_URL = "https://api.challonge.com/oauth"
DEVICE_AUTH_URL = "https://auth.challonge.com/oauth"
OAUTH_SCOPE = "me tournaments:read matches:read participants:read"

TOKEN_EXPIRE_TIME = timedelta(days=7)

# https://connect.challonge.com/challonge/apps/56501/edit


class ChallongeClient:
    """
    A wrapper for the Challonge API v2.1 using Python req.
    Documentation: https://challonge.apidog.io/
    """

    def __init__(self):
        """
        Initialize the client. You must provide either an api_key OR an oauth_token.
        
        Args:
            api_key (str): Your personal API Key (v1 key).
            oauth_token (str): A valid OAuth 2.0 Bearer token.
        """
        self.session = req.Session()
        
        # Standard headers required by Challonge v2.1 JSON:API spec
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/vnd.api+json"
        })
        self.auth_session = req.Session()
        self.auth_session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        })

    def authenticate(self, access_token: AccessToken|None) -> AccessToken:
        """
        Set the OAuth 2.0 Bearer token for authenticated requests.
        Returns the accesstoken, always refreshes or creates a new one.
        """

        if not access_token:
            token = self.new_oauth()
            self.set_new_token(token)
            return token
        
        refreshed = self.refresh_token(access_token)
        self.set_new_token(refreshed)
        return refreshed
        

    def set_new_token(self, access_token: AccessToken):
        self.session.headers.update({
            "Authorization-Type": "v2",
            "Authorization": f"Bearer {access_token.access_token}"
        })

    def new_oauth(self) -> AccessToken:
        res = self.auth_session.post(
            f"{DEVICE_AUTH_URL}/authorize_device",
            params={
                "client_id": CHALLONGE_CLIENT_ID,
                "scope": OAUTH_SCOPE,
            }
        )
        if res.status_code != 200:
            print(f"Failed to request device authorization: {res.status_code} - {res.text}")
            exit(1)

        res = res.json()
        verification_url = res['verification_uri_complete']
        device_code = res['device_code']
        print(f"Please visit this URL to authorize the application: {verification_url}")

        while True:
            sleep(2)  # wait before polling
            res = self.auth_session.post(
                f"{DEVICE_AUTH_URL}/token",
                params={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                    "client_id": CHALLONGE_CLIENT_ID,
                }
            )
            if res.status_code == 200:
                data = res.json()
                return AccessToken(
                    user="",
                    access_token=data["access_token"],
                    refresh_token=data["refresh_token"],
                    expires_at=datetime.fromtimestamp(data['created_at']) + timedelta(seconds=data["expires_in"])
                )
            elif res.status_code == 400:
                error = res.json().get("error")
                if error == "authorization_pending":
                    continue  # keep polling
                if error == "slow_down":
                    sleep(5)  # increase wait time
                    continue
                else:
                    print(f"Authorization failed: {error}")
                    exit(1)

    def refresh_token(self, old: AccessToken) -> AccessToken:
        res = self.auth_session.post(
            f"{OAUTH_BASE_URL}/token",
            params={
                "client_id": CHALLONGE_CLIENT_ID,
                "grant_type": "refresh_token",
                "refresh_token": old.refresh_token,
                "redirect_uri": "https://pingpov.net/contacts/"
            }
        )
        if res.status_code == 200:
            data = res.json()
            return AccessToken(
                user="",
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_at=datetime.fromtimestamp(data['created_at']) + timedelta(seconds=data["expires_in"])
            )
        else:
            print(f"Failed to refresh token: {res.status_code} - {res.text}")
            exit(1)


    def get_tournaments(self, page=1, per_page=25):
        """
        Fetch a list of tournaments to test the connection.
        """
        endpoint = f"{API_BASE_URL}/tournaments"
        
        params = {
            "page[number]": page,
            "page[size]": per_page
        }

        try:
            response = self.session.get(endpoint, params=params)
            response.raise_for_status() # Raise error for 4xx/5xx responses
            return response.json()
        
        except req.exceptions.HTTPError as err:
            print(f"HTTP Error: {err}")
            print(f"Response Body: {response.text}")
            return None
        except Exception as err:
            print(f"An error occurred: {err}")
            return None

        """
        Example of a POST req to create a tournament.
        Payload must follow JSON:API standard (wrapping data in 'data' -> 'attributes').
        """
        endpoint = f"{API_BASE_URL}/tournaments"
        
        # JSON:API compliant payload
        payload = {
            "data": {
                "type": "tournaments",
                "attributes": {
                    "name": name,
                    "url": url_slug,
                    "tournamentType": tournament_type
                }
            }
        }

        try:
            response = self.session.post(endpoint, json=payload)
            response.raise_for_status()
            return response.json()
        except req.exceptions.HTTPError as err:
            print(f"Creation Failed: {err}")
            print(f"Details: {response.text}")
            return None