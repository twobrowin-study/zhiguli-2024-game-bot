from loguru import logger
from telegram import ReplyKeyboardMarkup, Update
from telegram.constants import ParseMode

from src.data.config import KeyboardKeyHit, chat_func
from src.exceptions.tg import (
    TgChatDoesNotExistError,
    TgMessageDoesNotExistError,
    TgMessageTextDoesNotExistError,
)
from src.tg.context import Context


def get_chat_id_and_func(update: Update, context: Context) -> tuple[int, chat_func]:
    """Получить функцию чата"""
    if not update.effective_chat:
        raise TgChatDoesNotExistError
    chat_id = update.effective_chat.id
    chat_func = context.bot_data.config.chats.chat_id_to_func[chat_id]
    return chat_id, chat_func


def get_help_key_hint(update: Update, context: Context) -> KeyboardKeyHit:
    """Получить клавишу получения помощи для чата"""
    _, chat_func = get_chat_id_and_func(update, context)
    return context.bot_data.config.help_messages[chat_func]


def get_key_text(update: Update, _: Context) -> str:
    """Получить текст нажатой клавиши"""
    if not update.message:
        raise TgMessageDoesNotExistError

    if not update.message.text:
        raise TgMessageTextDoesNotExistError

    return update.message.text


def get_key_hint_with_chat_id_and_func(
    update: Update, context: Context
) -> tuple[KeyboardKeyHit, int, chat_func]:
    """Получить нажатую клавишу, идентификатор чата и его функцию"""
    chat_id, chat_func = get_chat_id_and_func(update, context)

    key = get_key_text(update, context)
    key_hit = context.bot_data.config.keyboard_by_key[key]

    logger.info(f"Key hit {key_hit.key} from chat {chat_id} with func {chat_func}")

    return key_hit, chat_id, chat_func


async def reply_keyboard_key_handler(
    update: Update,
    context: Context,
    override_keyboard_key_hint: KeyboardKeyHit | None = None,
    override_reply_keys: list[list[str]] | None = None,
    **additional_template_context: str | int,
) -> None:
    """Стандартный ответ на нажатие клавиши с возможностью отправить клавиатуру для ответа"""
    if override_keyboard_key_hint:
        chat_id, chat_func = get_chat_id_and_func(update, context)
        key_hit = override_keyboard_key_hint
    else:
        key_hit, chat_id, chat_func = get_key_hint_with_chat_id_and_func(update, context)

    template_context = {}
    if chat_func == "team":
        template_context |= {"team": context.bot_data.config.chats.chat_id_to_team[chat_id]}
    if additional_template_context:
        template_context |= additional_template_context

    reply_markup = None
    reply_keys = context.bot_data.config.get_reply_keys_from_key_ids(key_hit.keyboard)
    if override_reply_keys:
        reply_markup = ReplyKeyboardMarkup(override_reply_keys)
    elif key_hit.keyboard and reply_keys:
        reply_markup = ReplyKeyboardMarkup(reply_keys)

    if not update.message:
        raise TgMessageDoesNotExistError

    if key_hit.message:
        message_template = key_hit.get_message_template()
        message_markdown = message_template.render(context=template_context)
        await update.message.reply_markdown(message_markdown, reply_markup=reply_markup)

    if key_hit.messages:
        messages_templates = key_hit.get_messages_templates()
        messages_markdowns = [
            message_template.render(context=template_context)
            for message_template in messages_templates
        ]
        for message_markdown in messages_markdowns:
            await update.message.reply_markdown(message_markdown, reply_markup=reply_markup)


def notify(
    context: Context,
    chat_id: int,
    notification: KeyboardKeyHit,
    **template_context: int | str,
) -> None:
    message_markdown = notification.get_message_template().render(context=template_context)
    context.application.create_task(
        context.bot.send_message(chat_id, message_markdown, ParseMode.MARKDOWN)
    )


def notify_all_teams(
    context: Context,
    notification: KeyboardKeyHit,
    except_chat_ids: list[int] | None = None,
    **template_context: int | str,
) -> None:
    for chat_id in context.bot_data.config.chats.team_chat_ids:
        if except_chat_ids and chat_id not in except_chat_ids:
            notify(context, chat_id, notification, **template_context)
