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


class FightStates:
    ASSAULTER_TEAM_CHOOSE_AWAIT = 1
    DEFENDER_TEAM_CHOOSE_AWAIT = 2
    FIGHT_RESULT_AWAIT = 3
    DISTRICT_CHOOSE_AWAIT = 4


async def fight_start_handler(update: Update, context: Context) -> int:
    """Начать стрелку за райончик"""
    reply_keys = context.bot_data.config.get_reply_keys_to_choose_teams()
    await reply_keyboard_key_handler(update, context, override_reply_keys=reply_keys)
    return FightStates.ASSAULTER_TEAM_CHOOSE_AWAIT


async def fight_choose_assaulter_handler(update: Update, context: Context) -> int:
    """Была выбрана команда - атакующий, теперь следует выбрать защищаюгося"""
    if context.chat_data is None:
        raise TgChatDataDoesNotExistError
    assaulter_team_name = get_key_text(update, context)
    context.chat_data["assaulter_team_name"] = assaulter_team_name
    context.chat_data["assaulter_team_chat_id"] = context.bot_data.config.chats.team_name_to_team[
        assaulter_team_name
    ].chat_id

    logger.info(f"Got assaulter team for district fight assaulter team {assaulter_team_name}")

    reply_keys = context.bot_data.config.get_reply_keys_to_choose_teams(assaulter_team_name)
    key_hit = context.bot_data.config.keyboard["district_fight_choose_defender"]

    await reply_keyboard_key_handler(
        update, context, override_keyboard_key_hint=key_hit, override_reply_keys=reply_keys
    )
    return FightStates.DEFENDER_TEAM_CHOOSE_AWAIT


async def fight_choose_defender_handler(update: Update, context: Context) -> int:
    """Была выбрана команда - защищающийся, теперь следует уведомить защищающегося и выбрать результат сражения"""
    if context.chat_data is None:
        raise TgChatDataDoesNotExistError
    defender_team_name = get_key_text(update, context)
    assaulter_team_name = context.chat_data["assaulter_team_name"]
    context.chat_data["defender_team_name"] = defender_team_name

    logger.info(
        f"Got defender team for district fight assaulter team {assaulter_team_name} defender team {defender_team_name}"
    )

    defender_team_chat_id = context.bot_data.config.chats.team_name_to_team[
        defender_team_name
    ].chat_id
    context.chat_data["defender_team_chat_id"] = defender_team_chat_id
    defender_notification = context.bot_data.config.keyboard["district_fight_notification_defender"]
    notify(
        context,
        defender_team_chat_id,
        defender_notification,
        assaulter_team_name=assaulter_team_name,
    )

    logger.info(
        f"Notified team for district fight assaulter team {assaulter_team_name} defender team {defender_team_name}"
    )

    reply_keys = context.bot_data.config.get_reply_keys_to_choose_from_flat_list(
        [
            assaulter_team_name,
            defender_team_name,
            context.bot_data.config.keyboard["district_fight_notify_defender"].key,
        ]
    )
    key_hit = context.bot_data.config.keyboard["district_fight_result"]

    await reply_keyboard_key_handler(
        update,
        context,
        override_keyboard_key_hint=key_hit,
        override_reply_keys=reply_keys,
        defender_team_name=defender_team_name,
        assaulter_team_name=assaulter_team_name,
    )
    return FightStates.FIGHT_RESULT_AWAIT


async def fight_notify_defender_handler(update: Update, context: Context) -> int:
    """Повторно выслать уведомление защищающейся команде"""
    if context.chat_data is None:
        raise TgChatDataDoesNotExistError
    assaulter_team_name = context.chat_data["assaulter_team_name"]
    defender_team_name = context.chat_data["defender_team_name"]
    defender_team_chat_id = context.chat_data["defender_team_chat_id"]

    logger.info(
        f"Got defender notification request for district fight assaulter team {assaulter_team_name} defender team {defender_team_name}"
    )

    defender_notification = context.bot_data.config.keyboard["district_fight_notification_defender"]
    notify(
        context,
        defender_team_chat_id,
        defender_notification,
        assaulter_team_name=assaulter_team_name,
    )

    logger.info(
        f"Notified defender team by request for district fight assaulter team {assaulter_team_name} defender team {defender_team_name}"
    )

    await reply_keyboard_key_handler(update, context, defender_team_name=defender_team_name)
    return FightStates.FIGHT_RESULT_AWAIT


async def fight_result_handler(update: Update, context: Context) -> int:
    """Был выбран результат сражения"""
    if context.chat_data is None:
        raise TgChatDataDoesNotExistError
    winner_team_name = get_key_text(update, context)
    context.chat_data["winner_team_name"] = winner_team_name

    assaulter_team_name = context.chat_data["assaulter_team_name"]
    assaulter_team_chat_id = context.chat_data["assaulter_team_chat_id"]
    defender_team_name = context.chat_data["defender_team_name"]
    defender_team_chat_id = context.chat_data["defender_team_chat_id"]

    if winner_team_name == assaulter_team_name:
        winner_team_chat_id = assaulter_team_chat_id
        loser_team_name = defender_team_name
        loser_team_chat_id = defender_team_chat_id
    else:
        winner_team_chat_id = defender_team_chat_id
        loser_team_name = assaulter_team_name
        loser_team_chat_id = assaulter_team_chat_id

    logger.info(
        f"Got fight results for district fight winner team {winner_team_name} losser team {loser_team_name}"
    )

    context.chat_data["winner_team_chat_id"] = winner_team_chat_id
    context.chat_data["loser_team_name"] = loser_team_name
    context.chat_data["loser_team_chat_id"] = loser_team_chat_id

    loser_district_names = await context.bot_data.get_free_disticts_names_of_team_by_chat_id(
        loser_team_chat_id
    )
    reply_keys = context.bot_data.config.get_reply_keys_to_choose_from_flat_list(
        loser_district_names
    )

    key_hit = context.bot_data.config.keyboard["district_fight_choose_district"]
    await reply_keyboard_key_handler(
        update,
        context,
        override_keyboard_key_hint=key_hit,
        override_reply_keys=reply_keys,
        winner_team_name=winner_team_name,
        loser_team_name=loser_team_name,
    )
    return FightStates.DISTRICT_CHOOSE_AWAIT


async def fight_district_handler(update: Update, context: Context) -> int:
    """Была подтверждена покупка - следует её произвести и всех уведомить"""
    if context.chat_data is None:
        raise TgChatDataDoesNotExistError
    district_name = get_key_text(update, context)
    context.chat_data["district_name"] = district_name

    winner_team_name = context.chat_data["winner_team_name"]
    winner_team_chat_id = context.chat_data["winner_team_chat_id"]
    loser_team_name = context.chat_data["loser_team_name"]
    loser_team_chat_id = context.chat_data["loser_team_chat_id"]

    logger.info(
        f"Got district for district fight winner team {winner_team_name} losser team {loser_team_name} district name {district_name}"
    )

    key_hit = context.bot_data.config.keyboard["district_fight_done"]
    await reply_keyboard_key_handler(
        update,
        context,
        override_keyboard_key_hint=key_hit,
        district_name=district_name,
        winner_team_name=winner_team_name,
        loser_team_name=loser_team_name,
    )

    await context.bot_data.set_district_owner_and_update_districts_map(
        district_name, winner_team_chat_id
    )

    notification_all = context.bot_data.config.keyboard["district_fight_notification_all"]
    notification_winner = context.bot_data.config.keyboard["district_fight_notification_winner"]
    notification_loser = context.bot_data.config.keyboard["district_fight_notification_loser"]

    notify_all_teams(
        context,
        notification_all,
        except_chat_ids=[winner_team_chat_id, loser_team_chat_id],
        district_name=district_name,
        winner_team_name=winner_team_name,
        loser_team_name=loser_team_name,
    )
    notify(
        context,
        winner_team_chat_id,
        notification_winner,
        district_name=district_name,
        loser_team_name=loser_team_name,
    )
    notify(
        context,
        loser_team_chat_id,
        notification_loser,
        district_name=district_name,
        winner_team_name=winner_team_name,
    )

    logger.info(
        f"Notified all users for district fight winner team {winner_team_name} losser team {loser_team_name} district name {district_name}"
    )

    await districts_map_handler(update, context)
    return ConversationHandler.END
