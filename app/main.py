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
from config import get_telegram_token, get_authorized_users_file, get_user_filters_file, get_logging_level, get_admin_ids, get_database_path, get_logging_backup_logs_count
import time
import requests
from user_manager import UserManager
from database import init_database

def get_version():
    """Читает версию из файла VERSION"""
    try:
        with open('VERSION', 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        return "unknown"
    except Exception:
        return "unknown"

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
ADMIN_IDS = get_admin_ids()
DATABASE_PATH = get_database_path()

# Для обратной совместимости (если нужны старые пути)
try:
    AUTHORIZED_USERS_FILE = get_authorized_users_file()
    USER_FILTERS_FILE = get_user_filters_file()
except RuntimeError:
    AUTHORIZED_USERS_FILE = "db/authorized_users.txt"
    USER_FILTERS_FILE = "db/user_filters.txt"

# Получаем уровень логирования из конфигурации
LOGGING_LEVEL = get_logging_level()

# Инициализируем наш логгер
from logger import setup_logger
logger_instance = setup_logger(LOGGING_LEVEL)

# Настройка логгеров сторонних библиотек уже выполняется в logger.py

# Форматтеры и фильтры уже настроены в logger.py

# Используем наш логгер
from logger import get_logger
logger = get_logger(__name__)

# Удаляю глобальное создание bot
# bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Глобальная переменная для контроля завершения бота
stop_bot = False

# Глобальная переменная для менеджера пользователей
user_manager = None

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
            # bot.stop_polling() # Удалено
            pass
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
    'UserManager': Fore.CYAN,
    'Database': Fore.BLUE,
    'WARNING': Fore.YELLOW,
    'ERROR': Fore.RED,
    'DEBUG': Fore.CYAN
}

# Используем функции логирования из нашего модуля
from logger import log_info, log_warning, log_error, log_debug, log_telegram, log_smtp

def log_message(level, message, module='CORE'):
    """Логирование сообщений с указанием уровня"""
    if level == 'INFO':
        log_info(message, module)
    elif level == 'WARNING':
        log_warning(message, module)
    elif level == 'ERROR':
        log_error(message, module)
    elif level == 'DEBUG':
        log_debug(message, module)

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
    """Получение списка авторизованных пользователей"""
    if user_manager is None:
        return set()
    return user_manager.get_authorized_users()

def get_user_filters():
    """Получение фильтров пользователей"""
    if user_manager is None:
        return {}
    return user_manager.get_user_filters()

def set_user_filter(user_id, flt):
    """Установка фильтра для пользователя"""
    if user_manager is None:
        return False
    return user_manager.set_user_filter(user_id, flt)

def remove_user_filter(user_id):
    """Удаление фильтра пользователя"""
    if user_manager is None:
        return False
    return user_manager.remove_user_filter(user_id)

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

class SMTPHandler(Message):
    def __init__(self, bot=None, user_manager=None):
        super().__init__()
        self.bot = bot
        self.user_manager = user_manager
    
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

        if self.user_manager:
            authorized_users = self.user_manager.get_authorized_users()
        else:
            authorized_users = get_authorized_users()
        
        log_info(f"Отправка сообщения {len(authorized_users)} авторизованным пользователям", module='Telegram')
        log_debug(f"📋 Список авторизованных пользователей: {authorized_users}", module='Telegram')
        
        for user_id in authorized_users:
            try:
                # Проверяем, нужно ли отправлять сообщение пользователю
                if self.user_manager and self.user_manager.should_send_message(user_id, msg_text):
                    if self.bot:
                        self.bot.send_message(user_id, process_string(msg_text))
                        log_info(f"Сообщение отправлено пользователю {user_id}", module='Telegram')
                    else:
                        log_error(f"Бот не инициализирован для отправки сообщения пользователю {user_id}", module='Telegram')
                else:
                    log_info(f"Сообщение отфильтровано для пользователя {user_id}", module='Telegram')
                    
            except Exception as e:
                log_error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}", module='Telegram')

def start_smtp_server(bot=None, user_manager=None):
    log_info("🚀 Запуск SMTP сервера...", module='SMTP')
    
    # Отключаем логи aiosmtpd если не в DEBUG режиме
    if LOGGING_LEVEL != 'DEBUG':
        import logging
        logging.getLogger('aiosmtpd').setLevel(logging.ERROR)
        logging.getLogger('aiosmtpd.smtp').setLevel(logging.ERROR)
        logging.getLogger('aiosmtpd.controller').setLevel(logging.ERROR)
        logging.getLogger('aiosmtpd.handlers').setLevel(logging.ERROR)
    
    handler = SMTPHandler(bot, user_manager)
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

def start_telegram_bot(bot, user_manager):
    log_info("🤖 Запуск Telegram бота...", module='Telegram')
    
    # Проверка подключения к Telegram API
    check_telegram_bot(bot)
    
    @bot.message_handler(commands=['auth'])
    def handle_auth(message):
        user_id = message.from_user.id
        log_telegram(f"Запрос на авторизацию от пользователя {user_id}")
        
        # Проверяем, не авторизован ли уже пользователь
        if user_manager.is_authorized(user_id):
            bot.reply_to(message, "Вы уже авторизованы!")
            return
        
        # Создаем запрос на авторизацию
        request_id = user_manager.create_auth_request(
            user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            request_text="Запрос на авторизацию"
        )
        
        if request_id:
            # Отправляем уведомления администраторам
            for admin_id in ADMIN_IDS:
                try:
                    # Создаем inline клавиатуру
                    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
                    keyboard = InlineKeyboardMarkup()
                    keyboard.add(
                        InlineKeyboardButton("✅ Одобрить", callback_data=f"auth_approve_{request_id}"),
                        InlineKeyboardButton("❌ Отклонить", callback_data=f"auth_reject_{request_id}")
                    )
                    
                    # Формируем сообщение с информацией о пользователе
                    user_info = f"👤 Запрос на авторизацию\n\n"
                    user_info += f"ID: {user_id}\n"
                    if message.from_user.username:
                        user_info += f"Username: @{message.from_user.username}\n"
                    if message.from_user.first_name:
                        user_info += f"Имя: {message.from_user.first_name}\n"
                    if message.from_user.last_name:
                        user_info += f"Фамилия: {message.from_user.last_name}\n"
                    user_info += f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    
                    bot.send_message(admin_id, user_info, reply_markup=keyboard)
                    log_info(f"Уведомление отправлено администратору {admin_id}", module='Telegram')
                except Exception as e:
                    log_error(f"Ошибка отправки уведомления администратору {admin_id}: {e}", module='Telegram')
            
            bot.reply_to(message, "Ваш запрос на авторизацию отправлен администраторам. Ожидайте ответа.")
        else:
            bot.reply_to(message, "Ошибка создания запроса на авторизацию. Попробуйте позже.")

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

    @bot.message_handler(commands=['add_user'])
    def handle_add_user(message):
        user_id = message.from_user.id
        
        # Проверяем права администратора
        if not is_admin(user_id):
            bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
            return
        
        # Парсим команду: /add_user 123456789
        args = message.text.split(maxsplit=1)
        if len(args) != 2:
            bot.reply_to(message, "Используйте: /add_user ID_пользователя")
            return
        
        try:
            target_user_id = int(args[1].strip())
            
            # Добавляем пользователя
            if user_manager is None:
                bot.reply_to(message, "Система управления пользователями недоступна.")
                return
                
            if user_manager.add_authorized_user(target_user_id, added_by=user_id):
                bot.reply_to(message, f"Пользователь {target_user_id} успешно добавлен.")
            else:
                bot.reply_to(message, f"Пользователь {target_user_id} уже авторизован или произошла ошибка.")
                
        except ValueError:
            bot.reply_to(message, "Неверный формат ID пользователя. Используйте только цифры.")
        except Exception as e:
            log_error(f"Ошибка добавления пользователя: {e}", module='Telegram')
            bot.reply_to(message, "Произошла ошибка при добавлении пользователя.")

    @bot.message_handler(commands=['list_users'])
    def handle_list_users(message):
        user_id = message.from_user.id
        
        # Проверяем права администратора
        if not is_admin(user_id):
            bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
            return
        
        if user_manager is None:
            bot.reply_to(message, "Система управления пользователями недоступна.")
            return
            
        users = user_manager.get_all_users_info()
        if not users:
            bot.reply_to(message, "Список авторизованных пользователей пуст.")
            return
        
        response = "📋 Список авторизованных пользователей:\n\n"
        for user in users:
            name = f"{user['first_name'] or ''} {user['last_name'] or ''}".strip() or user['username'] or f"User{user['user_id']}"
            response += f"• {user['user_id']}: {name}\n"
        
        bot.reply_to(message, response)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('auth_'))
    def handle_auth_callback(call):
        user_id = call.from_user.id
        
        # Проверяем права администратора
        if not is_admin(user_id):
            bot.answer_callback_query(call.id, "У вас нет прав для выполнения этой операции.")
            return
        
        # Парсим callback data
        parts = call.data.split('_')
        if len(parts) != 3:
            bot.answer_callback_query(call.id, "Неверный формат callback данных.")
            return
        
        action = parts[1]  # approve или reject
        request_id = int(parts[2])
        
        # Обрабатываем запрос
        if user_manager is None:
            bot.answer_callback_query(call.id, "Система авторизации недоступна.")
            return
        
        # Получаем информацию о запросе ДО его обработки
        target_user_id = user_manager.get_auth_request_user_id(request_id)
        
        approved = (action == 'approve')
        success = user_manager.process_auth_request(request_id, approved, user_id)
        
        if success and target_user_id:
            status_text = "одобрена" if approved else "отклонена"
            notification_text = f"✅ Ваша заявка на авторизацию {status_text}!"
            if approved:
                notification_text += "\n\nТеперь вы можете получать уведомления о событиях УРВ."
            bot.send_message(target_user_id, notification_text)
            
            # Обновляем сообщение администратора
            status_emoji = "✅" if approved else "❌"
            status_text = "одобрена" if approved else "отклонена"
            bot.edit_message_text(
                f"{status_emoji} Заявка {status_text}",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id
            )
            
            bot.answer_callback_query(call.id, f"Заявка {status_text}")
        else:
            bot.answer_callback_query(call.id, "Ошибка обработки заявки. Возможно, она уже обработана.")

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
        log_error("   Добавьте ваш токен в секцию [Telegram] -> bot_token", module='CORE')
        os._exit(1)
    
    # Проверка администраторов
    if not ADMIN_IDS:
        log_warning("⚠️  Не настроены администраторы в config.ini", module='CORE')
        log_warning("   Добавьте ID администраторов в секцию [Admins] -> admin_ids", module='CORE')
    
    # Проверка базы данных
    try:
        # Проверяем, что можем создать/записать в базу данных
        db_dir = os.path.dirname(DATABASE_PATH)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
            log_info(f"📁 Создана папка для базы данных: {db_dir}", module='CORE')
    except Exception as e:
        log_error(f"❌ Ошибка доступа к базе данных: {e}", module='CORE')
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

def check_telegram_bot(bot):
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
    # Получаем версию приложения
    version = get_version()
    
    # Логотип без боковых рамок
    logo_art = f"""
{Fore.CYAN}╔════════════════════════════════════════════════════════════════╗
   OrionEventsToTelegram v{version}
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
    
    # Инициализация базы данных
    log_info("🗄️  Инициализация базы данных...", module='CORE')
    db = init_database(DATABASE_PATH)
    
    # Создаем менеджер пользователей после инициализации БД
    global user_manager
    user_manager = UserManager(db)
    log_info("✅ Менеджер пользователей инициализирован", module='CORE')
    
    # Создаем бота
    bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
    
    # Запускаем SMTP сервер с передачей бота и user_manager
    smtp_thread = threading.Thread(target=start_smtp_server, args=(bot, user_manager))
    smtp_thread.daemon = True  # Поток завершится при закрытии основного потока
    smtp_thread.start()

    # Удаляем поток проверки ввода, так как он создает конфликты

    try:
        # Небольшая задержка для запуска SMTP сервера
        time.sleep(1)
        
        start_telegram_bot(bot, user_manager)  # Запускаем бота в основном потоке
    except KeyboardInterrupt:
        log_warning("Получен сигнал CTRL-C (KeyboardInterrupt). Завершение работы...", module='CORE')
        # Устанавливаем флаг для завершения бота
        global stop_bot
        stop_bot = True
        # Останавливаем бота
        # bot.stop_polling()  # bot теперь локальный в start_telegram_bot
        log_info("Приложение корректно завершено", module='CORE')
        os._exit(0)  # Принудительное завершение

if __name__ == '__main__':
    main()
