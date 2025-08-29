"""
Модуль логирования для OrionEventsToTelegram
"""

import logging
import os
from typing import Optional
from pathlib import Path
from datetime import datetime

# Инициализация colorama для всех систем
try:
    from colorama import init, Fore, Style
    init(autoreset=True)  # Автоматический сброс цветов
except ImportError:
    # Fallback если colorama не установлен
    class Fore:
        RED = ''
        YELLOW = ''
        GREEN = ''
        CYAN = ''
        BLUE = ''
        MAGENTA = ''
        WHITE = ''
    
    class Style:
        RESET_ALL = ''


class ColoredFormatter(logging.Formatter):
    """Кастомный форматтер с цветным выводом"""
    
    COLORS = {
        logging.ERROR: Fore.RED,
        logging.WARNING: Fore.YELLOW,
        logging.INFO: Fore.GREEN,
        logging.DEBUG: Fore.CYAN,
    }
    
    MODULE_COLORS = {
        'CORE': Fore.GREEN,
        'Telegram': Fore.MAGENTA,
        'SMTP': Fore.BLUE,
        'UserManager': Fore.CYAN,
        'Database': Fore.BLUE,
        'SystemInit': Fore.YELLOW,
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Форматирует сообщение с цветом"""
        # Сначала форматируем базовое сообщение
        formatted = super().format(record)
        
        # Цвет для уровня логирования
        level_color = self.COLORS.get(record.levelno, Fore.WHITE)
        
        # Цвет для модуля
        module_color = self.MODULE_COLORS.get(record.name, Fore.WHITE)
        
        # Применяем цвета к частям сообщения
        parts = formatted.split(' - ')
        if len(parts) >= 4:
            time_part = parts[0]
            level_part = f"{level_color}{parts[1]}{Style.RESET_ALL}"
            name_part = f"{module_color}{parts[2]}{Style.RESET_ALL}"
            msg_part = parts[3]
            return f"{time_part} - {level_part} - {name_part} - {msg_part}"
        
        # Fallback если формат неожиданный
        return f"{level_color}{formatted}{Style.RESET_ALL}"


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
    
    # В DEBUG режиме показываем больше технической информации
    DEBUG_KEYWORDS = [
        'DEBUG:',
        'Connection:',
        'SMTP:',
        'Telegram:',
        'Database:',
        'UserManager:'
    ]
    
    def __init__(self, debug_mode: bool = False):
        super().__init__()
        self.debug_mode = debug_mode
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Фильтрует технические сообщения"""
        message = record.getMessage()
        
        # В не-DEBUG режимах блокируем все DEBUG сообщения
        if not self.debug_mode and record.levelno == logging.DEBUG:
            return False
        
        if self.debug_mode:
            # В DEBUG режиме пропускаем все сообщения с ключевыми словами DEBUG
            if any(keyword in message for keyword in self.DEBUG_KEYWORDS):
                return True
            # Остальные технические сообщения фильтруем даже в DEBUG
            return not any(keyword in message for keyword in self.TECHNICAL_KEYWORDS)
        
        # В не-DEBUG режимах фильтруем все технические сообщения
        # включая те, что содержат DEBUG_KEYWORDS
        return not any(keyword in message for keyword in self.TECHNICAL_KEYWORDS + self.DEBUG_KEYWORDS)


class Logger:
    """Основной класс логирования"""
    
    def __init__(self, level: str = 'WARNING', backup_days: int = 7):
        try:
            self.level = level.upper()
            self.backup_days = backup_days
            self._setup_logging()
        except Exception as e:
            print(f"[ERROR] Logger initialization failed: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _setup_logging(self) -> None:
        """Настройка логирования"""
        try:
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
            
        except Exception as e:
            print(f"[ERROR] Logging setup failed: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback для Windows: минимальный логгер
            if os.name == 'nt':
                try:
                    # Простейшая настройка без сложных форматтеров
                    logging.basicConfig(
                        level=log_level,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[
                            logging.StreamHandler(),
                            logging.FileHandler(log_dir / 'fallback.log', encoding='utf-8')
                        ]
                    )
                except Exception as e2:
                    print(f"[ERROR] Windows fallback also failed: {e2}")
                    raise
            else:
                raise
    
    def _setup_console_handler(self) -> None:
        """Настройка консольного обработчика"""
        try:
            console_handler = logging.StreamHandler()
            
            # Используем цветной форматтер для всех систем
            console_handler.setFormatter(ColoredFormatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s'))
            
            # Добавляем фильтр для всех систем
            console_handler.addFilter(TechnicalLogFilter(debug_mode=(self.level == 'DEBUG')))
            
            logging.getLogger().addHandler(console_handler)
            
        except Exception as e:
            print(f"[ERROR] Console handler setup failed: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: простой обработчик без форматирования
            try:
                simple_handler = logging.StreamHandler()
                simple_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
                simple_handler.setFormatter(simple_formatter)
                logging.getLogger().addHandler(simple_handler)
            except Exception as e2:
                print(f"[ERROR] Console fallback also failed: {e2}")
                raise
    
    def _setup_file_handler(self) -> None:
        """Настройка файлового обработчика с ротацией по дате"""
        try:
            log_dir = Path(__file__).parent.parent / 'log'
            
            # Формируем имя файла только с датой
            dt_str = datetime.now().strftime('%Y%m%d')
            log_file = log_dir / f'{dt_str}_app.log'
            
            # Очищаем старые лог файлы (оставляем только последние backup_days дней)
            self._cleanup_old_logs(log_dir, self.backup_days)
            
            # Используем обычный FileHandler вместо RotatingFileHandler
            # так как ротация теперь по дате, а не по размеру
            file_handler = logging.FileHandler(
                log_file,
                encoding='utf-8'
            )
            
            # Используем FileFormatter для всех систем
            file_handler.setFormatter(FileFormatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s'))
            
            # Добавляем фильтр для всех систем
            file_handler.addFilter(TechnicalLogFilter(debug_mode=(self.level == 'DEBUG')))
            
            logging.getLogger().addHandler(file_handler)
        except Exception as e:
            print(f"[ERROR] File handler setup failed: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: простой файловый обработчик
            try:
                fallback_handler = logging.FileHandler(
                    log_file,
                    encoding='utf-8'
                )
                simple_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
                fallback_handler.setFormatter(simple_formatter)
                logging.getLogger().addHandler(fallback_handler)
            except Exception as e2:
                print(f"[ERROR] File fallback also failed: {e2}")
                raise
    
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
            
            # В DEBUG режиме включаем все логгеры
            if self.level == 'DEBUG':
                logger.setLevel(logging.DEBUG)
                logger.propagate = True  # Разрешаем пропагацию в DEBUG режиме
            else:
                # В других режимах отключаем только в INFO и выше
                logger.setLevel(logging.ERROR)
                logger.propagate = False
                # Удаляем все обработчики
                for handler in logger.handlers[:]:
                    logger.removeHandler(handler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Получение логгера с указанным именем"""
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        return logger


# Глобальный экземпляр логгера
_logger_instance: Optional[Logger] = None


def setup_logger(level: str = 'WARNING', backup_days: int = 7) -> Logger:
    """Инициализация логгера"""
    try:
        global _logger_instance
        _logger_instance = Logger(level, backup_days)
        return _logger_instance
    except Exception as e:
        print(f"[ERROR] Error in setup_logger: {e}")
        raise


def get_logger(name: str = __name__) -> logging.Logger:
    """Получение логгера"""
    if _logger_instance is None:
        setup_logger()
    assert _logger_instance is not None  # для типизации
    return _logger_instance.get_logger(name)


def log_info(message: str, module: str = 'CORE') -> None:
    """Логирование информационного сообщения"""
    try:
        logger = get_logger(module)
        logger.info(message)
    except Exception as e:
        print(f"[ERROR] Error in log_info: {e}")
        # Fallback to print
        print(f"[INFO] {module}: {message}")
        # Дополнительный fallback: попробуем использовать базовый logging
        try:
            basic_logger = logging.getLogger(module)
            basic_logger.setLevel(logging.INFO)
            basic_logger.info(message)
        except Exception as e2:
            print(f"[ERROR] Basic logging fallback also failed: {e2}")
            # Последний fallback: просто print
            print(f"[INFO] {module}: {message}")


def log_warning(message: str, module: str = 'CORE') -> None:
    """Логирование предупреждения"""
    logger = get_logger(module)
    logger.warning(message)


def log_error(message: str, module: str = 'CORE') -> None:
    """Логирование ошибки"""
    logger = get_logger(module)
    logger.error(message)


def log_debug(message: str, module: str = 'CORE') -> None:
    """Логирование отладочной информации"""
    logger = get_logger(module)
    logger.debug(message)


def log_telegram(message: str) -> None:
    """Логирование Telegram событий"""
    log_info(message, 'Telegram')


def log_smtp(message: str) -> None:
    """Логирование SMTP событий"""
    log_info(message, 'SMTP') 