from .storage import Storage, AccessToken
from .api import ChallongeClient


def main():
    storage = Storage("db.sqlite3")
    api_client = ChallongeClient()

    access_token = storage.get_access_token()
    updated_token = api_client.authenticate(access_token)

    storage.save_access_token(updated_token)
    print("Access token updated.")

    