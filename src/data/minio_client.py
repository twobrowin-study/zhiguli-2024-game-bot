import asyncio
from io import BytesIO
from typing import Literal

import filetype.filetype
from loguru import logger
from minio import Minio, S3Error
from urllib3 import BaseHTTPResponse


class MinIOClient:
    """Обёртка для удобного асинхронного взаимодействия с MINIO"""

    MinioSecureType = Literal["unsecure", "tls"]

    def __init__(
        self, access_key: str, secret_key: str, secure: MinioSecureType, host: str
    ) -> None:
        self.host = host
        self._minio_secure = secure == "tls"
        self.base_url = f"{'https' if self._minio_secure else 'http'}://{self.host}"
        self._client = Minio(
            self.host, access_key=access_key, secret_key=secret_key, secure=self._minio_secure
        )
        self._semaphore = asyncio.Semaphore(50)

    async def _put_object(
        self, bucket: str, filename: str, bio: BytesIO, content_type: str
    ) -> None:
        """Внутренняя функция для асинхроанного помещения файла в заданный бакет"""

        def _put_object_sync() -> None:
            bio.seek(0)
            self._client.put_object(
                bucket_name=bucket,
                object_name=filename,
                data=bio,
                length=bio.getbuffer().nbytes,
                content_type=content_type,
            )

        await asyncio.get_event_loop().run_in_executor(None, _put_object_sync)

    async def upload(self, bucket: str, filename: str, bio: BytesIO, content_type: str) -> None:
        """
        Асинхронное помещение файла в бакет
        """
        async with self._semaphore:
            logger.info(f"Uploading {filename} to MinIO into bukcket {bucket}")
            await self._put_object(bucket, filename, bio, content_type)
        logger.success(f"Done uploading {filename} to MinIO into bukcket {bucket}")

    async def upload_with_guessed_content_type(
        self, bucket: str, filename: str, bio: BytesIO
    ) -> None:
        """
        Асинхронное помещение файла в бакет c угаданным типом данных
        """
        bio.seek(0)
        try:
            guessed_file = filetype.guess(bio)
            content_type = guessed_file.mime if guessed_file else "application/octet-stream"
        except TypeError:
            content_type = "application/octet-stream"
        await self.upload(bucket, filename, bio, content_type)

    async def download(self, bucket: str, filename: str) -> tuple[BytesIO | None, str | None]:
        """Асинхронная загрузка файла из бакета"""
        logger.info(f"Downloading {filename} from MinIO bucket {bucket}")

        def _get_object() -> BaseHTTPResponse:
            return self._client.get_object(bucket, filename)

        try:
            response = await asyncio.get_event_loop().run_in_executor(None, _get_object)
            logger.success(f"Done downloading {filename} from MinIO {bucket}")
            file_bytes = BytesIO(response.read())
            content_type = response.getheader("content-type")
        except S3Error as e:
            if e.code == "NoSuchKey":
                logger.info(f"File {filename} not found in MinIO {bucket}")
                file_bytes = None
                content_type = "application/octet-stream"
            else:
                raise
        else:
            response.close()
            response.release_conn()

        return file_bytes, content_type

    async def create_bucket_and_check_if_empty(self, bucket: str) -> bool:
        """Асинхронное создание бакета если его не существует и получение булевой переменной о наличии в нём файлов"""
        logger.info(f"Creating MinIO bucket {bucket}")

        def _create_bucket() -> bool:
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket)
                logger.success(f"Created MinIO bucket {bucket}")
                return True
            for _ in self._client.list_objects(bucket):
                return False
            return True

        return await asyncio.get_event_loop().run_in_executor(None, _create_bucket)
