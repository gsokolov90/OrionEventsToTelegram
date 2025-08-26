import sys
import os

# Добавляем родительскую директорию в sys.path для работы относительных импортов
if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import threading
import logging
import signal
from aiosmtpd.controller import Controller
from aiosmtpd.handlers import Message
from email.message import EmailMessage
import telebot
import re
from colorama import init, Fore, Style
from datetime import datetime
import time
import requests
import urllib3
from user_manager import UserManager
from database import init_database
from events_database import init_events_database, EventsCleanupScheduler
from config import get_telegram_token, get_logging_level, get_admin_ids, get_users_database_path, get_events_database_path, get_events_retention_days, get_cleanup_enabled, get_cleanup_time, get_logging_backup_logs_count

def get_version():
    """Читает версию из файла VERSION"""
    try:
        # Пытаемся найти файл VERSION в текущей или родительской директории
        version_paths = ['VERSION', '../VERSION', '../../VERSION']
        for path in version_paths:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read().strip()
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
    os.system('title OrionEventsToTelegram - Мониторинг УРВ')

# Инициализация colorama для Windows
init()

# Получаем токен из переменных окружения
TELEGRAM_BOT_TOKEN = get_telegram_token()
ADMIN_IDS = get_admin_ids()
DATABASE_PATH = get_users_database_path()



# Получаем уровень логирования из конфигурации
LOGGING_LEVEL = get_logging_level()

# Импортируем функции логирования (инициализация будет в main)
from logger import log_info, log_warning, log_error, log_debug, log_telegram, log_smtp

# Удаляю глобальное создание bot
# bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# Глобальная переменная для контроля завершения бота
stop_bot = False

# Глобальная переменная для менеджера пользователей
user_manager = None

# Глобальная переменная для планировщика очистки событий
events_cleanup_scheduler = None

# Удаляем функцию check_user_input, так как она создает конфликты

def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    global stop_bot, events_cleanup_scheduler
    
    # Проверяем, был ли уже запрос на выход
    if hasattr(signal_handler, 'exit_requested'):
        log_warning("Подтверждено завершение работы...", module='CORE')
        stop_bot = True
        
        # Останавливаем планировщик очистки событий с таймаутом
        if events_cleanup_scheduler:
            try:
                log_info("🛑 Остановка планировщика очистки событий...", module='CORE')
                events_cleanup_scheduler.stop()
                log_info("✅ Планировщик очистки событий остановлен", module='CORE')
            except Exception as e:
                log_error(f"❌ Ошибка остановки планировщика очистки: {e}", module='CORE')
        
        # Небольшая пауза для завершения потоков
        time.sleep(0.5)
        
        log_info("✅ Приложение завершено", module='CORE')
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
  │  [Ожидание 3 сек] ──→ Отменить                           │
  │                                                          │
  ╰──────────────────────────────────────────────────────────╯
╚════════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
        print(confirmation_art)
        
        # Сбрасываем флаг через 3 секунды (уменьшено с 5 до 3)
        def reset_flag():
            time.sleep(3)
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
    def __init__(self, bot=None, user_manager=None, events_db=None):
        super().__init__()
        self.bot = bot
        self.user_manager = user_manager
        self.events_db = events_db
    
    def handle_message(self, message):
        log_smtp("📧 Получено новое email сообщение")
        log_debug("DEBUG: Начало обработки SMTP сообщения", module='SMTP')
        
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
        log_debug(f"📧 Полное содержимое email: {body}", module='SMTP')
        
        # Сохраняем событие в базу данных
        if self.events_db:
            try:
                # Парсим дату и время события
                dt_match = re.match(r'(\d{2}\.\d{2}\.\d{4}) (\d{2}:\d{2}:\d{2})', body)
                event_date = dt_match.group(1) if dt_match else None
                event_time = dt_match.group(2) if dt_match else None
                direction_match = re.search(r'режим:(\S+)', body)
                direction = direction_match.group(1) if direction_match else ""
                
                # Создаем обработанное сообщение для Telegram
                processed_message = process_string(body)
                
                # Сохраняем в базу данных
                if employee_name and direction and event_date and event_time:
                    from datetime import datetime
                    try:
                        event_timestamp = datetime.strptime(f"{event_date} {event_time}", "%d.%m.%Y %H:%M:%S")
                    except Exception:
                        event_timestamp = datetime.now()
                    success = self.events_db.add_event(
                        employee_name=employee_name,
                        direction=direction,
                        event_timestamp=event_timestamp,
                        raw_message=body,
                        processed_message=processed_message
                    )
                    if success:
                        log_info(f"💾 Событие сохранено в базу данных: {employee_name} - {direction}", module='EventsDatabase')
                    else:
                        log_error(f"❌ Ошибка сохранения события в базу данных: {employee_name}", module='EventsDatabase')
                else:
                    log_warning(f"⚠️  Неполные данные для сохранения события: сотрудник='{employee_name}', направление='{direction}', дата='{event_date}', время='{event_time}'", module='EventsDatabase')
            except Exception as e:
                log_error(f"❌ Ошибка обработки события для базы данных: {e}", module='EventsDatabase')
        
        # Отправляем только тело сообщения в Telegram
        msg_text = body
        log_debug("DEBUG: Подготовка к отправке в Telegram", module='SMTP')

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

def start_smtp_server(bot=None, user_manager=None, events_db=None):
    log_info("🚀 Запуск SMTP сервера...", module='SMTP')
    log_debug("DEBUG: Инициализация SMTP сервера", module='SMTP')
    
    # Отключаем логи aiosmtpd если не в DEBUG режиме
    if LOGGING_LEVEL != 'DEBUG':
        import logging
        logging.getLogger('aiosmtpd').setLevel(logging.ERROR)
        logging.getLogger('aiosmtpd.smtp').setLevel(logging.ERROR)
        logging.getLogger('aiosmtpd.controller').setLevel(logging.ERROR)
        logging.getLogger('aiosmtpd.handlers').setLevel(logging.ERROR)
    else:
        log_debug("DEBUG: aiosmtpd логи включены", module='SMTP')
    
    handler = SMTPHandler(bot, user_manager, events_db)
    controller = Controller(handler, hostname='127.0.0.1', port=1025)
    
    try:
        controller.start()
        log_info("✅ SMTP сервер запущен на localhost:1025", module='SMTP')
        # Держим поток активным
        while True:
            time.sleep(1)  # Небольшая пауза для снижения нагрузки на CPU
    except KeyboardInterrupt:
        log_warning("Получен сигнал прерывания, остановка SMTP сервера...", module='SMTP')
    except Exception as e:
        log_error(f"Ошибка в SMTP сервере: {e}", module='SMTP')
    finally:
        try:
            controller.stop()
            log_info("SMTP сервер остановлен", module='SMTP')
        except Exception as e:
            log_error(f"Ошибка при остановке SMTP сервера: {e}", module='SMTP')

def clear_bot_menu(bot):
    """Очищает бургер меню бота"""
    try:
        # Принудительно удаляем все команды
        bot.delete_my_commands()
        # Также очищаем команды для всех языков
        bot.delete_my_commands(scope=None, language_code=None)
        log_info("🧹 Бургер меню очищено", module='Telegram')
    except Exception as e:
        log_error(f"❌ Ошибка очистки бургер меню: {e}", module='Telegram')

def set_authorized_menu(bot):
    """Устанавливает бургер меню для авторизованных пользователей"""
    try:
        from telebot.types import BotCommand
        
        commands = [
            BotCommand("report", "📊 Сформировать отчет по сотруднику"),
            BotCommand("filter", "🔍 Установить фильтр по фамилии"),
            BotCommand("unfilter", "❌ Отключить фильтр"),
            BotCommand("start", "🔄 Перезапуск бота")
        ]
        
        # Сначала очищаем все команды
        bot.delete_my_commands()
        bot.delete_my_commands(scope=None, language_code=None)
        
        # Затем устанавливаем новые команды
        bot.set_my_commands(commands, scope=None, language_code=None)
        
        # Принудительно обновляем для всех языков
        for lang_code in ['ru', 'en']:
            try:
                bot.set_my_commands(commands, scope=None, language_code=lang_code)
            except Exception:
                pass  # Игнорируем ошибки для конкретных языков
        
        log_info("✅ Бургер меню для авторизованных пользователей установлено", module='Telegram')
    except Exception as e:
        log_error(f"❌ Ошибка установки бургер меню: {e}", module='Telegram')

def start_telegram_bot(bot, user_manager):
    log_info("🤖 Запуск Telegram бота...", module='Telegram')
    
    # Проверка подключения к Telegram API
    check_telegram_bot(bot)
    
    # Очищаем бургер меню при старте
    clear_bot_menu(bot)
    
    # Проверяем, что команды действительно очищены
    try:
        current_commands = bot.get_my_commands()
        if current_commands:
            log_warning(f"⚠️  Обнаружены старые команды: {[cmd.command for cmd in current_commands]}", module='Telegram')
        else:
            log_info("✅ Команды успешно очищены", module='Telegram')
    except Exception as e:
        log_error(f"❌ Ошибка проверки команд: {e}", module='Telegram')
    
    @bot.message_handler(commands=['start'])
    def handle_start(message):
        user_id = message.from_user.id
        log_telegram(f"Команда /start от пользователя {user_id}")
        
        if user_manager.is_authorized(user_id):
            # Для авторизованных пользователей - перезапуск бота
            bot.reply_to(message, "🔄 Бот перезапущен! Используйте команды из меню для работы.")
            # Устанавливаем меню для авторизованного пользователя
            set_authorized_menu(bot)
            
            # Проверяем установку команд
            try:
                current_commands = bot.get_my_commands()
                log_info(f"📋 Установленные команды: {[cmd.command for cmd in current_commands]}", module='Telegram')
            except Exception as e:
                log_error(f"❌ Ошибка проверки установленных команд: {e}", module='Telegram')
        else:
            # Для неавторизованных пользователей - приветствие
            welcome_text = (
                "👋 Добро пожаловать в систему мониторинга УРВ!\n\n"
                "Для получения уведомлений о событиях УРВ необходимо авторизоваться.\n"
                "Используйте команду /auth для запроса авторизации."
            )
            bot.reply_to(message, welcome_text)

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
                # Устанавливаем бургер меню для авторизованного пользователя
                set_authorized_menu(bot)
                
                # Проверяем установку команд
                try:
                    current_commands = bot.get_my_commands()
                    log_info(f"📋 Установленные команды после добавления пользователя: {[cmd.command for cmd in current_commands]}", module='Telegram')
                except Exception as e:
                    log_error(f"❌ Ошибка проверки установленных команд: {e}", module='Telegram')
            else:
                bot.reply_to(message, f"Пользователь {target_user_id} уже авторизован или произошла ошибка.")
                
        except ValueError:
            bot.reply_to(message, "Неверный формат ID пользователя. Используйте только цифры.")
        except Exception as e:
            log_error(f"Ошибка добавления пользователя: {e}", module='Telegram')
            bot.reply_to(message, "Произошла ошибка при добавлении пользователя.")

    @bot.message_handler(commands=['update_menu'])
    def handle_update_menu(message):
        user_id = message.from_user.id
        
        # Проверяем права администратора
        if not is_admin(user_id):
            bot.reply_to(message, "У вас нет прав для выполнения этой команды.")
            return
        
        try:
            # Принудительно обновляем меню
            clear_bot_menu(bot)
            set_authorized_menu(bot)
            
            # Проверяем результат
            current_commands = bot.get_my_commands()
            command_list = [cmd.command for cmd in current_commands]
            
            bot.reply_to(message, f"✅ Меню обновлено!\n\nУстановленные команды: {', '.join(command_list)}")
            log_info(f"Меню принудительно обновлено администратором {user_id}", module='Telegram')
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка обновления меню: {e}")
            log_error(f"Ошибка принудительного обновления меню: {e}", module='Telegram')

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
                # Устанавливаем бургер меню для авторизованного пользователя
                set_authorized_menu(bot)
                
                # Проверяем установку команд
                try:
                    current_commands = bot.get_my_commands()
                    log_info(f"📋 Установленные команды после авторизации: {[cmd.command for cmd in current_commands]}", module='Telegram')
                except Exception as e:
                    log_error(f"❌ Ошибка проверки установленных команд: {e}", module='Telegram')
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

    @bot.message_handler(commands=['report'])
    def handle_report(message):
        args = message.text.split(maxsplit=1)
        if len(args) != 2:
            bot.reply_to(message, "Используйте: /report <фамилия или часть фамилии>")
            return
        surname = args[1].strip()
        
        # Получаем полное имя сотрудника из базы данных
        from app.config import get_events_database_path
        from app.events_database import EventsDatabaseManager
        db_path = get_events_database_path()
        events_db = EventsDatabaseManager(db_path)
        full_name = get_full_employee_name(events_db, surname)
        
        if not full_name:
            bot.reply_to(message, f"Сотрудник с фамилией '{surname}' не найден в базе данных.")
            return
        
        from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("1 месяц", callback_data=f"report_period:{surname}:30"),
            InlineKeyboardButton("3 месяца", callback_data=f"report_period:{surname}:90"),
            InlineKeyboardButton("6 месяцев", callback_data=f"report_period:{surname}:180")
        )
        bot.reply_to(message, f"Выберите период для отчета по сотруднику: {full_name}", reply_markup=keyboard)

    @bot.callback_query_handler(func=lambda call: call.data.startswith('report_period:'))
    def handle_report_period(call):
        try:
            _, surname, days = call.data.split(':')
            days = int(days)
        except Exception:
            bot.answer_callback_query(call.id, "Ошибка выбора периода.")
            return
        bot.answer_callback_query(call.id, "Формирую отчет...")
        # Получаем путь к БД событий
        from app.config import get_events_database_path
        from app.events_database import EventsDatabaseManager
        db_path = get_events_database_path()
        events_db = EventsDatabaseManager(db_path)
        # Получаем полное имя сотрудника из базы данных
        full_surname = get_full_employee_name(events_db, surname)
        events = events_db.get_events_by_employee_and_period(full_surname, days)
        if not events:
            bot.send_message(call.message.chat.id, f"Нет событий по сотруднику '{full_surname}' за выбранный период.")
            return
        # Генерируем HTML-отчет
        html_content = generate_html_report(events, full_surname, days)
        # Определяем дату конца периода для имени файла
        from datetime import datetime
        events_sorted = sorted(events, key=lambda e: e['event_timestamp'])
        if events_sorted:
            last_event = events_sorted[-1]
            ts = last_event['event_timestamp']
            if isinstance(ts, str):
                try:
                    ts_dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    ts_dt = datetime.fromisoformat(ts)
            else:
                ts_dt = ts
            date_to = ts_dt.date()
        else:
            from datetime import date as dtdate
            date_to = dtdate.today()
        filename = get_report_filename(full_surname, days, date_to)
        # Сохраняем во временный файл
        import tempfile
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.html', encoding='utf-8') as tmp:
            tmp.write(html_content)
            tmp_path = tmp.name
        # Отправляем файл
        with open(tmp_path, 'rb') as f:
            bot.send_document(call.message.chat.id, f, caption=f"ОТЧЕТ УРВ по сотруднику: {full_surname}", visible_file_name=filename)
        # Удаляем временный файл
        import os
        os.remove(tmp_path)

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
            bot.infinity_polling(timeout=5, long_polling_timeout=5, skip_pending=True)
        except requests.exceptions.ReadTimeout as e:
            if stop_bot:
                break
            log_warning(f"ReadTimeout: {e}. Повтор через {delay} сек.", module='Telegram')
            # Используем более короткие интервалы для быстрого реагирования на остановку
            for _ in range(delay):
                if stop_bot:
                    break
                time.sleep(1)
            delay = min(delay * 2, 300)  # увеличиваем задержку до 5 минут максимум
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as e:
            if stop_bot:
                break
            log_warning(f"Проблема с подключением к Telegram API: {e}", module='Telegram')
            log_info("Проверьте интернет-соединение и доступность api.telegram.org", module='Telegram')
            # Используем более короткие интервалы для быстрого реагирования на остановку
            for _ in range(delay):
                if stop_bot:
                    break
                time.sleep(1)
            delay = min(delay * 2, 300)
        except (urllib3.exceptions.ConnectTimeoutError, urllib3.exceptions.NameResolutionError) as e:
            if stop_bot:
                break
            log_warning(f"Ошибка DNS/соединения: {e}", module='Telegram')
            log_info("Проверьте интернет-соединение и DNS", module='Telegram')
            # Используем более короткие интервалы для быстрого реагирования на остановку
            for _ in range(delay):
                if stop_bot:
                    break
                time.sleep(1)
            delay = min(delay * 2, 300)
        except KeyboardInterrupt:
            log_warning("Получен сигнал прерывания в Telegram боте", module='Telegram')
            break
        except Exception as e:
            if stop_bot:
                break
            import traceback
            log_error(f"Неожиданная ошибка в Telegram боте: {e}", module='Telegram')
            if LOGGING_LEVEL == 'DEBUG':
                traceback.print_exc()
            # Используем более короткие интервалы для быстрого реагирования на остановку
            for _ in range(delay):
                if stop_bot:
                    break
                time.sleep(1)
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
        return True
    except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError, 
            urllib3.exceptions.ConnectTimeoutError, urllib3.exceptions.NameResolutionError) as e:
        log_warning(f"⚠️  Проблема с подключением к Telegram API: {e}", module='Telegram')
        log_info("   Приложение запустится, но Telegram бот может не работать", module='Telegram')
        log_info("   Проверьте интернет-соединение и доступность api.telegram.org", module='Telegram')
        return False
    except Exception as e:
        log_error(f"❌ Критическая ошибка подключения к Telegram API: {e}", module='Telegram')
        log_error("   Проверьте токен бота и интернет-соединение", module='Telegram')
        return False

def get_full_employee_name(events_db, surname):
    """Получение полного имени сотрудника из базы данных"""
    try:
        # Получаем уникальные имена сотрудников, содержащие surname
        conn = events_db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT employee_name 
            FROM events 
            WHERE employee_name LIKE ? 
            ORDER BY employee_name
            LIMIT 1
        """, (f"%{surname}%",))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0]  # Возвращаем полное имя из БД
        else:
            return surname  # Если не найдено, возвращаем исходное
    except Exception as e:
        log_error(f"Ошибка получения полного имени сотрудника: {e}", module='EventsDatabase')
        return surname

def generate_html_report(events, surname, days):
    from datetime import datetime, timedelta, date
    from collections import defaultdict, OrderedDict
    import os
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    # Получаем текущее время для подвала
    generation_time = datetime.now().strftime('%d.%m.%Y в %H:%M')
    
    # Преобразуем все event_timestamp к datetime
    for event in events:
        ts = event['event_timestamp']
        if isinstance(ts, str):
            try:
                ts_dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            except Exception:
                ts_dt = datetime.fromisoformat(ts)
        else:
            ts_dt = ts
        event['ts_dt'] = ts_dt
    # Сортируем события по времени
    events_sorted = sorted(events, key=lambda e: e['ts_dt'])
    # Сначала формируем все пары вход-выход
    pairs = []
    incomplete_shifts = []  # Для неполных смен в старых днях
    i = 0
    n = len(events_sorted)
    while i < n:
        ev = events_sorted[i]
        if ev['direction'].lower() == 'вход':
            entry = ev
            entry_date = entry['ts_dt'].date()
            # ищем ближайший выход после входа
            exit_ev = None
            for j in range(i+1, n):
                if events_sorted[j]['direction'].lower() == 'выход':
                    exit_ev = events_sorted[j]
                    break
            if exit_ev:
                # Полная пара вход-выход
                pairs.append((entry, exit_ev))
                i = events_sorted.index(exit_ev, i+1) + 1
            else:
                # Нет выхода
                if entry_date >= yesterday:
                    # Для текущего и вчерашнего дня - пропускаем незавершенные смены
                    i += 1
                else:
                    # Для более старых дней - добавляем как неполную смену
                    incomplete_shifts.append((entry, None))
                    i += 1
        else:
            i += 1
    # Группируем пары по дате входа
    day_blocks = OrderedDict()
    total_in = total_out = work_days = 0
    total_work_time = timedelta()
    weekday_ru = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
    
    # Обрабатываем полные пары
    for entry, exit_ev in pairs:
        entry_date = entry['ts_dt'].date()
        if entry_date not in day_blocks:
            day_blocks[entry_date] = {
                'weekday': entry['ts_dt'].weekday(),
                'work_time': timedelta(),
                'events': [],
                'weekday_str': weekday_ru[entry['ts_dt'].weekday()]
            }
        # Добавляем событие входа
        day_blocks[entry_date]['events'].append({
            'type': 'in', 
            'time': entry['ts_dt'].strftime('%H:%M')
        })
        total_in += 1
        # Добавляем событие выхода
        out_time = exit_ev['ts_dt'].strftime('%H:%M')
        # Проверяем, является ли это ночной сменой
        is_night_shift = exit_ev['ts_dt'].date() != entry['ts_dt'].date()
        day_blocks[entry_date]['events'].append({
            'type': 'out', 
            'time': out_time,
            'is_night_shift': is_night_shift
        })
        total_out += 1
        # Считаем рабочее время
        delta = exit_ev['ts_dt'] - entry['ts_dt']
        if delta.total_seconds() > 0:
            day_blocks[entry_date]['work_time'] += delta
    
    # Обрабатываем неполные смены (только для старых дней)
    for entry, exit_ev in incomplete_shifts:
        entry_date = entry['ts_dt'].date()
        if entry_date not in day_blocks:
            day_blocks[entry_date] = {
                'weekday': entry['ts_dt'].weekday(),
                'work_time': timedelta(),
                'events': [],
                'weekday_str': weekday_ru[entry['ts_dt'].weekday()]
            }
        # Добавляем событие входа с пометкой
        day_blocks[entry_date]['events'].append({
            'type': 'in', 
            'time': entry['ts_dt'].strftime('%H:%M')
        })
        total_in += 1
        # Добавляем пометку о том, что нет выхода
        day_blocks[entry_date]['events'].append({
            'type': 'no_exit', 
            'time': 'Нет выхода'
        })
    
    # Формируем строки времени и статистику
    for d in day_blocks:
        work_time = day_blocks[d]['work_time']
        work_time_str = f"{work_time.seconds//3600}ч {(work_time.seconds%3600)//60}м" if work_time else "-"
        day_blocks[d]['work_time_str'] = work_time_str
        if work_time_str != '-':
            work_days += 1
            try:
                h, m = [int(x[:-1]) for x in work_time_str.split()]
                total_work_time += timedelta(hours=h, minutes=m)
            except Exception:
                pass
    # Сортируем дни по убыванию
    sorted_dates = sorted(day_blocks.keys(), reverse=True)
    # Для периода
    if sorted_dates:
        period_start = min(sorted_dates)
        period_end = max(sorted_dates)
    else:
        period_start = period_end = today
    # Детализация по дням
    details = ""
    for d in sorted_dates:
        block = day_blocks[d]
        events_in_block = block['events']
        work_time_str = block['work_time_str']
        weekday = block['weekday_str']
        details += f"<div class='day-block'>"
        details += f"<div class='day-header-row'><div class='day-header'><svg viewBox='0 0 24 24' fill='none' xmlns='http://www.w3.org/2000/svg'><path d='M19 3H5C3.89 3 3 3.89 3 5V19C3 20.11 3.89 21 5 21H19C20.11 21 21 20.11 21 19V5C21 3.89 20.11 3 19 3M19 19H5V9H19V19M19 7H5V5H19V7Z' fill='currentColor'/></svg>{d.strftime('%d.%m.%Y')} ({weekday})</div><div class='day-time'>{work_time_str}</div></div>"
        details += "<table class='day-table'><tr><th>Время</th><th>Событие</th></tr>"
        for ev in events_in_block:
            if ev['type'] == 'in':
                details += f"<tr><td class='time'><span class='time-value'>{ev['time']}</span></td><td class='event-in'><svg width='16' height='16' viewBox='0 0 24 24' fill='none' xmlns='http://www.w3.org/2000/svg'><path d='M8.59 16.59L13.17 12L8.59 7.41L10 6L16 12L10 18L8.59 16.59Z' fill='currentColor'/></svg>Вход</td></tr>"
            elif ev['type'] == 'out':
                night_shift_mark = ""
                if ev.get('is_night_shift', False):
                    night_shift_mark = "<span class='night-shift'>+1</span>"
                details += f"<tr><td class='time'><span class='time-value'>{ev['time']}</span>{night_shift_mark}</td><td class='event-out'><svg width='16' height='16' viewBox='0 0 24 24' fill='none' xmlns='http://www.w3.org/2000/svg'><path d='M15.41 16.59L10.83 12L15.41 7.41L14 6L8 12L14 18L15.41 16.59Z' fill='currentColor'/></svg>Выход</td></tr>"
            elif ev['type'] == 'no_exit':
                details += f"<tr><td class='time'>-</td><td class='event-no-exit'><svg width='16' height='16' viewBox='0 0 24 24' fill='none' xmlns='http://www.w3.org/2000/svg'><path d='M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2M12 20C7.59 20 4 16.41 4 12C4 7.59 7.59 4 12 4C16.41 4 20 7.59 20 12C20 16.41 16.41 20 12 20M12 6C10.9 6 10 6.9 10 8C10 9.1 10.9 10 12 10C13.1 10 14 9.1 14 8C14 6.9 13.1 6 12 6M12 12C10.9 12 10 12.9 10 14C10 15.1 10.9 16 12 16C13.1 16 14 15.1 14 14C14 12.9 13.1 12 12 12Z' fill='currentColor'/></svg>Нет выхода</td></tr>"
        details += "</table></div>"
    # Среднее время
    avg_work_time = total_work_time / work_days if work_days else timedelta()
    avg_hours = int(avg_work_time.total_seconds() // 3600)
    avg_minutes = int((avg_work_time.total_seconds() % 3600) // 60)
    # Определяем период строкой
    if days == 30:
        period = '1 месяц'
    elif days == 90:
        period = '3 месяца'
    elif days == 180:
        period = '6 месяцев'
    else:
        period = f'{days} дней'
    # Читаем шаблон
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'report_template.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()
    html = template.replace('{{surname}}', surname)
    html = html.replace('{{period}}', f"{period_start.strftime('%d.%m.%Y')} — {period_end.strftime('%d.%m.%Y')}")
    html = html.replace('{{total_in}}', str(total_in))
    html = html.replace('{{total_out}}', str(total_out))
    html = html.replace('{{work_days}}', str(work_days))
    html = html.replace('{{avg_hours}}', str(avg_hours))
    html = html.replace('{{avg_minutes}}', str(avg_minutes))
    html = html.replace('{{details}}', details)
    html = html.replace('{{generation_time}}', generation_time)
    return html

def get_report_filename(surname, days, date_to):
    # date_to — последний день периода (datetime)
    if days == 30:
        period = '1 месяц'
    elif days == 90:
        period = '3 месяца'
    elif days == 180:
        period = '6 месяцев'
    else:
        period = f'{days} дней'
    safe_surname = surname.replace(' ', '_').replace('.', '.')
    date_str = date_to.strftime('%Y-%m-%d')
    return f"{date_str} {surname} отчет УРВ {period}.html"

def main():
    try:
        print("[DEBUG] Step 1: Starting main function...")
        
        # Для Windows используем простой логгер без сложных форматтеров
        if os.name == 'nt':  # Windows
            print("[DEBUG] Step 2: Windows detected, using simple logger...")
            import logging
            # Создаем директорию для логов если её нет
            import os
            log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'log')
            os.makedirs(log_dir, exist_ok=True)
            
            # Создаем простой логгер для Windows
            logging.basicConfig(
                level=logging.DEBUG,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.StreamHandler(),
                    logging.FileHandler(os.path.join(log_dir, 'windows_app.log'), encoding='utf-8')
                ]
            )
            print("[DEBUG] Step 3: Simple Windows logger created")
            
            # Создаем простые функции логирования для Windows
            def simple_log_info(message, module='CORE'):
                print(f"[INFO] {module}: {message}")
                logging.info(f"{module}: {message}")
            
            def simple_log_warning(message, module='CORE'):
                print(f"[WARNING] {module}: {message}")
                logging.warning(f"{module}: {message}")
            
            def simple_log_error(message, module='CORE'):
                print(f"[ERROR] {module}: {message}")
                logging.error(f"{module}: {message}")
            
            def simple_log_debug(message, module='CORE'):
                print(f"[DEBUG] {module}: {message}")
                logging.debug(f"{module}: {message}")
            
            # Заменяем функции логирования
            global log_info, log_warning, log_error, log_debug
            log_info = simple_log_info
            log_warning = simple_log_warning
            log_error = simple_log_error
            log_debug = simple_log_debug
            
            print("[DEBUG] Step 4: Windows logging functions created")
        else:
            # Для Unix систем используем обычный логгер
            print("[DEBUG] Step 2: Unix detected, using normal logger...")
            from logger import setup_logger
            print("[DEBUG] Step 3: Logger imported successfully")
            
            print("[DEBUG] Step 4: Setting up logger...")
            setup_logger(LOGGING_LEVEL)
            print("[DEBUG] Step 5: Logger setup completed")
        
        # Получаем версию приложения
        print("[DEBUG] Step 6: Getting version...")
        version = get_version()
        print(f"[DEBUG] Step 7: Version = {version}")
        
        # Логотип без боковых рамок
        print("[DEBUG] Step 8: Creating logo...")
        logo_art = f"""
{Fore.CYAN}╔════════════════════════════════════════════════════════════════╗
   OrionEventsToTelegram v{version}
  🚀 Мониторинг событий УРВ → Telegram Bot
  📧 SMTP: localhost:1025
  📊 Логирование: {LOGGING_LEVEL}
╚════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
        print("[DEBUG] Step 9: Printing logo...")
        print(logo_art)
        print("[DEBUG] Step 10: Logo printed successfully")
        
        print("[DEBUG] Step 11: Calling log_info...")
        log_info("🚀 Запуск приложения OrionEventsToTelegram...", module='CORE')
        print("[DEBUG] Step 12: log_info completed successfully")
        
        # Проверки конфигурации и модулей
        check_configuration()
        check_smtp_server()
    
        # Создаем бота
        bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
        
        # Проверяем подключение к Telegram API
        telegram_available = check_telegram_bot(bot)
        if not telegram_available:
            log_warning("Telegram бот будет работать в режиме восстановления", module='CORE')
        
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

        # Инициализация базы данных событий
        events_db_path = get_events_database_path()
        events_retention_days = get_events_retention_days()
        cleanup_enabled = get_cleanup_enabled()
        cleanup_time = get_cleanup_time()

        log_info(f"🗄️  Инициализация базы данных событий: {events_db_path}", module='CORE')
        events_db = init_events_database(events_db_path)
        log_info("✅ База данных событий инициализирована", module='CORE')
        
        # Получаем статистику событий
        stats = events_db.get_statistics()
        log_info(f"📊 Статистика событий: {stats['total_events']} записей, {stats['unique_employees']} сотрудников", module='CORE')

        # Инициализация планировщика очистки событий
        global events_cleanup_scheduler
        if cleanup_enabled:
            log_info(f"🧹 Запуск планировщика очистки событий (время: {cleanup_time})", module='CORE')
            events_cleanup_scheduler = EventsCleanupScheduler(events_db, events_retention_days, cleanup_time, cleanup_enabled)
            events_cleanup_scheduler.start()
            log_info("✅ Планировщик очистки событий запущен", module='CORE')
        else:
            log_info("🧹 Планировщик очистки событий отключен в конфигурации.", module='CORE')
            events_cleanup_scheduler = None
        
        # Запускаем SMTP сервер с передачей бота, user_manager и events_db
        smtp_thread = threading.Thread(target=start_smtp_server, args=(bot, user_manager, events_db))
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
            
            # Останавливаем планировщик очистки событий
            if events_cleanup_scheduler:
                try:
                    log_info("🛑 Остановка планировщика очистки событий...", module='CORE')
                    events_cleanup_scheduler.stop()
                    log_info("✅ Планировщик очистки событий остановлен", module='CORE')
                except Exception as e:
                    log_error(f"❌ Ошибка остановки планировщика очистки: {e}", module='CORE')
            
            # Небольшая пауза для завершения потоков
            time.sleep(0.5)
            
            log_info("✅ Приложение корректно завершено", module='CORE')
            os._exit(0)  # Принудительное завершение
        
    except Exception as e:
        print(f"\n{Fore.RED}[CRITICAL ERROR] Критическая ошибка в main(): {e}{Style.RESET_ALL}")
        print(f"{Fore.RED}[CRITICAL ERROR] Тип ошибки: {type(e).__name__}{Style.RESET_ALL}")
        
        # Пытаемся вывести traceback если возможно
        try:
            import traceback
            print(f"\n{Fore.YELLOW}[TRACEBACK]{Style.RESET_ALL}")
            traceback.print_exc()
        except:
            pass
        
        print(f"\n{Fore.RED}Приложение завершилось с ошибкой!{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Проверьте конфигурацию и попробуйте снова.{Style.RESET_ALL}")
        
        # Пауза перед выходом
        input("\nНажмите Enter для выхода...")
        os._exit(1)

if __name__ == '__main__':
    main()
