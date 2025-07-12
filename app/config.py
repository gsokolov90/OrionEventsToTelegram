import os
import configparser
from pathlib import Path

def get_config():
    """Получение конфигурации из config.ini"""
    config = configparser.ConfigParser()
    config_path = Path(__file__).parent.parent / 'config.ini'
    
    if not config_path.exists():
        raise RuntimeError(
            'Файл config.ini не найден!\n'
            'Создайте файл config.ini в корне проекта со следующим содержимым:\n'
            '[Telegram]\n'
            'bot_token = ваш_токен_бота_здесь\n'
            '\n'
            '[Paths]\n'
            'authorized_users_file = db/authorized_users.txt\n'
            'user_filters_file = db/user_filters.txt'
        )
    
    config.read(config_path, encoding='utf-8')
    return config

def get_telegram_token():
    config = get_config()
    
    if 'Telegram' not in config:
        raise RuntimeError(
            'Секция [Telegram] не найдена в config.ini!\n'
            'Добавьте секцию:\n'
            '[Telegram]\n'
            'bot_token = ваш_токен_бота_здесь'
        )
    
    token = config.get('Telegram', 'bot_token', fallback=None)
    
    if not token or token == 'your_telegram_bot_token_here':
        raise RuntimeError(
            'TELEGRAM_BOT_TOKEN не настроен в config.ini!\n'
            'Замените "your_telegram_bot_token_here" на ваш реальный токен бота в секции [Telegram]'
        )
    
    return token

def get_authorized_users_file():
    config = get_config()
    
    if 'Paths' not in config:
        raise RuntimeError(
            'Секция [Paths] не найдена в config.ini!\n'
            'Добавьте секцию:\n'
            '[Paths]\n'
            'authorized_users_file = db/authorized_users.txt\n'
            'user_filters_file = db/user_filters.txt'
        )
    
    return config.get('Paths', 'authorized_users_file', fallback='db/authorized_users.txt')

def get_user_filters_file():
    config = get_config()
    
    if 'Paths' not in config:
        raise RuntimeError(
            'Секция [Paths] не найдена в config.ini!\n'
            'Добавьте секцию:\n'
            '[Paths]\n'
            'authorized_users_file = db/authorized_users.txt\n'
            'user_filters_file = db/user_filters.txt'
        )
    
    return config.get('Paths', 'user_filters_file', fallback='db/user_filters.txt')

def get_logging_level():
    config = get_config()
    
    if 'Logging' not in config:
        # По умолчанию WARNING для пользователей
        return 'WARNING'
    
    level = config.get('Logging', 'level', fallback='WARNING').upper()
    
    # Проверяем корректность уровня
    valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
    if level not in valid_levels:
        print(f"⚠️  Неверный уровень логирования '{level}'. Используется WARNING.")
        return 'WARNING'
    
    return level 