import html
import json
import traceback

from loguru import logger
from telegram import Bot, Update
from telegram.constants import ParseMode

from src.tg.context import Context


async def error_handler(update: object, context: Context) -> None:
    """
    Обработчик ошибки:

    * Возвращает пользователю сообщение об ошибке

    * Отправляет сообщение об ошибке во все группы суперадминистраторов
    """
    try:
        if isinstance(update, Update) and update.effective_chat:
            bot: Bot = context.bot
            await bot.send_message(
                update.effective_chat.id,
                context.bot_data.config.error_message,
                parse_mode=ParseMode.MARKDOWN,
            )
    except Exception:
        logger.error("Was not able to retrun user error message")

    if not context.error:
        logger.error("There was no error in context, skipping")
        return

    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    logger.error(f"Exception while handling an update:\n{tb_string}")

    update_str = (
        update.to_dict()
        if isinstance(update, Update)
        else update
        if isinstance(update, dict)
        else str(update)
    )
    messages_parts = [
        "An exception was raised while handling an update",
        f"update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}",
        f"context.chat_data = {html.escape(str(context.chat_data))}",
        f"context.user_data = {html.escape(str(context.user_data))}",
        f"{html.escape(tb_string)}",
    ]
    messages = []
    for message_part_idx, message_part in enumerate(messages_parts):
        curr_len = len(message_part)
        template = "<pre>{message_part}</pre>\n\n" if message_part_idx > 0 else "{message_part}\n"
        if len(messages) > 0 and (len(messages[-1]) + curr_len <= 4096):
            messages[-1] += template.format(message_part=message_part)
        elif curr_len <= 4096:
            messages.append(template.format(message_part=message_part))
        else:
            messages += [
                template.format(
                    message_part=message_part[
                        message_part_text_start_idx : message_part_text_start_idx + 4096
                    ]
                )
                for message_part_text_start_idx in range(0, curr_len, 4096)
            ]

    for message in messages:
        await context.application.bot.send_message(
            context.bot_data.config.chats.admin, message, parse_mode=ParseMode.HTML
        )
