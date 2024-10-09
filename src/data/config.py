import os
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import find_dotenv, load_dotenv
from jinja2 import Template
from loguru import logger
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.data.minio_client import MinIOClient
from src.exceptions.config import (
    KeyboardKeyHintMessageNotSetError,
    KeyboardkeyHintMessageOrMessagesNotSetError,
    KeyboardKeyHintMessagesNotSetError,
)

chat_func = Literal["admin", "bank", "fight", "team"]
key_id = Literal[
    "cancel",
    "game_mechanics",
    "show_districts_map",
    "district_sell_start_choose_team",
    "district_sell_choose_district",
    "district_sell_confirm",
    "district_sell_confirmed",
    "district_sell_notification_all",
    "district_sell_notification_owner",
    "district_fight_start_choose_assaulter",
    "district_fight_choose_defender",
    "district_fight_notify_defender",
    "district_fight_notification_defender",
    "district_fight_result",
    "district_fight_choose_district",
    "district_fight_done",
    "district_fight_notification_all",
    "district_fight_notification_winner",
    "district_fight_notification_loser",
]


class Team(BaseModel):
    """Модель чата команды"""

    name: str
    chat_id: int
    map_color: str
    color_emoji: str
    default_district_name: str


class Chats(BaseModel):
    """Модель чатов, с которыми может взаимодействовать бот"""

    admin: int
    bank: int
    fight: int
    teams: list[Team]

    team_chat_ids: list[int] = []
    all_chat_ids: list[int] = []

    chat_id_to_func: dict[int, chat_func] = {}
    chat_id_to_team: dict[int, Team] = {}

    default_district_name_to_team_chat_id: dict[str, int] = {}

    team_names: list[str] = []
    team_name_to_team: dict[str, Team] = {}

    def model_post_init(self, __context: Any) -> None:
        self.team_chat_ids = [team.chat_id for team in self.teams]

        self.all_chat_ids = [
            self.admin,
            self.bank,
            self.fight,
            *self.team_chat_ids,
        ]

        self.chat_id_to_func = {
            self.admin: "admin",
            self.bank: "bank",
            self.fight: "fight",
            **{chat_id: "team" for chat_id in self.team_chat_ids},
        }

        self.chat_id_to_team = {team.chat_id: team for team in self.teams}
        self.default_district_name_to_team_chat_id = {
            team.default_district_name: team.chat_id for team in self.teams
        }

        self.team_names = [team.name for team in self.teams]
        self.team_name_to_team = {team.name: team for team in self.teams}
        return super().model_post_init(__context)


class KeyboardKeyHit(BaseModel):
    """Модель реакции на нажатие клавиши клавиатуры (или команды)"""

    key: str
    message: str | None = None
    messages: list[str] | None = None
    keyboard: list[key_id] | None = None

    def model_post_init(self, __context: Any) -> None:
        if not self.message and not self.messages:
            raise KeyboardkeyHintMessageOrMessagesNotSetError
        return super().model_post_init(__context)

    def get_message_template(self) -> Template:
        if not self.message:
            raise KeyboardKeyHintMessageNotSetError
        return Template(self.message)

    def get_messages_templates(self) -> list[Template]:
        if not self.messages:
            raise KeyboardKeyHintMessagesNotSetError
        return [Template(message) for message in self.messages]


class DefaultDistrict(BaseModel):
    """Модель стандартной конфигурации райончиков"""

    name: str
    mask_filename: str


class DistrictsMap(BaseModel):
    """Модель карты райончиков"""

    backing_filename: str
    text_filename: str
    none_map_color: str
    default_districts: list[DefaultDistrict]
    distict_names: list[str] = []

    def model_post_init(self, __context: Any) -> None:
        self.distict_names = [district.name for district in self.default_districts]
        return super().model_post_init(__context)


class Config(BaseSettings):
    """Модель конфига приложения"""

    model_config = SettingsConfigDict(env_nested_delimiter="__")

    token: str

    pg_user: str
    pg_password: str

    minio_root_user: str
    minio_root_password: str
    minio_secure: MinIOClient.MinioSecureType
    minio_host: str
    minio_bucket: str

    my_name: str
    help_comand_hint: str

    error_message: str

    chats: Chats

    districts_map: DistrictsMap

    help_messages: dict[chat_func, KeyboardKeyHit]
    keyboard: dict[key_id, KeyboardKeyHit]
    keyboard_by_key: dict[str, KeyboardKeyHit] = {}

    def model_post_init(self, __context: Any) -> None:
        self.keyboard_by_key = {
            keyboard_key_hint.key: keyboard_key_hint
            for _, keyboard_key_hint in self.keyboard.items()
            if keyboard_key_hint.key
        }
        return super().model_post_init(__context)

    def _get_reply_keys_from_flat_keys(self, reply_keys_flat: list[str]) -> list[list[str]]:
        reply_keys_flat_len = len(reply_keys_flat)
        if reply_keys_flat_len <= 2:
            return [reply_keys_flat]
        return [reply_keys_flat[idx : idx + 2] for idx in range(0, reply_keys_flat_len, 2)]

    def get_reply_keys_from_key_ids(self, key_ids: list[key_id] | None) -> list[list[str]] | None:
        if not key_ids:
            return None
        return self._get_reply_keys_from_flat_keys(
            [self.keyboard[key_id].key for key_id in key_ids if key_id in self.keyboard]
        )

    def get_reply_keys_to_choose_from_flat_list(self, choose_options: list[str]) -> list[list[str]]:
        return [*self._get_reply_keys_from_flat_keys(choose_options), [self.keyboard["cancel"].key]]

    def get_reply_keys_to_choose_teams(
        self, exclude_team_name: str | None = None
    ) -> list[list[str]]:
        team_names = [team.name for team in self.chats.teams if team.name != exclude_team_name]
        return self.get_reply_keys_to_choose_from_flat_list(team_names)


def create_config() -> Config:
    """Создание конфига из файла и переменных окружения"""

    load_dotenv(find_dotenv())

    with Path("config/config.yaml").open() as stream:
        full_config = yaml.safe_load(stream)

    if not full_config:
        full_config = {}

    full_config["minio_secure"] = "unsecure"
    if os.getenv("MINIO_CERTDIR"):
        full_config["minio_secure"] = "tls"

    config_obj = Config(**full_config)

    logger.info(f"\n{config_obj.model_dump_json(indent=4)}")

    return config_obj
