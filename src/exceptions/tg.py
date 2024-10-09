class TgChatDoesNotExistError(Exception):
    """Не существует чата, из которого поступило сообщение"""


class TgMessageDoesNotExistError(Exception):
    """Не существет сообщения"""


class TgMessageTextDoesNotExistError(Exception):
    """Не существует текста сообщения"""


class TgChatDataDoesNotExistError(Exception):
    """Не заданы данные чата"""
