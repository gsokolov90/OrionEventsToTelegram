"""
Модуль логирования для OrionEventsToTelegram
"""

import logging
import os
from typing import Optional
from pathlib import Path
from logging.handlers import RotatingFileHandler
from colorama import init, Fore, Style
from datetime import datetime

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


class FileFormatter(logging.Formatter):
    """Форматтер для файлового вывода без цветов"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Форматирует сообщение без цветов для файла"""
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
        
        # Создаем каталог для логов если его нет
        log_dir = Path(__file__).parent.parent / 'log'
        log_dir.mkdir(exist_ok=True)
        
        # Настройка базового логирования
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[]
        )
        
        # Очищаем существующие обработчики
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Создаем обработчики
        self._setup_console_handler()
        self._setup_file_handler()
        
        # Настройка логгеров сторонних библиотек
        self._setup_external_loggers()
    
    def _setup_console_handler(self) -> None:
        """Настройка консольного обработчика"""
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s'))
        console_handler.addFilter(TechnicalLogFilter(debug_mode=(self.level == 'DEBUG')))
        logging.getLogger().addHandler(console_handler)
    
    def _setup_file_handler(self) -> None:
        """Настройка файлового обработчика с ротацией по дате"""
        try:
            try:
                from .config import get_logging_backup_count
            except ImportError:
                from config import get_logging_backup_count
            log_dir = Path(__file__).parent.parent / 'log'
            
            # Формируем имя файла только с датой
            dt_str = datetime.now().strftime('%Y%m%d')
            log_file = log_dir / f'{dt_str}_app.log'
            
            # Очищаем старые лог файлы (оставляем только последние backup_count дней)
            self._cleanup_old_logs(log_dir, get_logging_backup_count())
            
            # Используем обычный FileHandler вместо RotatingFileHandler
            # так как ротация теперь по дате, а не по размеру
            file_handler = logging.FileHandler(
                log_file,
                encoding='utf-8'
            )
            
            file_handler.setFormatter(FileFormatter('%(asctime)s - %(levelname)s - %(message)s'))
            logging.getLogger().addHandler(file_handler)
        except Exception as e:
            print(f"[ERROR] Ошибка при настройке файлового логгера: {e}")
    
    def _cleanup_old_logs(self, log_dir: Path, keep_days: int) -> None:
        """Удаляет старые лог файлы, оставляя только последние keep_days дней"""
        try:
            # Получаем список всех лог файлов
            log_files = list(log_dir.glob('*_app.log'))
            
            # Сортируем файлы по дате (новые в конце)
            log_files.sort()
            
            # Если файлов больше чем нужно сохранить, удаляем старые
            if len(log_files) > keep_days:
                files_to_delete = log_files[:-keep_days]
                for file in files_to_delete:
                    try:
                        file.unlink()
                        print(f"[INFO] Удален старый лог файл: {file.name}")
                    except Exception as e:
                        print(f"[WARNING] Не удалось удалить файл {file.name}: {e}")
        except Exception as e:
            print(f"[WARNING] Ошибка при очистке старых логов: {e}")
    
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