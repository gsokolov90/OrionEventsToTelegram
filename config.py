import os
from dotenv import load_dotenv

load_dotenv()

def get_telegram_token():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        # Проверяем, существует ли .env файл
        if not os.path.exists('.env'):
            raise RuntimeError(
                'Файл .env не найден!\n'
                'Создайте файл .env в корне проекта со следующим содержимым:\n'
                'TELEGRAM_BOT_TOKEN=ваш_токен_бота_здесь'
            )
        
        # Проверяем содержимое .env файла
        try:
            with open('.env', 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    raise RuntimeError(
                        'Файл .env пустой!\n'
                        'Добавьте в файл .env:\n'
                        'TELEGRAM_BOT_TOKEN=ваш_токен_бота_здесь'
                    )
                elif 'your_telegram_bot_token_here' in content:
                    raise RuntimeError(
                        'В файле .env указан пример токена!\n'
                        'Замените "your_telegram_bot_token_here" на ваш реальный токен бота'
                    )
                else:
                    raise RuntimeError(
                        'TELEGRAM_BOT_TOKEN не найден в .env файле!\n'
                        'Добавьте в файл .env:\n'
                        'TELEGRAM_BOT_TOKEN=ваш_токен_бота_здесь'
                    )
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise e
            else:
                raise RuntimeError(
                    f'Ошибка чтения файла .env: {e}\n'
                    'Убедитесь, что файл .env существует и доступен для чтения'
                )
    
    return token

def get_authorized_users_file():
    return 'db/authorized_users.txt'

def get_user_filters_file():
    return 'db/user_filters.txt' 