import io
from datetime import datetime
from pathlib import Path

from loguru import logger
from PIL import Image
from pytz import timezone
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.data.config import Config
from src.data.db_model import DbModel, District, DistrictsMap
from src.data.minio_client import MinIOClient
from src.exceptions.db import (
    DistrictsMapFileWasNotFoundInMinioError,
    DistrictsMapsTableIsEmptyError,
    DistrictsMapWasNotSavedError,
)


class BotData(dict):
    def __init__(self, config: Config) -> None:
        self.config = config
        self._db_engine = create_async_engine(
            f"postgresql+asyncpg://{self.config.pg_user}:{self.config.pg_password}@localhost:5432/postgres",
            echo=False,
            pool_size=10,
            max_overflow=2,
            pool_recycle=300,
            pool_pre_ping=True,
            pool_use_lifo=True,
        )
        self._db_session = async_sessionmaker(bind=self._db_engine)
        self._minio = MinIOClient(
            self.config.minio_root_user,
            self.config.minio_root_password,
            self.config.minio_secure,
            self.config.minio_host,
        )

    async def init(self) -> None:
        """Инциализация"""
        await self.init_minio()
        await self.init_db()

    async def init_minio(self) -> None:
        """Инциализация MinIO"""
        logger.info("Initializing MinIO")
        bucket_empty = await self._minio.create_bucket_and_check_if_empty(self.config.minio_bucket)
        if bucket_empty:
            logger.info("Loading bucket with initial data")
            for file in Path("data").iterdir():
                bio = io.BytesIO(file.read_bytes())
                await self._minio.upload_with_guessed_content_type(
                    self.config.minio_bucket, file.name, bio
                )
            logger.success("Done loading bucket with initial data")
        logger.success("Done initializing MinIO")

    async def init_db(self) -> None:
        """Инциалазация БД"""
        logger.info("Initializing DB")
        async with self._db_engine.begin() as conn:
            await conn.run_sync(DbModel.metadata.create_all)

        logger.info("Initalizig districts table")
        async with self._db_session() as session:
            test_district = await session.scalar(select(District))
            if not test_district:
                logger.info("Loading table districts with default values")

                await session.execute(
                    insert(District).values(
                        [
                            {
                                "name": default_district.name,
                                "mask_filename": default_district.mask_filename,
                                "owner_chat_id": self.config.chats.default_district_name_to_team_chat_id.get(
                                    default_district.name
                                ),
                            }
                            for default_district in self.config.districts_map.default_districts
                        ]
                    )
                )

                await session.commit()
                logger.success("Done loading table districts with default values")

        logger.info("Initializig district maps")
        async with self._db_session() as session:
            test_district_map = await session.scalar(select(DistrictsMap))
            if not test_district_map:
                logger.info("Loading table district maps with default value")
                await self._update_districts_map()
                logger.success("Done loading table district maps with default value")

        logger.success("Done initializing DB")

    async def _update_districts_map(self) -> None:
        """Обновить карту распределения райончиков и получить актуальную версию"""
        districts_map_timestamp = datetime.now(tz=timezone("Europe/Moscow"))
        districts_map_filename = f"districts_map_{districts_map_timestamp.isoformat()}.png"

        logger.info(f"Prepearing new distrits map with filename {districts_map_filename}")

        async with self._db_session() as session:
            logger.info(
                f"Prepearing image file for new districts map with filename {districts_map_filename}"
            )
            districts_map_backing_bio, _ = await self._minio.download(
                self.config.minio_bucket, self.config.districts_map.backing_filename
            )

            if not districts_map_backing_bio:
                raise DistrictsMapFileWasNotFoundInMinioError

            districts_map = Image.open(districts_map_backing_bio)

            districts = await session.scalars(select(District))
            for district in districts:
                district_mask_bio, _ = await self._minio.download(
                    self.config.minio_bucket, district.mask_filename
                )

                if not district_mask_bio:
                    raise DistrictsMapFileWasNotFoundInMinioError

                district_mask = (
                    Image.open(district_mask_bio).convert("L").resize(districts_map.size)
                )
                district_mask_evaled = Image.eval(district_mask, lambda x: x * 0.83)
                district_mask_color = (
                    self.config.chats.chat_id_to_team[district.owner_chat_id].map_color
                    if district.owner_chat_id
                    else self.config.districts_map.none_map_color
                )
                district_mask_color_fill = Image.new("RGB", districts_map.size, district_mask_color)
                districts_map = Image.composite(
                    district_mask_color_fill, districts_map, district_mask_evaled
                )
                district_mask.close()
                district_mask_color_fill.close()

            text_bio, _ = await self._minio.download(
                self.config.minio_bucket, self.config.districts_map.text_filename
            )
            if not text_bio:
                raise DistrictsMapFileWasNotFoundInMinioError
            text = Image.open(text_bio)
            districts_map.alpha_composite(text)
            text.close()

            districts_map_bio = io.BytesIO()
            districts_map.save(districts_map_bio, format="PNG")
            districts_map.close()
            districts_map_bio.seek(0)
            logger.info(
                f"Done prepearing image file for new districts map with filename {districts_map_filename}"
            )

            logger.info(
                f"Uploading file into Minio for new districts map with filename {districts_map_filename}"
            )
            await self._minio.upload_with_guessed_content_type(
                self.config.minio_bucket, districts_map_filename, districts_map_bio
            )

            logger.info(
                f"Prepearing image file for new districts map with filename {districts_map_filename}"
            )
            await session.execute(
                insert(DistrictsMap).values(
                    timestamp=districts_map_timestamp, filename=districts_map_filename
                )
            )

            await session.commit()

            return_districts_map = await session.scalar(
                select(DistrictsMap).order_by(DistrictsMap.timestamp.desc()).limit(1)
            )

            if not return_districts_map:
                raise DistrictsMapWasNotSavedError

            logger.success(
                f"Done prepearing new districts map with filename {districts_map_filename}"
            )

    async def get_districts_map_and_notify_to_set_file_id(self) -> tuple[bytes | str, bool]:
        """Получить байты или идентификатор файла карты райончиков и указание на то, следует ли установить идентийикатор файла"""
        async with self._db_session() as session:
            districts_map = await session.scalar(
                select(DistrictsMap).order_by(DistrictsMap.timestamp.desc()).limit(1)
            )

            if not districts_map:
                raise DistrictsMapsTableIsEmptyError

            if districts_map.file_id:
                return districts_map.file_id, False

            districts_map_bio, _ = await self._minio.download(
                self.config.minio_bucket, districts_map.filename
            )

            if not districts_map_bio:
                raise DistrictsMapFileWasNotFoundInMinioError

            districts_map_bio.seek(0)
            return districts_map_bio.read(), True

    async def set_districts_map_file_id(self, file_id: str) -> None:
        """Установить идентификатор файла райончиков"""
        async with self._db_session() as session:
            districts_map = await session.scalar(
                select(DistrictsMap).order_by(DistrictsMap.timestamp.desc()).limit(1)
            )
            if not districts_map:
                raise DistrictsMapsTableIsEmptyError
            await session.execute(
                update(DistrictsMap)
                .where(DistrictsMap.id == districts_map.id)
                .values(file_id=file_id)
            )
            await session.commit()
            logger.info("Set districts map file id")

    async def get_teams_with_district_num(self) -> dict[int, dict[str, str | int]]:
        """Получить список команд с количеством подконтрольных райончиков"""
        async with self._db_session() as session:
            team_districts = await session.execute(
                select(District.owner_chat_id, func.count(District.owner_chat_id))
                .where(District.owner_chat_id.is_not(None))
                .group_by(District.owner_chat_id)
            )
            return_dict = {}
            for chat_id, district_num in team_districts.all():
                chat_id: int
                district_num: int
                team = self.config.chats.chat_id_to_team[chat_id]
                return_dict |= {
                    chat_id: {
                        "color_emoji": team.color_emoji,
                        "name": team.name,
                        "district_num": district_num,
                    }
                }
            return return_dict

    async def get_free_disticts_names(self) -> list[str]:
        """Получить список не занятых райончиков"""
        async with self._db_session() as session:
            free_districts = await session.scalars(
                select(District.name)
                .where(District.owner_chat_id.is_(None))
                .order_by(District.id.asc())
            )
            return list(free_districts)

    async def get_free_disticts_names_of_team_by_chat_id(self, chat_id: int) -> list[str]:
        """Получить список не занятых райончиков"""
        async with self._db_session() as session:
            free_districts = await session.scalars(
                select(District.name)
                .where(District.owner_chat_id == chat_id)
                .order_by(District.id.asc())
            )
            return list(free_districts)

    async def set_district_owner_and_update_districts_map(
        self, district_name: str, owner_chat_id: int
    ) -> None:
        """Установить владение райончиком и обновить карту райончиков"""
        async with self._db_session() as session:
            await session.execute(
                update(District)
                .where(District.name == district_name)
                .values(owner_chat_id=owner_chat_id)
            )
            await session.commit()
        await self._update_districts_map()

    def __deepcopy__(self, _: object) -> None:
        pass
