from loguru import logger
from telegram import Bot, BotCommand, BotName
from telegram.ext import (
    Application,
    BaseHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
)
from telegram.ext.filters import Chat, ChatType, Text

from src.data.config import Config
from src.handlers.basic import (
    cancel_key_hit_handler,
    help_handler,
    simple_key_hit_handler,
)
from src.handlers.district_fight import (
    FightStates,
    fight_choose_assaulter_handler,
    fight_choose_defender_handler,
    fight_district_handler,
    fight_notify_defender_handler,
    fight_result_handler,
    fight_start_handler,
)
from src.handlers.district_sell import (
    SellStates,
    sell_confirm_handler,
    sell_district_handler,
    sell_start_handler,
    sell_team_handler,
)
from src.handlers.districts_map import districts_map_handler


class Configurator:
    """Класс конфигурирования приложения - содержит описание инциализации приложения, фильтры и обработчики событий"""

    HELP_COMMAND = "help"
    """Команда помощи"""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._prepare_filters()
        self.help_handler: BaseHandler = CommandHandler(
            self.HELP_COMMAND, help_handler, filters=self.all_groups_filter, block=False
        )
        self.cancel_handler: BaseHandler = MessageHandler(
            self.cancel_filter, cancel_key_hit_handler, block=False
        )
        self.conversation_fallbacks = [self.help_handler, self.cancel_handler]

    def _prepare_filters(self) -> None:
        """Подготовка фильтров для обработчиков"""
        self.all_groups_filter = ChatType.GROUPS & Chat(self._config.chats.all_chat_ids)
        self.team_groups_filter = ChatType.GROUPS & Chat(self._config.chats.team_chat_ids)
        self.admin_group_filter = ChatType.GROUPS & Chat(self._config.chats.admin)
        self.bank_group_filter = ChatType.GROUPS & Chat(self._config.chats.bank)
        self.fight_group_filter = ChatType.GROUPS & Chat(self._config.chats.fight)

        self.game_mechanics_key_filter = self.team_groups_filter & Text(
            [self._config.keyboard["game_mechanics"].key]
        )

        self.districts_map_key_filter = self.all_groups_filter & Text(
            [self._config.keyboard["show_districts_map"].key]
        )

        self.cancel_filter = (self.bank_group_filter | self.fight_group_filter) & Text(
            [self._config.keyboard["cancel"].key]
        )

        self.sell_keys_filter = self.bank_group_filter & Text(
            [
                self._config.keyboard["district_sell_start_choose_team"].key,
                *self._config.chats.team_names,
                *self._config.districts_map.distict_names,
                self._config.keyboard["district_sell_confirmed"].key,
            ]
        )

        self.fight_keys_filter = self.fight_group_filter & Text(
            [
                self._config.keyboard["district_fight_start_choose_assaulter"].key,
                *self._config.chats.team_names,
                *self._config.districts_map.distict_names,
            ]
        )

        self.fight_notify_filter = self.fight_group_filter & Text(
            [self._config.keyboard["district_fight_notify_defender"].key]
        )

    async def application_post_init(self, application: Application) -> None:
        """Инциализация окружения приложения для конфигурации бота"""
        logger.info("Application post init...")

        bot: Bot = application.bot
        bot_my_name: BotName = await bot.get_my_name()
        if bot_my_name.name != self._config.my_name:
            await bot.set_my_name(self._config.my_name)
            logger.info("Found difference in my name - updated")

        bot_my_comands: tuple[BotCommand, ...] = await bot.get_my_commands()
        my_commands = (BotCommand(self.HELP_COMMAND, self._config.help_comand_hint),)
        if bot_my_comands != my_commands:
            await bot.set_my_commands(my_commands)
            logger.info("Found difference in my commands - updated")

        logger.success("Done application post init")

    def create_basic_handlers(self) -> list[BaseHandler]:
        """Основные обработчики команд и клавиш"""
        return [
            self.help_handler,
            MessageHandler(self.game_mechanics_key_filter, simple_key_hit_handler, block=False),
            MessageHandler(self.districts_map_key_filter, districts_map_handler, block=False),
        ]

    def create_district_sell_conversation_handler(self) -> ConversationHandler:
        """Обработчик общения для покупки района"""
        return ConversationHandler(
            entry_points=[MessageHandler(self.sell_keys_filter, sell_start_handler, block=False)],
            states={
                SellStates.TEAM_CHOOSE_AWAIT: [
                    MessageHandler(self.sell_keys_filter, sell_team_handler, block=False)
                ],
                SellStates.DISTRICT_CHOOSE_AWAIT: [
                    MessageHandler(self.sell_keys_filter, sell_district_handler, block=False)
                ],
                SellStates.SELL_CONFIRMATION_AWAIT: [
                    MessageHandler(self.sell_keys_filter, sell_confirm_handler, block=False)
                ],
            },
            fallbacks=self.conversation_fallbacks,
            block=False,
        )

    def create_district_fight_conversation_handler(self) -> ConversationHandler:
        """Обработчик общения для покупки района"""
        return ConversationHandler(
            entry_points=[MessageHandler(self.fight_keys_filter, fight_start_handler, block=False)],
            states={
                FightStates.ASSAULTER_TEAM_CHOOSE_AWAIT: [
                    MessageHandler(
                        self.fight_keys_filter, fight_choose_assaulter_handler, block=False
                    )
                ],
                FightStates.DEFENDER_TEAM_CHOOSE_AWAIT: [
                    MessageHandler(
                        self.fight_keys_filter, fight_choose_defender_handler, block=False
                    )
                ],
                FightStates.FIGHT_RESULT_AWAIT: [
                    MessageHandler(
                        self.fight_notify_filter, fight_notify_defender_handler, block=False
                    ),
                    MessageHandler(self.fight_keys_filter, fight_result_handler, block=False),
                ],
                FightStates.DISTRICT_CHOOSE_AWAIT: [
                    MessageHandler(self.fight_keys_filter, fight_district_handler, block=False)
                ],
            },
            fallbacks=self.conversation_fallbacks,
            block=False,
        )
