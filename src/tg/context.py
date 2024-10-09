from telegram.ext import CallbackContext, ExtBot

from src.tg.bot_data import BotData


class Context(CallbackContext[ExtBot, dict, dict, BotData]):
    """Контекст вызова обработчиков сообщений"""
