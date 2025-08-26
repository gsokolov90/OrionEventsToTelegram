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
            'users_db_path = db/users.db\n'
            'events_db_path = db/events.db\n'
            'events_retention_days = 180\n'
            '\n'
            '[Cleanup]\n'
            'cleanup_enabled = true\n'
            'cleanup_time = 02:00\n'
            '\n'
            '[Paths]\n'
            'authorized_users_file = db/authorized_users.txt\n'
            'user_filters_file = db/user_filters.txt'
        )
    
    try:
        # Пробуем прочитать с автоматическим определением кодировки
        config.read(config_path, encoding='utf-8')
        print("[DEBUG] Успешно прочитано config.ini с utf-8")
    except Exception as e:
        print(f"[DEBUG] Ошибка чтения config.ini с utf-8: {e}")
        try:
            # Если не получилось, пробуем с utf-8-sig (автоматически убирает BOM)
            config.read(config_path, encoding='utf-8-sig')
            print("[DEBUG] Успешно прочитано с utf-8-sig")
        except Exception as e2:
            print(f"[DEBUG] Ошибка чтения config.ini с utf-8-sig: {e2}")
            # Если и это не помогло, читаем как bytes и декодируем вручную
            try:
                with open(config_path, 'rb') as f:
                    content = f.read()
                    print(f"[DEBUG] Прочитано {len(content)} байт из config.ini")
                    
                    # Убираем BOM если есть
                    if content.startswith(b'\xef\xbb\xbf'):
                        print("[DEBUG] Обнаружен BOM, убираем...")
                        content = content[3:]
                    
                    # Декодируем как UTF-8
                    content_str = content.decode('utf-8')
                    print(f"[DEBUG] Декодировано в строку длиной {len(content_str)}")
                    
                    # Создаем временный файл для configparser
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False, encoding='utf-8') as temp_file:
                        temp_file.write(content_str)
                        temp_file.flush()
                        print(f"[DEBUG] Создан временный файл: {temp_file.name}")
                        config.read(temp_file.name, encoding='utf-8')
                        print("[DEBUG] Успешно прочитано из временного файла")
                        # Удаляем временный файл
                        import os
                        os.unlink(temp_file.name)
                        print("[DEBUG] Временный файл удален")
            except Exception as e3:
                print(f"[DEBUG] Критическая ошибка при обработке config.ini: {e3}")
                raise RuntimeError(f"Не удалось прочитать config.ini: {e3}")
    
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

def get_users_database_path():
    """Получение пути к базе данных пользователей"""
    config = get_config()
    
    if 'Database' not in config:
        # Возвращаем путь по умолчанию относительно корня проекта
        return str(Path(__file__).parent.parent / 'db' / 'users.db')
    
    db_path = config.get('Database', 'users_db_path', fallback='db/users.db')
    
    # Если путь относительный, делаем его абсолютным относительно корня проекта
    if not os.path.isabs(db_path):
        return str(Path(__file__).parent.parent / db_path)
    
    return db_path

def get_events_database_path():
    """Получение пути к базе данных событий"""
    config = get_config()
    
    if 'Database' not in config:
        # Возвращаем путь по умолчанию относительно корня проекта
        return str(Path(__file__).parent.parent / 'db' / 'events.db')
    
    db_path = config.get('Database', 'events_db_path', fallback='db/events.db')
    
    # Если путь относительный, делаем его абсолютным относительно корня проекта
    if not os.path.isabs(db_path):
        return str(Path(__file__).parent.parent / db_path)
    
    return db_path

def get_events_retention_days():
    """Получение количества дней для хранения событий"""
    config = get_config()
    
    if 'Database' not in config:
        # По умолчанию 180 дней
        return 180
    
    try:
        retention_days = config.getint('Database', 'events_retention_days', fallback=180)
        if retention_days < 1:
            print(f"⚠️  Неверное количество дней '{retention_days}'. Используется 180.")
            return 180
        return retention_days
    except ValueError:
        print(f"⚠️  Неверный формат количества дней. Используется 180.")
        return 180

def get_cleanup_enabled():
    """Получение настройки включения автоматической очистки"""
    config = get_config()
    
    if 'Cleanup' not in config:
        # По умолчанию включено
        return True
    
    try:
        return config.getboolean('Cleanup', 'cleanup_enabled', fallback=True)
    except ValueError:
        print(f"⚠️  Неверный формат настройки cleanup_enabled. Используется True.")
        return True

def get_cleanup_time():
    """Получение времени запуска очистки"""
    config = get_config()
    
    if 'Cleanup' not in config:
        # По умолчанию 02:00
        return "02:00"
    
    cleanup_time = config.get('Cleanup', 'cleanup_time', fallback='02:00')
    
    # Проверяем формат времени HH:MM
    import re
    if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', cleanup_time):
        print(f"⚠️  Неверный формат времени '{cleanup_time}'. Используется 02:00.")
        return "02:00"
    
    return cleanup_time

# Для обратной совместимости
def get_database_path():
    """Получение пути к базе данных пользователей (обратная совместимость)"""
    return get_users_database_path()

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

def get_logging_backup_logs_count():
    """Получение количества дней для хранения логов"""
    config = get_config()
    
    if 'Logging' not in config:
        # По умолчанию 5 дней
        return 5
    
    try:
        backup_logs_count = config.getint('Logging', 'backup_logs_count', fallback=5)
        if backup_logs_count < 0:
            print(f"⚠️  Неверное количество дней '{backup_logs_count}'. Используется 5.")
            return 5
        return backup_logs_count
    except ValueError:
        print(f"⚠️  Неверный формат количества дней. Используется 5.")
        return 5 