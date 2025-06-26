import threading
import logging
from aiosmtpd.controller import Controller
from aiosmtpd.handlers import Message
from email.message import EmailMessage
import telebot
import re
from colorama import init, Fore, Back, Style
from datetime import datetime
import os
from dotenv import load_dotenv
from config import get_telegram_token, get_authorized_users_file, get_user_filters_file

# Настройка кодировки для Windows
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

# Инициализация colorama для Windows
init()

# Загрузка переменных окружения из .env
load_dotenv()

# Получаем токен из переменных окружения
TELEGRAM_BOT_TOKEN = get_telegram_token()
AUTHORIZED_USERS_FILE = get_authorized_users_file()
USER_FILTERS_FILE = get_user_filters_file()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Создаем кастомный форматтер для цветного вывода
class ColoredFormatter(logging.Formatter):
    def format(self, record):
        # Добавляем цвета в зависимости от уровня
        if record.levelno == logging.ERROR:
            color = Fore.RED
        elif record.levelno == logging.WARNING:
            color = Fore.YELLOW
        elif record.levelno == logging.INFO:
            color = Fore.GREEN
        elif record.levelno == logging.DEBUG:
            color = Fore.CYAN
        else:
            color = Fore.WHITE
        
        # Форматируем сообщение с цветом
        record.msg = f"{color}{record.msg}{Style.RESET_ALL}"
        return super().format(record)

# Применяем цветной форматтер
for handler in logging.root.handlers:
    handler.setFormatter(ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s'))

logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

def log_info(message):
    """Логирование информационных сообщений"""
    print(f"{Fore.GREEN}[INFO] {datetime.now().strftime('%H:%M:%S')} - {message}{Style.RESET_ALL}")

def log_warning(message):
    """Логирование предупреждений"""
    print(f"{Fore.YELLOW}[WARN] {datetime.now().strftime('%H:%M:%S')} - {message}{Style.RESET_ALL}")

def log_error(message):
    """Логирование ошибок"""
    print(f"{Fore.RED}[ERROR] {datetime.now().strftime('%H:%M:%S')} - {message}{Style.RESET_ALL}")

def log_success(message):
    """Логирование успешных операций"""
    print(f"{Fore.CYAN}[SUCCESS] {datetime.now().strftime('%H:%M:%S')} - {message}{Style.RESET_ALL}")

def log_telegram(message):
    """Логирование Telegram событий"""
    print(f"{Fore.MAGENTA}[TELEGRAM] {datetime.now().strftime('%H:%M:%S')} - {message}{Style.RESET_ALL}")

def log_smtp(message):
    """Логирование SMTP событий"""
    print(f"{Fore.BLUE}[SMTP] {datetime.now().strftime('%H:%M:%S')} - {message}{Style.RESET_ALL}")

def process_string(s):
    # Извлекаем время (часы и минуты)
    match_time = re.search(r'\b(\d{1,2}:\d{2}):\d{2}\b', s)
    time = match_time.group(1) if match_time else ""

    # Извлекаем направление (Вход или Выход)
    match_direction = re.search(r'режим:(\S+)', s)
    direction = match_direction.group(1) if match_direction else ""

    # Извлекаем ФИО сотрудника
    match_employee = re.search(r'Сотрудник:(.+)', s)
    employee = match_employee.group(1).strip() if match_employee else ""

    # Соответствие направления эмодзи
    direction_emojis = {'Вход': '⚙️', 'Выход': '🏡'}
    emoji = direction_emojis.get(direction, '🚪')

    # Формируем итоговое сообщение
    output = f"🕒 {time} | {emoji} {direction} | 👤 {employee}"
    return output

def get_authorized_users():
    try:
        with open(AUTHORIZED_USERS_FILE, 'r') as f:
            users = f.read().splitlines()
            return [int(user_id) for user_id in users]
    except FileNotFoundError:
        return []

def get_user_filters():
    filters = {}
    try:
        with open(USER_FILTERS_FILE, 'r') as f:
            for line in f:
                if ':' in line:
                    user_id, flt = line.strip().split(':', 1)
                    filters[int(user_id)] = flt
    except FileNotFoundError:
        pass
    return filters

def set_user_filter(user_id, flt):
    filters = get_user_filters()
    filters[user_id] = flt
    with open(USER_FILTERS_FILE, 'w') as f:
        for uid, flt in filters.items():
            f.write(f"{uid}:{flt}\n")

def remove_user_filter(user_id):
    filters = get_user_filters()
    if user_id in filters:
        del filters[user_id]
        with open(USER_FILTERS_FILE, 'w') as f:
            for uid, flt in filters.items():
                f.write(f"{uid}:{flt}\n")
        return True
    return False

class SMTPHandler(Message):
    def handle_message(self, message):
        log_smtp("Получено новое email сообщение")
        
        # Декодируем тело сообщения
        if message.is_multipart():
            body = ''
            for part in message.walk():
                if part.get_content_type() == 'text/plain':
                    charset = part.get_content_charset() or 'utf-8'
                    payload = part.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        body += payload.decode(charset, errors='replace')
                    else:
                        body += str(payload)
        else:
            charset = message.get_content_charset() or 'utf-8'
            payload = message.get_payload(decode=True)
            if isinstance(payload, bytes):
                body = payload.decode(charset, errors='replace')
            else:
                body = str(payload)

        log_smtp(f"Обработка сообщения: {body[:100]}...")

        # Отправляем только тело сообщения в Telegram
        msg_text = body

        authorized_users = get_authorized_users()
        user_filters = get_user_filters()
        
        log_info(f"Отправка сообщения {len(authorized_users)} авторизованным пользователям")
        
        for user_id in authorized_users:
            try:
                employee = re.search(r'Сотрудник:(.+)', msg_text)
                employee_name = employee.group(1).strip() if employee else ""
                flt = user_filters.get(user_id, None)
                
                if flt:
                    if flt.lower() in employee_name.lower():
                        bot.send_message(user_id, process_string(msg_text))
                        log_success(f"Сообщение отправлено пользователю {user_id} (фильтр: {flt})")
                    else:
                        log_info(f"Сообщение отфильтровано для пользователя {user_id} (фильтр: {flt}, сотрудник: {employee_name})")
                else:
                    bot.send_message(user_id, process_string(msg_text))
                    log_success(f"Сообщение отправлено пользователю {user_id}")
                    
            except Exception as e:
                log_error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")

def start_smtp_server():
    log_info("Запуск SMTP сервера...")
    handler = SMTPHandler()
    controller = Controller(handler, hostname='127.0.0.1', port=1025)
    controller.start()
    log_success("SMTP сервер запущен на 127.0.0.1:1025")
    # Держим поток активным
    try:
        while True:
            pass
    except KeyboardInterrupt:
        log_warning("Получен сигнал прерывания, остановка SMTP сервера...")
        controller.stop()
        log_success("SMTP сервер остановлен")

def start_telegram_bot():
    log_info("Запуск Telegram бота...")
    
    @bot.message_handler(commands=['auth'])
    def handle_auth(message):
        log_telegram(f"Попытка авторизации от пользователя {message.from_user.id}")
        if message.text.strip() == '/auth 68233334':
            user_id = message.from_user.id
            authorized_users = get_authorized_users()
            if user_id not in authorized_users:
                with open(AUTHORIZED_USERS_FILE, 'a') as f:
                    f.write(f"{user_id}\n")
                log_success(f"Пользователь {user_id} успешно авторизован")
                bot.reply_to(message, "Вы успешно авторизованы!")
            else:
                log_info(f"Пользователь {user_id} уже авторизован")
                bot.reply_to(message, "Вы уже авторизованы.")
        else:
            log_warning(f"Неудачная попытка авторизации от пользователя {message.from_user.id}")
            bot.reply_to(message, "Неверный код авторизации.")

    @bot.message_handler(commands=['filter'])
    def handle_filter(message):
        log_telegram(f"Установка фильтра от пользователя {message.from_user.id}")
        args = message.text.split(maxsplit=1)
        if len(args) == 2:
            flt = args[1].strip()
            set_user_filter(message.from_user.id, flt)
            log_success(f"Фильтр '{flt}' установлен для пользователя {message.from_user.id}")
            bot.reply_to(message, f"Фильтр установлен: {flt}")
        else:
            log_warning(f"Некорректная команда фильтра от пользователя {message.from_user.id}")
            bot.reply_to(message, "Используйте: /filter фамилия или часть фамилии сотрудника")

    @bot.message_handler(commands=['unfilter'])
    def handle_unfilter(message):
        log_telegram(f"Отключение фильтра от пользователя {message.from_user.id}")
        if remove_user_filter(message.from_user.id):
            log_success(f"Фильтр отключен для пользователя {message.from_user.id}")
            bot.reply_to(message, "Фильтр отключен. Теперь вы будете получать все сообщения.")
        else:
            log_info(f"Попытка отключить несуществующий фильтр от пользователя {message.from_user.id}")
            bot.reply_to(message, "У вас не было установлено фильтра.")

    # Обработчик ошибок Telegram
    @bot.message_handler(func=lambda message: True)
    def handle_all_messages(message):
        log_telegram(f"Получено сообщение от пользователя {message.from_user.id}: {message.text}")

    log_success("Telegram бот запущен")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        log_error(f"Ошибка в Telegram боте: {e}")
        # Перезапуск бота при ошибке
        log_info("Перезапуск Telegram бота...")
        start_telegram_bot()

def main():
    log_info("Запуск приложения OrionEventsToTelegram...")
    
    # Создаем папку db если её нет
    if not os.path.exists('db'):
        os.makedirs('db')
        log_success("Папка db создана")
    
    # Создаем файлы данных если их нет
    if not os.path.exists(AUTHORIZED_USERS_FILE):
        with open(AUTHORIZED_USERS_FILE, 'w', encoding='utf-8') as f:
            pass  # Создаем пустой файл
        log_success(f"Файл {AUTHORIZED_USERS_FILE} создан")
    
    if not os.path.exists(USER_FILTERS_FILE):
        with open(USER_FILTERS_FILE, 'w', encoding='utf-8') as f:
            pass  # Создаем пустой файл
        log_success(f"Файл {USER_FILTERS_FILE} создан")
    
    smtp_thread = threading.Thread(target=start_smtp_server)
    smtp_thread.daemon = True  # Поток завершится при закрытии основного потока
    smtp_thread.start()

    try:
        start_telegram_bot()  # Запускаем бота в основном потоке
    except KeyboardInterrupt:
        log_warning("Получен сигнал CTRL-C (KeyboardInterrupt). Завершение работы...")
        # Здесь можно добавить дополнительные действия по завершению, если нужно
        exit(0)

if __name__ == '__main__':
    main()
