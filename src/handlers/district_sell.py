from loguru import logger
from telegram import Update
from telegram.ext import ConversationHandler

from src.exceptions.tg import TgChatDataDoesNotExistError
from src.handlers.districts_map import districts_map_handler
from src.handlers.helpers import (
    get_key_text,
    notify,
    notify_all_teams,
    reply_keyboard_key_handler,
)
from src.tg.context import Context


class SellStates:
    TEAM_CHOOSE_AWAIT = 1
    DISTRICT_CHOOSE_AWAIT = 2
    SELL_CONFIRMATION_AWAIT = 3


async def sell_start_handler(update: Update, context: Context) -> int:
    """Начать продажу райончика"""
    reply_keys = context.bot_data.config.get_reply_keys_to_choose_teams()
    await reply_keyboard_key_handler(update, context, override_reply_keys=reply_keys)
    return SellStates.TEAM_CHOOSE_AWAIT


async def sell_team_handler(update: Update, context: Context) -> int:
    """Была выбрана команда - покупатель, теперь следует передать данные о доступных к покупке райончиках"""
    if context.chat_data is None:
        raise TgChatDataDoesNotExistError
    team_name = get_key_text(update, context)

    context.chat_data["team_name"] = team_name
    context.chat_data["team_chat_id"] = context.bot_data.config.chats.team_name_to_team[
        team_name
    ].chat_id

    logger.info(f"Got team for district selling team {team_name}")

    free_district_names = await context.bot_data.get_free_disticts_names()

    reply_keys = context.bot_data.config.get_reply_keys_to_choose_from_flat_list(
        free_district_names
    )
    key_hit = context.bot_data.config.keyboard["district_sell_choose_district"]

    await reply_keyboard_key_handler(
        update, context, override_keyboard_key_hint=key_hit, override_reply_keys=reply_keys
    )
    return SellStates.DISTRICT_CHOOSE_AWAIT


async def sell_district_handler(update: Update, context: Context) -> int:
    """Был выбран райончик - теперь следует подтвердить покупку"""
    if context.chat_data is None:
        raise TgChatDataDoesNotExistError
    district_name = get_key_text(update, context)

    context.chat_data["district_name"] = district_name

    team_name = context.chat_data["team_name"]
    key_hit = context.bot_data.config.keyboard["district_sell_confirm"]

    logger.info(f"Got district for district selling team {team_name} district {district_name}")

    await reply_keyboard_key_handler(
        update,
        context,
        override_keyboard_key_hint=key_hit,
        district_name=district_name,
        team_name=team_name,
    )
    return SellStates.SELL_CONFIRMATION_AWAIT


async def sell_confirm_handler(update: Update, context: Context) -> int:
    """Была подтверждена покупка - следует её произвести и всех уведомить"""
    if context.chat_data is None:
        raise TgChatDataDoesNotExistError

    district_name = context.chat_data["district_name"]
    team_name = context.chat_data["team_name"]
    team_chat_id = context.chat_data["team_chat_id"]

    logger.info(f"Got confirmation for district selling team {team_name} district {district_name}")

    await reply_keyboard_key_handler(
        update, context, district_name=district_name, team_name=team_name
    )
    await context.bot_data.set_district_owner_and_update_districts_map(district_name, team_chat_id)

    notification_all = context.bot_data.config.keyboard["district_sell_notification_all"]
    notification_owner = context.bot_data.config.keyboard["district_sell_notification_owner"]

    notify_all_teams(
        context,
        notification_all,
        except_chat_ids=[team_chat_id],
        district_name=district_name,
        team_name=team_name,
    )
    notify(context, team_chat_id, notification_owner, district_name=district_name)

    logger.info(f"Notified users for district selling team {team_name} district {district_name}")

    await districts_map_handler(update, context)
    return ConversationHandler.END
