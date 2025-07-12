import threading
import logging
import signal
from aiosmtpd.controller import Controller
from aiosmtpd.handlers import Message
from email.message import EmailMessage
import telebot
import re
from colorama import init, Fore, Back, Style
from datetime import datetime
import os
from config import get_telegram_token, get_authorized_users_file, get_user_filters_file, get_logging_level
import time
import requests

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

# Инициализация colorama для Windows
init()

# Получаем токен из переменных окружения
TELEGRAM_BOT_TOKEN = get_telegram_token()
AUTHORIZED_USERS_FILE = get_authorized_users_file()
USER_FILTERS_FILE = get_user_filters_file()

# Получаем уровень логирования из конфигурации
LOGGING_LEVEL = get_logging_level()

# Преобразуем строку в уровень логирования
level_map = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR
}

# Настройка логирования
logging.basicConfig(
    level=level_map.get(LOGGING_LEVEL, logging.WARNING),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# Принудительно отключаем все логи от сторонних библиотек в не-DEBUG режимах
if LOGGING_LEVEL != 'DEBUG':
    # Отключаем все логгеры, которые могут создавать шум
    for logger_name in ['aiosmtpd', 'asyncio', 'urllib3', 'requests', 'telebot', 
                       'aiosmtpd.smtp', 'aiosmtpd.controller', 'aiosmtpd.handlers',
                       'aiohttp', 'aiohttp.client', 'aiohttp.server']:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.ERROR)
        logger.propagate = False
        # Удаляем все обработчики
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

# Отключаем логи от сторонних библиотек (кроме DEBUG уровня)
if LOGGING_LEVEL != 'DEBUG':
    logging.getLogger('aiosmtpd').setLevel(logging.ERROR)
    logging.getLogger('asyncio').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('requests').setLevel(logging.ERROR)
    logging.getLogger('telebot').setLevel(logging.ERROR)
    # Дополнительно отключаем все логи от aiosmtpd
    logging.getLogger('aiosmtpd.smtp').setLevel(logging.ERROR)
    logging.getLogger('aiosmtpd.controller').setLevel(logging.ERROR)
    logging.getLogger('aiosmtpd.handlers').setLevel(logging.ERROR)
else:
    # В DEBUG режиме показываем технические логи
    logging.getLogger('aiosmtpd').setLevel(logging.DEBUG)
    logging.getLogger('asyncio').setLevel(logging.DEBUG)
    logging.getLogger('urllib3').setLevel(logging.DEBUG)
    logging.getLogger('requests').setLevel(logging.DEBUG)
    logging.getLogger('telebot').setLevel(logging.DEBUG)

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

# Создаем фильтр для отключения технических логов в не-DEBUG режимах
class TechnicalLogFilter(logging.Filter):
    def __init__(self, debug_mode=False):
        super().__init__()
        self.debug_mode = debug_mode
    
    def filter(self, record):
        if self.debug_mode:
            return True
        
        # Отфильтровываем технические сообщения
        technical_keywords = [
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
        
        for keyword in technical_keywords:
            if keyword in record.getMessage():
                return False
        
        return True

# Применяем цветной форматтер и фильтр
for handler in logging.root.handlers:
    handler.setFormatter(ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s'))
    handler.addFilter(TechnicalLogFilter(debug_mode=(LOGGING_LEVEL == 'DEBUG')))

logger = logging.getLogger(__name__)

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Глобальная переменная для контроля завершения бота
stop_bot = False

# Удаляем функцию check_user_input, так как она создает конфликты

def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    global stop_bot
    
    # Проверяем, был ли уже запрос на выход
    if hasattr(signal_handler, 'exit_requested'):
        log_warning("Подтверждено завершение работы...", module='CORE')
        stop_bot = True
        # Останавливаем бота
        try:
            bot.stop_polling()
        except:
            pass
        log_info("Приложение завершено", module='CORE')
        os._exit(0)  # Принудительное завершение
    else:
        # Первый запрос на выход
        signal_handler.exit_requested = True
        print(f"\n{Fore.YELLOW}[WARN] Получен сигнал завершения!{Style.RESET_ALL}")
        
        # ASCII рисунок для подтверждения выхода без боковых рамок
        confirmation_art = f"""
{Fore.CYAN}╔════════════════════════════════════════════════════════════════════╗
                    ⚠️  ПОДТВЕРЖДЕНИЕ ВЫХОДА  ⚠️

  Для подтверждения выхода нажмите Ctrl-C еще раз

  ╭──────────────────────────────────────────────────────────╮
  │                                                          │
  │  [Ctrl-C] ──→ Подтвердить выход                          │
  │                                                          │
  │  [Ожидание 5 сек] ──→ Отменить                           │
  │                                                          │
  ╰──────────────────────────────────────────────────────────╯
╚════════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
        print(confirmation_art)
        
        # Сбрасываем флаг через 5 секунд
        def reset_flag():
            time.sleep(5)
            if hasattr(signal_handler, 'exit_requested'):
                delattr(signal_handler, 'exit_requested')
                print(f"\n{Fore.GREEN}[INFO] Запрос на выход отменен{Style.RESET_ALL}")
        
        # Запускаем поток для сброса флага
        reset_thread = threading.Thread(target=reset_flag)
        reset_thread.daemon = True
        reset_thread.start()

# Универсальная функция логирования с подсветкой модуля
MODULE_COLORS = {
    'CORE': Fore.GREEN,
    'Telegram': Fore.MAGENTA,
    'SMTP': Fore.BLUE,
    'WARNING': Fore.YELLOW,
    'ERROR': Fore.RED,
    'DEBUG': Fore.CYAN
}

def log_message(level, message, module='CORE'):
    color = MODULE_COLORS.get(module, Fore.WHITE)
    level_color = MODULE_COLORS.get(level, Fore.WHITE)
    now = datetime.now().strftime('%H:%M:%S')
    # Формируем строку с подсветкой модуля
    mod_str = f"[{module.upper()}]"
    if level == 'INFO':
        print(f"{color}[INFO] {now} - {mod_str} {message}{Style.RESET_ALL}")
    elif level == 'WARNING':
        print(f"{level_color}[WARN] {now} - {mod_str} {message}{Style.RESET_ALL}")
    elif level == 'ERROR':
        print(f"{level_color}[ERROR] {now} - {mod_str} {message}{Style.RESET_ALL}")
    elif level == 'DEBUG':
        print(f"{level_color}[DEBUG] {now} - {mod_str} {message}{Style.RESET_ALL}")

# Обёртки для разных уровней логирования

def log_info(message, module='CORE'):
    if LOGGING_LEVEL in ['DEBUG', 'INFO']:
        log_message('INFO', message, module)

def log_warning(message, module='CORE'):
    if LOGGING_LEVEL in ['DEBUG', 'INFO', 'WARNING']:
        log_message('WARNING', message, module)

def log_error(message, module='CORE'):
    if LOGGING_LEVEL in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
        log_message('ERROR', message, module)

def log_debug(message, module='CORE'):
    if LOGGING_LEVEL == 'DEBUG':
        log_message('DEBUG', message, module)

# Для совместимости с остальным кодом

def log_telegram(message):
    log_info(message, module='Telegram')

def log_smtp(message):
    log_info(message, module='SMTP')

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
        log_smtp("📧 Получено новое email сообщение")
        
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

        # Извлекаем информацию о сотруднике для более информативного сообщения
        employee_match = re.search(r'Сотрудник:(.+)', body)
        employee_name = employee_match.group(1).strip() if employee_match else "Неизвестный сотрудник"
        
        log_smtp(f"👤 Обработка события: {employee_name}")
        log_debug(f"📧 Полное содержимое email: {body}")
        
        # Отправляем только тело сообщения в Telegram
        msg_text = body

        authorized_users = get_authorized_users()
        user_filters = get_user_filters()
        
        log_info(f"Отправка сообщения {len(authorized_users)} авторизованным пользователям", module='Telegram')
        log_debug(f"📋 Список авторизованных пользователей: {authorized_users}", module='Telegram')
        log_debug(f"🔍 Активные фильтры пользователей: {user_filters}", module='Telegram')
        
        for user_id in authorized_users:
            try:
                employee = re.search(r'Сотрудник:(.+)', msg_text)
                employee_name = employee.group(1).strip() if employee else ""
                flt = user_filters.get(user_id, None)
                log_debug(f"👤 Обработка пользователя {user_id}, фильтр: {flt}, сотрудник: {employee_name}", module='Telegram')
                
                if flt:
                    if flt.lower() in employee_name.lower():
                        bot.send_message(user_id, process_string(msg_text))
                        log_info(f"Сообщение отправлено пользователю {user_id} (фильтр: {flt})", module='Telegram')
                    else:
                        log_info(f"Сообщение отфильтровано для пользователя {user_id} (фильтр: {flt}, сотрудник: {employee_name})", module='Telegram')
                else:
                    bot.send_message(user_id, process_string(msg_text))
                    log_info(f"Сообщение отправлено пользователю {user_id}", module='Telegram')
                    
            except Exception as e:
                log_error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}", module='Telegram')

def start_smtp_server():
    log_info("🚀 Запуск SMTP сервера...", module='SMTP')
    
    # Отключаем логи aiosmtpd если не в DEBUG режиме
    if LOGGING_LEVEL != 'DEBUG':
        import logging
        logging.getLogger('aiosmtpd').setLevel(logging.ERROR)
        logging.getLogger('aiosmtpd.smtp').setLevel(logging.ERROR)
        logging.getLogger('aiosmtpd.controller').setLevel(logging.ERROR)
        logging.getLogger('aiosmtpd.handlers').setLevel(logging.ERROR)
    
    handler = SMTPHandler()
    controller = Controller(handler, hostname='127.0.0.1', port=1025)
    controller.start()
    log_info("✅ SMTP сервер запущен на localhost:1025", module='SMTP')
    # Держим поток активным
    try:
        while True:
            time.sleep(1)  # Небольшая пауза для снижения нагрузки на CPU
    except KeyboardInterrupt:
        log_warning("Получен сигнал прерывания, остановка SMTP сервера...", module='SMTP')
        controller.stop()
        log_info("SMTP сервер остановлен", module='SMTP')

def start_telegram_bot():
    log_info("🤖 Запуск Telegram бота...", module='Telegram')
    
    # Проверка подключения к Telegram API
    check_telegram_bot()
    
    @bot.message_handler(commands=['auth'])
    def handle_auth(message):
        log_telegram(f"Попытка авторизации от пользователя {message.from_user.id}")
        if message.text.strip() == '/auth 68233334':
            user_id = message.from_user.id
            authorized_users = get_authorized_users()
            if user_id not in authorized_users:
                with open(AUTHORIZED_USERS_FILE, 'a') as f:
                    f.write(f"{user_id}\n")
                log_info(f"Пользователь {user_id} успешно авторизован", module='Telegram')
                bot.reply_to(message, "Вы успешно авторизованы!")
            else:
                log_info(f"Пользователь {user_id} уже авторизован", module='Telegram')
                bot.reply_to(message, "Вы уже авторизованы.")
        else:
            log_warning(f"Неудачная попытка авторизации от пользователя {message.from_user.id}", module='Telegram')
            bot.reply_to(message, "Неверный код авторизации.")

    @bot.message_handler(commands=['filter'])
    def handle_filter(message):
        log_telegram(f"Установка фильтра от пользователя {message.from_user.id}")
        args = message.text.split(maxsplit=1)
        if len(args) == 2:
            flt = args[1].strip()
            set_user_filter(message.from_user.id, flt)
            log_info(f"Фильтр '{flt}' установлен для пользователя {message.from_user.id}", module='Telegram')
            bot.reply_to(message, f"Фильтр установлен: {flt}")
        else:
            log_warning(f"Некорректная команда фильтра от пользователя {message.from_user.id}", module='Telegram')
            bot.reply_to(message, "Используйте: /filter фамилия или часть фамилии сотрудника")

    @bot.message_handler(commands=['unfilter'])
    def handle_unfilter(message):
        log_telegram(f"Отключение фильтра от пользователя {message.from_user.id}")
        if remove_user_filter(message.from_user.id):
            log_info(f"Фильтр отключен для пользователя {message.from_user.id}", module='Telegram')
            bot.reply_to(message, "Фильтр отключен. Теперь вы будете получать все сообщения.")
        else:
            log_info(f"Попытка отключить несуществующий фильтр от пользователя {message.from_user.id}", module='Telegram')
            bot.reply_to(message, "У вас не было установлено фильтра.")

    # Обработчик ошибок Telegram
    @bot.message_handler(func=lambda message: True)
    def handle_all_messages(message):
        log_telegram(f"Получено сообщение от пользователя {message.from_user.id}: {message.text}")

    log_info("✅ Telegram бот запущен", module='Telegram')
    
    # Сообщение о готовности сервера после запуска всех модулей
    log_info("📧 SMTP сервер слушает на localhost:1025", module='SMTP')
    log_info("🤖 Telegram бот активен и готов к работе", module='Telegram')
    log_info("🚀 Сервер готов и работает! Все модули запущены успешно.", module='CORE')
    log_info("⏳ Ожидание входящих сообщений от ОРИОН...", module='CORE')
    
    delay = 5  # стартовая задержка между попытками (сек)
    
    # Глобальная переменная для контроля завершения
    global stop_bot
    stop_bot = False
    
    while not stop_bot:
        try:
            # Используем более короткий timeout для быстрого реагирования на сигналы
            bot.infinity_polling(timeout=10, long_polling_timeout=10, skip_pending=True)
        except requests.exceptions.ReadTimeout as e:
            if stop_bot:
                break
            log_warning(f"ReadTimeout: {e}. Повтор через {delay} сек.", module='Telegram')
            time.sleep(delay)
            delay = min(delay * 2, 300)  # увеличиваем задержку до 5 минут максимум
        except KeyboardInterrupt:
            log_warning("Получен сигнал прерывания в Telegram боте", module='Telegram')
            break
        except Exception as e:
            if stop_bot:
                break
            import traceback
            log_error(f"Ошибка в Telegram боте: {e}", module='Telegram')
            traceback.print_exc()
            time.sleep(delay)
            delay = min(delay * 2, 300)
        else:
            delay = 5  # если всё прошло хорошо, сбрасываем задержку

def check_configuration():
    """Проверка конфигурации приложения"""
    log_info("🔍 Проверка конфигурации...", module='CORE')
    
    # Проверка токена Telegram
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN":
        log_error("❌ Не установлен токен Telegram бота в config.ini", module='CORE')
        log_error("   Добавьте ваш токен в секцию [telegram] -> token", module='CORE')
        os._exit(1)
    
    # Проверка файлов данных
    try:
        # Проверяем, что можем создать/записать в файлы
        test_content = "test"
        with open(AUTHORIZED_USERS_FILE, 'a') as f:
            f.write("")
        with open(USER_FILTERS_FILE, 'a') as f:
            f.write("")
    except Exception as e:
        log_error(f"❌ Ошибка доступа к файлам данных: {e}", module='CORE')
        os._exit(1)
    
    log_info("✅ Конфигурация корректна", module='CORE')

def check_smtp_server():
    """Проверка SMTP сервера"""
    import socket
    
    # Проверяем, что порт 1025 свободен
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', 1025))
        sock.close()
        
        if result == 0:
            log_error("❌ Порт 1025 уже занят другим процессом", module='SMTP')
            log_error("   Остановите другие приложения, использующие порт 1025", module='SMTP')
            os._exit(1)
    except Exception as e:
        log_error(f"❌ Ошибка проверки порта SMTP: {e}", module='SMTP')
        os._exit(1)

def check_telegram_bot():
    """Проверка подключения к Telegram API"""
    try:
        # Пробуем получить информацию о боте
        bot_info = bot.get_me()
        log_info(f"✅ Подключение к Telegram API: @{bot_info.username}", module='Telegram')
    except Exception as e:
        log_error(f"❌ Ошибка подключения к Telegram API: {e}", module='Telegram')
        log_error("   Проверьте токен бота и интернет-соединение", module='Telegram')
        os._exit(1)

def main():
    # Логотип без боковых рамок
    logo_art = f"""
{Fore.CYAN}╔════════════════════════════════════════════════════════════════╗
   OrionEventsToTelegram
  🚀 Мониторинг событий УРВ → Telegram Bot
  📧 SMTP: localhost:1025
  📊 Логирование: {LOGGING_LEVEL}
╚════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
    print(logo_art)
    log_info("🚀 Запуск приложения OrionEventsToTelegram...", module='CORE')
    
    # Проверки конфигурации и модулей
    check_configuration()
    check_smtp_server()
    
    # Устанавливаем обработчик сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Создаем папку db если её нет
    if not os.path.exists('db'):
        os.makedirs('db')
        log_info("📁 Папка db создана", module='CORE')
    
    # Создаем файлы данных если их нет
    if not os.path.exists(AUTHORIZED_USERS_FILE):
        with open(AUTHORIZED_USERS_FILE, 'w', encoding='utf-8') as f:
            pass  # Создаем пустой файл
        log_info(f"📄 Файл {AUTHORIZED_USERS_FILE} создан", module='CORE')
    
    if not os.path.exists(USER_FILTERS_FILE):
        with open(USER_FILTERS_FILE, 'w', encoding='utf-8') as f:
            pass  # Создаем пустой файл
        log_info(f"📄 Файл {USER_FILTERS_FILE} создан", module='CORE')
    
    smtp_thread = threading.Thread(target=start_smtp_server)
    smtp_thread.daemon = True  # Поток завершится при закрытии основного потока
    smtp_thread.start()

    # Удаляем поток проверки ввода, так как он создает конфликты

    try:
        # Небольшая задержка для запуска SMTP сервера
        time.sleep(1)
        
        start_telegram_bot()  # Запускаем бота в основном потоке
    except KeyboardInterrupt:
        log_warning("Получен сигнал CTRL-C (KeyboardInterrupt). Завершение работы...", module='CORE')
        # Устанавливаем флаг для завершения бота
        global stop_bot
        stop_bot = True
        # Останавливаем бота
        try:
            bot.stop_polling()
        except:
            pass
        log_info("Приложение корректно завершено", module='CORE')
        os._exit(0)  # Принудительное завершение

if __name__ == '__main__':
    main()
