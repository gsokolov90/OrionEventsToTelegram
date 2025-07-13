"""
OrionEventsToTelegram - Основной модуль приложения (упрощенная версия)

Рефакторенная версия с модульной архитектурой
"""

import threading
import signal
import time
import os

import telebot
import requests
from aiosmtpd.controller import Controller
from aiosmtpd.handlers import Message
from colorama import Fore, Style

from .config import get_telegram_token, get_authorized_users_file, get_user_filters_file, get_logging_level
from .logger import setup_logger, log_info, log_warning, log_error, log_telegram, log_smtp
from .user_manager import UserManager
from .message_processor import MessageProcessor
from .system_init import SystemInitializer, get_version


class OrionEventsApp:
    """Основной класс приложения"""
    
    def __init__(self):
        self.stop_bot = False
        self.bot = None
        self.smtp_controller = None
        self.user_manager = None
        self.message_processor = None
        self.system_init = None
        
    def setup_components(self):
        """Настройка компонентов приложения"""
        try:
            # Инициализация системы
            self.system_init = SystemInitializer()
            
            # Создание бота
            self.bot = telebot.TeleBot(self.system_init.telegram_token)
            
            # Инициализация системы
            if not self.system_init.initialize_system(self.bot):
                return False
            
            # Создание менеджера пользователей
            self.user_manager = UserManager(
                self.system_init.authorized_users_file,
                self.system_init.user_filters_file
            )
            
            # Создание процессора сообщений
            self.message_processor = MessageProcessor()
            
            # Настройка обработчиков сигналов
            self.system_init.setup_signal_handlers(self.signal_handler)
            
            return True
            
        except Exception as e:
            log_error(f"Ошибка настройки компонентов: {e}", module='CORE')
            return False
    
    def signal_handler(self, signum, frame):
        """Обработчик сигналов для корректного завершения"""
        # Проверяем, был ли уже запрос на выход
        if hasattr(self, '_exit_requested'):
            log_warning("Подтверждено завершение работы...", module='CORE')
            self.stop_bot = True
            # Останавливаем бота
            try:
                if self.bot:
                    self.bot.stop_polling()
            except:
                pass
            log_info("Приложение завершено", module='CORE')
            os._exit(0)  # Принудительное завершение
        else:
            # Первый запрос на выход
            self._exit_requested = True
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
                if hasattr(self, '_exit_requested'):
                    delattr(self, '_exit_requested')
                    print(f"{Fore.GREEN}[INFO] Выход отменен{Style.RESET_ALL}")
            
            threading.Thread(target=reset_flag, daemon=True).start()
    
    def setup_telegram_handlers(self):
        """Настройка обработчиков Telegram"""
        
        @self.bot.message_handler(commands=['auth'])
        def handle_auth(message):
            log_telegram(f"Попытка авторизации от пользователя {message.from_user.id}")
            if message.text.strip() == '/auth 68233334':
                user_id = message.from_user.id
                if self.user_manager.add_authorized_user(user_id):
                    self.bot.reply_to(message, "Вы успешно авторизованы!")
                else:
                    self.bot.reply_to(message, "Вы уже авторизованы.")
            else:
                log_warning(f"Неудачная попытка авторизации от пользователя {message.from_user.id}", module='Telegram')
                self.bot.reply_to(message, "Неверный код авторизации.")

        @self.bot.message_handler(commands=['filter'])
        def handle_filter(message):
            log_telegram(f"Установка фильтра от пользователя {message.from_user.id}")
            args = message.text.split(maxsplit=1)
            if len(args) == 2:
                flt = args[1].strip()
                if self.user_manager.set_user_filter(message.from_user.id, flt):
                    self.bot.reply_to(message, f"Фильтр установлен: {flt}")
                else:
                    self.bot.reply_to(message, "Ошибка установки фильтра.")
            else:
                log_warning(f"Некорректная команда фильтра от пользователя {message.from_user.id}", module='Telegram')
                self.bot.reply_to(message, "Используйте: /filter фамилия или часть фамилии сотрудника")

        @self.bot.message_handler(commands=['unfilter'])
        def handle_unfilter(message):
            log_telegram(f"Отключение фильтра от пользователя {message.from_user.id}")
            if self.user_manager.remove_user_filter(message.from_user.id):
                self.bot.reply_to(message, "Фильтр отключен. Теперь вы будете получать все сообщения.")
            else:
                self.bot.reply_to(message, "У вас не было установлено фильтра.")

        @self.bot.message_handler(func=lambda message: True)
        def handle_all_messages(message):
            log_telegram(f"Получено сообщение от пользователя {message.from_user.id}: {message.text}")

    def start_smtp_server(self):
        """Запуск SMTP сервера"""
        class SMTPHandler(Message):
            def __init__(self, app_instance):
                super().__init__()
                self.app = app_instance
            
            def handle_message(self, message):
                try:
                    # Извлекаем текст сообщения
                    if hasattr(message, 'get_body'):
                        body = message.get_body()
                    else:
                        body = message.get_payload()
                    
                    if isinstance(body, list):
                        body = body[0] if body else ""
                    
                    if hasattr(body, 'get_payload'):
                        text = body.get_payload()
                    else:
                        text = str(body)
                    
                    # Обрабатываем сообщение
                    if self.app.message_processor.is_valid_orion_message(text):
                        formatted_message = self.app.message_processor.format_message_for_telegram(text)
                        
                        # Отправляем всем авторизованным пользователям
                        authorized_users = self.app.user_manager.get_authorized_users()
                        for user_id in authorized_users:
                            if self.app.user_manager.should_send_message(user_id, text):
                                try:
                                    self.app.bot.send_message(user_id, formatted_message, parse_mode='Markdown')
                                    log_smtp(f"Сообщение отправлено пользователю {user_id}")
                                except Exception as e:
                                    log_error(f"Ошибка отправки сообщения пользователю {user_id}: {e}", module='SMTP')
                        else:
                            log_smtp(f"Получено сообщение от ОРИОН: {text[:100]}...")
                    else:
                        log_smtp(f"Получено невалидное сообщение: {text[:100]}...")
                        
                except Exception as e:
                    log_error(f"Ошибка обработки SMTP сообщения: {e}", module='SMTP')
        
        # Создаем обработчик с ссылкой на экземпляр приложения
        handler = SMTPHandler(self)
        
        # Запускаем SMTP сервер
        self.smtp_controller = Controller(handler, hostname='localhost', port=1025)
        self.smtp_controller.start()
        log_info("✅ SMTP сервер запущен на localhost:1025", module='SMTP')

    def start_telegram_bot(self):
        """Запуск Telegram бота"""
        self.setup_telegram_handlers()
        log_info("✅ Telegram бот запущен", module='Telegram')
        
        # Сообщение о готовности сервера после запуска всех модулей
        log_info("📧 SMTP сервер слушает на localhost:1025", module='SMTP')
        log_info("🤖 Telegram бот активен и готов к работе", module='Telegram')
        log_info("🚀 Сервер готов и работает! Все модули запущены успешно.", module='CORE')
        log_info("⏳ Ожидание входящих сообщений от ОРИОН...", module='CORE')
        
        delay = 5  # стартовая задержка между попытками (сек)
        
        while not self.stop_bot:
            try:
                # Используем более короткий timeout для быстрого реагирования на сигналы
                self.bot.infinity_polling(timeout=10, long_polling_timeout=10, skip_pending=True)
            except requests.exceptions.ReadTimeout as e:
                if self.stop_bot:
                    break
                log_warning(f"ReadTimeout: {e}. Повтор через {delay} сек.", module='Telegram')
                time.sleep(delay)
                delay = min(delay * 2, 300)  # увеличиваем задержку до 5 минут максимум
            except KeyboardInterrupt:
                log_warning("Получен сигнал прерывания в Telegram боте", module='Telegram')
                break
            except Exception as e:
                if self.stop_bot:
                    break
                import traceback
                log_error(f"Ошибка в Telegram боте: {e}", module='Telegram')
                traceback.print_exc()
                time.sleep(delay)
                delay = min(delay * 2, 300)
            else:
                delay = 5  # если всё прошло хорошо, сбрасываем задержку

    def run(self):
        """Запуск приложения"""
        # Получаем версию приложения
        version = get_version()
        
        # Логотип без боковых рамок
        logo_art = f"""
{Fore.CYAN}╔════════════════════════════════════════════════════════════════╗
   OrionEventsToTelegram v{version}
  🚀 Мониторинг событий УРВ → Telegram Bot
  📧 SMTP: localhost:1025
  📊 Логирование: {self.system_init.logging_level if self.system_init else 'UNKNOWN'}
╚════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
        print(logo_art)
        log_info("🚀 Запуск приложения OrionEventsToTelegram...", module='CORE')
        
        # Настройка компонентов
        if not self.setup_components():
            log_error("❌ Ошибка инициализации компонентов", module='CORE')
            return False
        
        # Запуск SMTP сервера в отдельном потоке
        smtp_thread = threading.Thread(target=self.start_smtp_server)
        smtp_thread.daemon = True
        smtp_thread.start()

        try:
            # Небольшая задержка для запуска SMTP сервера
            time.sleep(1)
            
            # Запуск Telegram бота в основном потоке
            self.start_telegram_bot()
            
        except KeyboardInterrupt:
            log_warning("Получен сигнал CTRL-C (KeyboardInterrupt). Завершение работы...", module='CORE')
            self.stop_bot = True
            try:
                if self.bot:
                    self.bot.stop_polling()
            except:
                pass
            log_info("Приложение корректно завершено", module='CORE')
            os._exit(0)
        
        return True


def main():
    """Точка входа в приложение"""
    app = OrionEventsApp()
    app.run()


if __name__ == '__main__':
    main() 