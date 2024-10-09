class DistrictsMapWasNotSavedError(Exception):
    """Карта райончиков не была сохранена"""


class DistrictsMapFileWasNotFoundInMinioError(Exception):
    """Файл карты райончиков не был найден в MinIO"""


class DistrictsMapsTableIsEmptyError(Exception):
    """Таблица карт райончиков не пуста"""
