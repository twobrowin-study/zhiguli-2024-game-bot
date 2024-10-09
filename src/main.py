from loguru import logger
from telegram.ext import Application, ContextTypes

from src.configurator import Configurator
from src.data.config import create_config
from src.handlers.error import error_handler
from src.tg.context import Context
from src.tg.persistence import Persistence

if __name__ == "__main__":
    logger.info("Starting...")
    config = create_config()

    persistence = Persistence(config)
    configurator = Configurator(config)

    app = (
        Application.builder()
        .token(config.token)
        .post_init(configurator.application_post_init)
        .persistence(persistence)
        .context_types(ContextTypes(Context))
        .build()
    )
    app.add_error_handler(error_handler, block=False)
    app.add_handlers(configurator.create_basic_handlers())
    app.add_handler(configurator.create_district_sell_conversation_handler())
    app.add_handler(configurator.create_district_fight_conversation_handler())
    app.run_polling()

    logger.info("Done! Have a great day!")
