"""
Модуль инициализации системы
"""

import os
import signal
import socket
import sys
from typing import Optional
from .config import get_telegram_token, get_authorized_users_file, get_user_filters_file, get_logging_level
from .logger import setup_logger, log_info, log_error


class SystemInitializer:
    """Класс для инициализации системы"""
    
    def __init__(self):
        self.telegram_token = get_telegram_token()
        self.authorized_users_file = get_authorized_users_file()
        self.user_filters_file = get_user_filters_file()
        self.logging_level = get_logging_level()
    
    def setup_windows_encoding(self) -> None:
        """Настройка кодировки для Windows"""
        if os.name == 'nt':  # Windows
            import locale
            # Устанавливаем UTF-8 кодировку
            os.environ['PYTHONIOENCODING'] = 'utf-8'
            # Пытаемся установить локаль для корректного отображения
            try:
                locale.setlocale(locale.LC_ALL, 'Russian_Russia.UTF-8')
            except:
                try:
                    locale.setlocale(locale.LC_ALL, 'ru_RU.UTF-8')
                except:
                    pass  # Если не удалось установить локаль, продолжаем работу
            # Устанавливаем кодировку консоли Windows
            os.system('chcp 65001 > nul 2>&1')
            # Устанавливаем заголовок окна консоли
            os.system('OrionEventsToTelegram - Мониторинг УРВ')
    
    def setup_logging(self) -> None:
        """Настройка системы логирования"""
        setup_logger(self.logging_level)
        log_info("🚀 Система логирования инициализирована", module='SystemInit')
    
    def check_configuration(self) -> bool:
        """Проверка конфигурации приложения"""
        log_info("🔍 Проверка конфигурации...", module='SystemInit')
        
        # Проверка токена Telegram
        if not self.telegram_token or self.telegram_token == "YOUR_BOT_TOKEN":
            log_error("❌ Не установлен токен Telegram бота в config.ini", module='SystemInit')
            log_error("   Добавьте ваш токен в секцию [telegram] -> token", module='SystemInit')
            return False
        
        # Проверка файлов данных
        try:
            # Проверяем, что можем создать/записать в файлы
            with open(self.authorized_users_file, 'a') as f:
                f.write("")
            with open(self.user_filters_file, 'a') as f:
                f.write("")
        except Exception as e:
            log_error(f"❌ Ошибка доступа к файлам данных: {e}", module='SystemInit')
            return False
        
        log_info("✅ Конфигурация корректна", module='SystemInit')
        return True
    
    def check_smtp_server(self) -> bool:
        """Проверка SMTP сервера"""
        log_info("🔍 Проверка SMTP сервера...", module='SystemInit')
        
        # Проверяем, что порт 1025 свободен
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', 1025))
            sock.close()
            
            if result == 0:
                log_error("❌ Порт 1025 уже занят другим процессом", module='SystemInit')
                log_error("   Остановите другие приложения, использующие порт 1025", module='SystemInit')
                return False
        except Exception as e:
            log_error(f"❌ Ошибка проверки порта SMTP: {e}", module='SystemInit')
            return False
        
        log_info("✅ SMTP сервер готов к запуску", module='SystemInit')
        return True
    
    def check_telegram_bot(self, bot) -> bool:
        """Проверка подключения к Telegram API"""
        log_info("🔍 Проверка подключения к Telegram API...", module='SystemInit')
        
        try:
            # Пробуем получить информацию о боте
            bot_info = bot.get_me()
            log_info(f"✅ Подключение к Telegram API: @{bot_info.username}", module='SystemInit')
            return True
        except Exception as e:
            log_error(f"❌ Ошибка подключения к Telegram API: {e}", module='SystemInit')
            log_error("   Проверьте токен бота и интернет-соединение", module='SystemInit')
            return False
    
    def setup_signal_handlers(self, signal_handler) -> None:
        """Настройка обработчиков сигналов"""
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        log_info("✅ Обработчики сигналов настроены", module='SystemInit')
    
    def create_directories(self) -> None:
        """Создание необходимых директорий"""
        # Создаем папку db если её нет
        if not os.path.exists('db'):
            os.makedirs('db')
            log_info("📁 Папка db создана", module='SystemInit')
        
        # Создаем файлы данных если их нет
        for file_path in [self.authorized_users_file, self.user_filters_file]:
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    pass  # Создаем пустой файл
                log_info(f"📄 Файл {file_path} создан", module='SystemInit')
    
    def initialize_system(self, bot) -> bool:
        """Полная инициализация системы"""
        try:
            # Настройка Windows
            self.setup_windows_encoding()
            
            # Настройка логирования
            self.setup_logging()
            
            # Проверки
            if not self.check_configuration():
                return False
            
            if not self.check_smtp_server():
                return False
            
            if not self.check_telegram_bot(bot):
                return False
            
            # Создание директорий
            self.create_directories()
            
            log_info("✅ Система успешно инициализирована", module='SystemInit')
            return True
            
        except Exception as e:
            log_error(f"❌ Ошибка инициализации системы: {e}", module='SystemInit')
            return False


def get_version() -> str:
    """Читает версию из файла VERSION"""
    try:
        with open('VERSION', 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return "unknown"
    except Exception:
        return "unknown" 