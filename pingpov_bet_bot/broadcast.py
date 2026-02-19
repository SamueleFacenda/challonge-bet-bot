from .storage import Storage
from pingpov_bet_bot import storage


async def send_to_all_private_chats(context, message: str):
    storage: Storage = context.bot_data['storage']
    chats = storage.get_private_chats()
    for chat_id in chats:
        await context.bot.send_message(chat_id=chat_id, text=message)

async def send_to_all_group_chats(context, message: str):
    storage: Storage = context.bot_data['storage']
    chats = storage.get_group_chats()
    for chat_id in chats:
        await context.bot.send_message(chat_id=chat_id, text=message)

async def track_group_chats(update, context):
    storage: Storage = context.bot_data['storage']

    result = update.my_chat_member
    chat_id = result.chat.id
    new_status = result.new_chat_member.status

    if new_status in ["member", "administrator"]:
        # Bot was added to a group
        storage.add_chat(chat_id, is_group=True)
        print(f"Added group {chat_id} to database.")
    elif new_status in ["left", "kicked"]:
        # Bot was removed from a group
        storage.remove_chat(chat_id)
        print(f"Removed group {chat_id} from database.")

def track_private_chats(func):
    """
    Decorator to track private chats when users interact with the bot in private messages.
    To be used on command handlers.
    """
    async def wrapper(update, context):
        storage: Storage = context.bot_data['storage']
        chat_id = update.effective_chat.id
        if update.effective_chat.type == "private":
            storage.add_chat(chat_id, is_group=False)
            print(f"Added private chat {chat_id} to database.")
        return await func(update, context)
    return wrapper
