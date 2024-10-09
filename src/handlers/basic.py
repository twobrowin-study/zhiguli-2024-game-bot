from telegram import Update
from telegram.ext import ConversationHandler

from src.handlers.helpers import get_help_key_hint, reply_keyboard_key_handler
from src.tg.context import Context


async def simple_key_hit_handler(update: Update, context: Context) -> int:
    """Базовый обработчик нажатия клавиши"""
    await reply_keyboard_key_handler(update, context)
    return ConversationHandler.END


async def help_handler(update: Update, context: Context) -> int:
    """Обработка команды помощи"""
    help_key = get_help_key_hint(update, context)
    await reply_keyboard_key_handler(update, context, help_key)
    return ConversationHandler.END


async def cancel_key_hit_handler(update: Update, context: Context) -> int:
    """Обработчик нажатия клавиши Отмена"""
    help_key = get_help_key_hint(update, context)
    help_reply_keys = context.bot_data.config.get_reply_keys_from_key_ids(help_key.keyboard)
    await reply_keyboard_key_handler(update, context, override_reply_keys=help_reply_keys)
    return ConversationHandler.END
