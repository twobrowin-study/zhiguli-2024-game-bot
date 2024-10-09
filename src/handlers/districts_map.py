from loguru import logger
from telegram import ReplyKeyboardMarkup, Update
from telegram.constants import ParseMode

from src.exceptions.tg import TgMessageDoesNotExistError
from src.handlers.helpers import get_chat_id_and_func
from src.tg.context import Context


async def districts_map_handler(update: Update, context: Context) -> None:
    """Получить карту райончиков"""
    chat_id, chat_func = get_chat_id_and_func(update, context)

    key_hit = context.bot_data.config.keyboard["show_districts_map"]

    logger.info(f"District map show request from chat {chat_id} with func {chat_func}")

    chat_id_to_teams = await context.bot_data.get_teams_with_district_num()

    template_context = {
        "team": chat_id_to_teams[chat_id] if chat_func == "team" else None,
        "teams": sorted(
            [team for team_chat_id, team in chat_id_to_teams.items() if team_chat_id != chat_id],
            key=lambda team: team["name"],
        ),
    }

    message_template = key_hit.get_message_template()
    message_markdown = message_template.render(context=template_context)

    (
        district_map,
        district_map_set_file_id,
    ) = await context.bot_data.get_districts_map_and_notify_to_set_file_id()

    if not update.message:
        raise TgMessageDoesNotExistError

    reply_markup = context.bot_data.config.get_reply_keys_from_key_ids(
        context.bot_data.config.help_messages[chat_func].keyboard
    )
    sent_message = await update.message.reply_photo(
        district_map,
        caption=message_markdown,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardMarkup(reply_markup) if reply_markup else None,
    )

    if district_map_set_file_id and len(sent_message.photo):
        await context.bot_data.set_districts_map_file_id(sent_message.photo[-1].file_id)
