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
            '[Admins]\n'
            'admin_ids = 123456789,987654321\n'
            '\n'
            '[Database]\n'
            'db_path = db/users.db\n'
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

def get_admin_ids():
    """Получение списка ID администраторов"""
    config = get_config()
    
    if 'Admins' not in config:
        # Возвращаем пустой список если секция не найдена
        return []
    
    admin_ids_str = config.get('Admins', 'admin_ids', fallback='')
    
    if not admin_ids_str:
        return []
    
    try:
        # Разбираем строку с ID через запятую
        admin_ids = []
        for admin_id in admin_ids_str.split(','):
            admin_id = admin_id.strip()
            if admin_id and admin_id.isdigit():
                admin_ids.append(int(admin_id))
        return admin_ids
    except Exception as e:
        print(f"⚠️  Ошибка парсинга ID администраторов: {e}")
        return []

def get_database_path():
    """Получение пути к базе данных"""
    config = get_config()
    
    if 'Database' not in config:
        # Возвращаем путь по умолчанию относительно корня проекта
        return str(Path(__file__).parent.parent / 'db' / 'users.db')
    
    db_path = config.get('Database', 'db_path', fallback='db/users.db')
    
    # Если путь относительный, делаем его абсолютным относительно корня проекта
    if not os.path.isabs(db_path):
        return str(Path(__file__).parent.parent / db_path)
    
    return db_path

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