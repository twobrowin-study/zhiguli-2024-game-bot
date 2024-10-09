from datetime import datetime

from sqlalchemy import BigInteger, DateTime
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    mapped_column,
)


class DbModel(MappedAsDataclass, DeclarativeBase):
    pass


class District(DbModel):
    """Райончики"""

    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    """Уникальный идентификатор райончика"""

    name: Mapped[str] = mapped_column()
    """Название райончика"""

    mask_filename: Mapped[str] = mapped_column()
    """Название файла маски райончика"""

    owner_chat_id: Mapped[int | None] = mapped_column(nullable=True, index=True, type_=BigInteger)
    """Идентификатор чата владельца райончика"""


class DistrictsMap(DbModel):
    """Карты райончиков с цветовым обозначением владельцев"""

    __tablename__ = "districts_maps"

    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    """Уникальный идентификатор карты"""

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    """Время создание карты"""

    filename: Mapped[str] = mapped_column()
    """Название файла карты райончиков"""

    file_id: Mapped[str | None] = mapped_column(default=None)
    """Id файла карты райончиков в telegram"""
