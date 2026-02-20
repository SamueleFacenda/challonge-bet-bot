# Challonge telegram bets bot

Bet on challonge tournaments from telegram.
<img width="616" height="254" alt="20260220_12h29m07s_grim" src="https://github.com/user-attachments/assets/a4c5f91f-274b-44a8-8c80-c6bdf6187e56" />
<img width="1420" height="998" alt="20260220_12h29m22s_grim" src="https://github.com/user-attachments/assets/5ef41391-801a-4265-8278-b420527b7a34" />

### Features:
- Place bets in private chats
- Get your bets outcome in private chats
- Get the tournament quotes on group chats

## How to run
Use `nix run` from the repo root or `nix run github:SamueleFacenda/challonge-bet-bot` without cloning the repo, 
correctly set your env vars or a `.env` file with the following vars:
- `DB_PATH`: path used for the sqlite db
- `TELEGRAM_BOT_TOKEN`: use the both father to create a new bot
- `CHALLONGE_APIV1_TOKEN`: v1 api token for challonge
- `CHALLONGE_CLIENT_ID`: not used right yet
- `CHALLONGE_CLIENT_SECRET`: not used yet

> [!NOTE]
> Challonge api V2 is not complete yet, we are using api V1
