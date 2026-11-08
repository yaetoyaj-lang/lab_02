"""Ошибки с сообщениями для пользователя"""


class StreamStatsError(Exception):
    """Базовая ошибка проекта"""


class UnsupportedFormatError(StreamStatsError):
    pass


class InvalidEventError(StreamStatsError):
    pass


class InvalidTimestampError(InvalidEventError):
    pass


class CLIConfigurationError(StreamStatsError):
    pass
