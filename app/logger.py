"""
Модуль логирования для OrionEventsToTelegram
"""

import logging
import os
from typing import Optional
from colorama import init, Fore, Style

# Инициализация colorama
init()


class ColoredFormatter(logging.Formatter):
    """Кастомный форматтер с цветным выводом"""
    
    COLORS = {
        logging.ERROR: Fore.RED,
        logging.WARNING: Fore.YELLOW,
        logging.INFO: Fore.GREEN,
        logging.DEBUG: Fore.CYAN,
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Форматирует сообщение с цветом"""
        color = self.COLORS.get(record.levelno, Fore.WHITE)
        record.msg = f"{color}{record.msg}{Style.RESET_ALL}"
        return super().format(record)


class TechnicalLogFilter(logging.Filter):
    """Фильтр для отключения технических логов в не-DEBUG режимах"""
    
    TECHNICAL_KEYWORDS = [
        'Available AUTH mechanisms',
        'Peer:',
        'handling connection',
        'EOF received',
        'Connection lost',
        'connection lost',
        '>> b\'',
        'sender:',
        'recip:'
    ]
    
    def __init__(self, debug_mode: bool = False):
        super().__init__()
        self.debug_mode = debug_mode
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Фильтрует технические сообщения"""
        if self.debug_mode:
            return True
        
        message = record.getMessage()
        return not any(keyword in message for keyword in self.TECHNICAL_KEYWORDS)


class Logger:
    """Основной класс логирования"""
    
    def __init__(self, level: str = 'WARNING'):
        self.level = level.upper()
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Настройка логирования"""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR
        }
        
        log_level = level_map.get(self.level, logging.WARNING)
        
        # Настройка базового логирования
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        
        # Применяем цветной форматтер и фильтр
        for handler in logging.root.handlers:
            handler.setFormatter(ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s'))
            handler.addFilter(TechnicalLogFilter(debug_mode=(self.level == 'DEBUG')))
        
        # Настройка логгеров сторонних библиотек
        self._setup_external_loggers()
    
    def _setup_external_loggers(self) -> None:
        """Настройка логгеров сторонних библиотек"""
        external_loggers = [
            'aiosmtpd', 'asyncio', 'urllib3', 'requests', 'telebot',
            'aiosmtpd.smtp', 'aiosmtpd.controller', 'aiosmtpd.handlers',
            'aiohttp', 'aiohttp.client', 'aiohttp.server'
        ]
        
        for logger_name in external_loggers:
            logger = logging.getLogger(logger_name)
            
            if self.level == 'DEBUG':
                logger.setLevel(logging.DEBUG)
            else:
                logger.setLevel(logging.ERROR)
                logger.propagate = False
                # Удаляем все обработчики
                for handler in logger.handlers[:]:
                    logger.removeHandler(handler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Получение логгера с указанным именем"""
        return logging.getLogger(name)


# Глобальный экземпляр логгера
_logger_instance: Optional[Logger] = None


def setup_logger(level: str = 'WARNING') -> Logger:
    """Инициализация логгера"""
    global _logger_instance
    _logger_instance = Logger(level)
    return _logger_instance


def get_logger(name: str = __name__) -> logging.Logger:
    """Получение логгера"""
    if _logger_instance is None:
        setup_logger()
    assert _logger_instance is not None  # для типизации
    return _logger_instance.get_logger(name)


def log_info(message: str, module: str = 'CORE') -> None:
    """Логирование информационного сообщения"""
    logger = get_logger()
    logger.info(f"[{module}] {message}")


def log_warning(message: str, module: str = 'CORE') -> None:
    """Логирование предупреждения"""
    logger = get_logger()
    logger.warning(f"[{module}] {message}")


def log_error(message: str, module: str = 'CORE') -> None:
    """Логирование ошибки"""
    logger = get_logger()
    logger.error(f"[{module}] {message}")


def log_debug(message: str, module: str = 'CORE') -> None:
    """Логирование отладочной информации"""
    logger = get_logger()
    logger.debug(f"[{module}] {message}")


def log_telegram(message: str) -> None:
    """Логирование Telegram событий"""
    log_info(message, 'Telegram')


def log_smtp(message: str) -> None:
    """Логирование SMTP событий"""
    log_info(message, 'SMTP') 