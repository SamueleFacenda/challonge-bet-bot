from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict, CliImplicitFlag

class Settings(BaseSettings, cli_parse_args=True):
    telegram_bot_token: SecretStr
    challonge_client_id: str
    challonge_client_secret: SecretStr
    challonge_apiv1_token: SecretStr
    db_path: str = "db.sqlite3"
    challonge_community_subdomain: str = ""
    players_start_balance: int = 1000
    debug: CliImplicitFlag[bool] = False

    # Automatic .env loading
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_prefix='CBB_', 
        env_ignore_empty=True
    )

CONFIG = Settings()