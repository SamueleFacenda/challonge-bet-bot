# Challonge telegram bets bot

Bet on challonge tournaments from telegram.

### Features:
- Place bets in private chats
- Get your bets outcome in private chats
- Get the tournament quotes on group chats

## How to run
Use `nix run`, correctly set your env vars or a `.env` file with the following vars:
- `DB_PATH`: path used for the sqlite db
- `TELEGRAM_BOT_TOKEN`: use the both father to create a new bot
- `CHALLONGE_APIV1_TOKEN`: v1 api token for challonge
- `CHALLONGE_CLIENT_ID`: not used right yet
- `CHALLONGE_CLIENT_SECRET`: not used yet

> [!NOTE]
> Challonge api V2 is not complete yet, we are using api V1