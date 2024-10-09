from loguru import logger
from telegram.ext import BasePersistence, PersistenceInput

from src.data.config import Config
from src.tg.bot_data import BotData

conversation_key = tuple[int | str, ...]


class Persistence(BasePersistence[dict, dict, BotData]):
    """Класс постоянных данных приложения"""

    def __init__(
        self,
        config: Config,
        update_interval: float = 60,
    ) -> None:
        super().__init__(
            store_data=PersistenceInput(
                bot_data=True, chat_data=False, user_data=False, callback_data=False
            ),
            update_interval=update_interval,
        )
        self._config = config

    async def get_bot_data(self) -> BotData:
        logger.info("Initializating bot data")
        bot_data = BotData(config=self._config)
        await bot_data.init()
        logger.info("Done initializating bot data")
        return bot_data

    async def get_user_data(self) -> dict[int, dict]:
        return {}

    async def get_chat_data(self) -> dict[int, dict]:
        return {}

    async def get_callback_data(self) -> None:
        pass

    async def get_conversations(self, name: str) -> dict[conversation_key, object]:  # noqa: ARG002
        return {}

    async def update_conversation(
        self, name: str, key: conversation_key, new_state: object
    ) -> None:
        pass

    async def update_user_data(self, user_id: int, data: dict) -> None:
        pass

    async def update_chat_data(self, chat_id: int, data: dict) -> None:
        pass

    async def update_callback_data(self, data: object) -> None:
        pass

    async def update_bot_data(self, data: BotData) -> None:
        pass

    async def drop_chat_data(self, chat_id: int) -> None:
        pass

    async def drop_user_data(self, user_id: int) -> None:
        pass

    async def refresh_user_data(self, user_id: int, user_data: dict) -> None:
        pass

    async def refresh_chat_data(self, chat_id: int, chat_data: dict) -> None:
        pass

    async def refresh_bot_data(self, bot_data: BotData) -> None:
        pass

    async def flush(self) -> None:
        pass
