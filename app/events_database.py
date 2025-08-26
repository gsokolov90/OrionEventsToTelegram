"""
Модуль для работы с базой данных событий SQLite
"""

import os
import sqlite3
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import threading
import time
# Простые функции логирования для Windows
def log_info(message, module='EventsDatabase'):
    print(f"[INFO] {module}: {message}")

def log_error(message, module='EventsDatabase'):
    print(f"[ERROR] {module}: {message}")

def log_debug(message, module='EventsDatabase'):
    print(f"[DEBUG] {module}: {message}")

def log_warning(message, module='EventsDatabase'):
    print(f"[WARNING] {module}: {message}")

# Пытаемся получить логгер только для Unix систем
logger = None
if os.name != 'nt':  # Не Windows
    try:
        from logger import get_logger
        logger = get_logger('EventsDatabase')
        # Переопределяем функции если логгер доступен
        def log_info(message, module='EventsDatabase'):
            logger.info(message)
        def log_error(message, module='EventsDatabase'):
            logger.error(message)
        def log_debug(message, module='EventsDatabase'):
            logger.debug(message)
        def log_warning(message, module='EventsDatabase'):
            logger.warning(message)
    except ImportError:
        pass  # Используем простые функции


class EventsDatabaseManager:
    """Менеджер базы данных событий с автоматическим созданием схемы"""
    
    def __init__(self, db_path: str):
        print(f"[DEBUG] EventsDatabase: EventsDatabaseManager.__init__ called with path: {db_path}")
        self.db_path = db_path
        print("[DEBUG] EventsDatabase: Calling _ensure_database_exists...")
        self._ensure_database_exists()
        print("[DEBUG] EventsDatabase: _ensure_database_exists completed")
    
    def _ensure_database_exists(self) -> None:
        """Создает базу данных и таблицы если их нет"""
        # Проверяем, что база данных создается в правильном месте
        # Если путь содержит 'app/db', исправляем его на корневую папку db
        if 'app/db' in self.db_path:
            corrected_path = self.db_path.replace('app/db', 'db')
            log_info(f"🔄 Исправляем путь базы данных событий: {self.db_path} → {corrected_path}", module='EventsDatabase')
            self.db_path = corrected_path
        
        # Проверяем, существует ли база данных
        if not os.path.exists(self.db_path):
            log_info(f"🗄️  База данных событий не найдена: {self.db_path}", module='EventsDatabase')
            log_info("📝 Создаем новую базу данных событий...", module='EventsDatabase')
        else:
            log_info(f"✅ База данных событий найдена: {self.db_path}", module='EventsDatabase')
        
        # Создаем папку db если её нет
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            log_info(f"📁 Папка {db_dir} создана", module='EventsDatabase')
        
        # Создаем базу данных и таблицы
        self._create_tables()
    
    def _create_tables(self) -> None:
        """Создает все необходимые таблицы"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Новая схема базы данных событий
        schema = {
            'events': '''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_name TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    event_timestamp TIMESTAMP NOT NULL,
                    raw_message TEXT NOT NULL,
                    processed_message TEXT NOT NULL
                )
            '''
        }
        # Создаем таблицы
        for table_name, create_sql in schema.items():
            try:
                cursor.execute(create_sql)
                log_info(f"✅ Таблица событий '{table_name}' готова", module='EventsDatabase')
            except Exception as e:
                log_error(f"Ошибка создания таблицы событий '{table_name}': {e}", module='EventsDatabase')
        conn.commit()
        conn.close()
        log_info(f"✅ База данных событий {self.db_path} инициализирована", module='EventsDatabase')
    
    def get_connection(self) -> sqlite3.Connection:
        """Получение соединения с базой данных"""
        return sqlite3.connect(self.db_path)
    
    def add_event(self, employee_name: str, direction: str, event_timestamp, raw_message: str, processed_message: str) -> bool:
        """Добавление нового события в базу данных (event_timestamp — datetime или unixtime)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            # event_timestamp должен быть строкой в формате ISO или unixtime (int)
            if isinstance(event_timestamp, int):
                ts = datetime.fromtimestamp(event_timestamp).isoformat(sep=' ')
            elif isinstance(event_timestamp, datetime):
                ts = event_timestamp.isoformat(sep=' ')
            else:
                ts = str(event_timestamp)
            cursor.execute("""
                INSERT INTO events (employee_name, direction, event_timestamp, raw_message, processed_message)
                VALUES (?, ?, ?, ?, ?)
            """, (employee_name, direction, ts, raw_message, processed_message))
            conn.commit()
            conn.close()
            log_info(f"✅ Событие добавлено: {employee_name} - {direction} в {ts}", module='EventsDatabase')
            return True
        except Exception as e:
            log_error(f"Ошибка добавления события: {e}", module='EventsDatabase')
            return False
    
    def get_events_by_employee(self, employee_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Получение событий по сотруднику"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, employee_name, direction, event_timestamp, raw_message, processed_message
                FROM events 
                WHERE employee_name LIKE ? 
                ORDER BY event_timestamp DESC 
                LIMIT ?
            """, (f"%{employee_name}%", limit))
            events = []
            for row in cursor.fetchall():
                events.append({
                    'id': row[0],
                    'employee_name': row[1],
                    'direction': row[2],
                    'event_timestamp': row[3],
                    'raw_message': row[4],
                    'processed_message': row[5]
                })
            conn.close()
            return events
        except Exception as e:
            log_error(f"Ошибка получения событий по сотруднику: {e}", module='EventsDatabase')
            return []
    
    def get_events_by_date_range(self, start_date: datetime, end_date: datetime, limit: int = 100) -> List[Dict[str, Any]]:
        """Получение событий по диапазону дат"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, employee_name, direction, event_timestamp, raw_message, processed_message
                FROM events 
                WHERE event_timestamp BETWEEN ? AND ?
                ORDER BY event_timestamp DESC 
                LIMIT ?
            """, (start_date.isoformat(sep=' '), end_date.isoformat(sep=' '), limit))
            events = []
            for row in cursor.fetchall():
                events.append({
                    'id': row[0],
                    'employee_name': row[1],
                    'direction': row[2],
                    'event_timestamp': row[3],
                    'raw_message': row[4],
                    'processed_message': row[5]
                })
            conn.close()
            return events
        except Exception as e:
            log_error(f"Ошибка получения событий по диапазону дат: {e}", module='EventsDatabase')
            return []
    
    def get_events_by_employee_and_period(self, employee_name: str, days: int = 30) -> List[Dict[str, Any]]:
        """Получение событий по сотруднику за последние N дней"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            cursor.execute("""
                SELECT id, employee_name, direction, event_timestamp, raw_message, processed_message
                FROM events 
                WHERE employee_name LIKE ? 
                  AND event_timestamp BETWEEN ? AND ?
                ORDER BY event_timestamp ASC
            """, (f"%{employee_name}%", start_date.isoformat(sep=' '), end_date.isoformat(sep=' ')))
            events = []
            for row in cursor.fetchall():
                events.append({
                    'id': row[0],
                    'employee_name': row[1],
                    'direction': row[2],
                    'event_timestamp': row[3],
                    'raw_message': row[4],
                    'processed_message': row[5]
                })
            conn.close()
            return events
        except Exception as e:
            log_error(f"Ошибка получения событий по сотруднику и периоду: {e}", module='EventsDatabase')
            return []
    
    def cleanup_old_events(self, retention_days: int) -> int:
        """Удаление старых записей событий"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Вычисляем дату, до которой удаляем записи
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            # Получаем количество записей для удаления
            cursor.execute("""
                SELECT COUNT(*) FROM events 
                WHERE event_timestamp < ?
            """, (cutoff_date.isoformat(sep=' '),))
            
            count_to_delete = cursor.fetchone()[0]
            
            if count_to_delete > 0:
                # Удаляем старые записи
                cursor.execute("""
                    DELETE FROM events 
                    WHERE event_timestamp < ?
                """, (cutoff_date.isoformat(sep=' '),))
                
                conn.commit()
                log_info(f"🗑️  Удалено {count_to_delete} старых записей событий (старше {retention_days} дней)", module='EventsDatabase')
            else:
                log_info("✅ Старые записи событий не найдены", module='EventsDatabase')
            
            conn.close()
            return count_to_delete
        except Exception as e:
            log_error(f"Ошибка очистки старых событий: {e}", module='EventsDatabase')
            return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики событий"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Общее количество записей
            cursor.execute("SELECT COUNT(*) FROM events")
            total_events = cursor.fetchone()[0]
            
            # Количество уникальных сотрудников
            cursor.execute("SELECT COUNT(DISTINCT employee_name) FROM events")
            unique_employees = cursor.fetchone()[0]
            
            # Статистика по направлениям
            cursor.execute("""
                SELECT direction, COUNT(*) 
                FROM events 
                GROUP BY direction
            """)
            direction_stats = dict(cursor.fetchall())
            
            # Последнее событие
            cursor.execute("""
                SELECT event_timestamp, employee_name, direction 
                FROM events 
                ORDER BY event_timestamp DESC 
                LIMIT 1
            """)
            last_event = cursor.fetchone()
            
            conn.close()
            
            return {
                'total_events': total_events,
                'unique_employees': unique_employees,
                'direction_stats': direction_stats,
                'last_event': {
                    'event_timestamp': last_event[0],
                    'employee_name': last_event[1],
                    'direction': last_event[2]
                } if last_event else None
            }
        except Exception as e:
            log_error(f"Ошибка получения статистики событий: {e}", module='EventsDatabase')
            return {
                'total_events': 0,
                'unique_employees': 0,
                'direction_stats': {},
                'last_event': None
            }
    
    def get_total_events_count(self) -> int:
        """Получение общего количества событий"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM events")
            count = cursor.fetchone()[0]
            
            conn.close()
            return count
        except Exception as e:
            log_error(f"Ошибка получения количества событий: {e}", module='EventsDatabase')
            return 0


class EventsCleanupScheduler:
    """Планировщик автоматической очистки событий"""
    
    def __init__(self, events_db: EventsDatabaseManager, retention_days: int, 
                 cleanup_time: str = "02:00", enabled: bool = True):
        self.events_db = events_db
        self.retention_days = retention_days
        self.cleanup_time = cleanup_time
        self.enabled = enabled
        self.running = False
        self.cleanup_thread = None
        
        # Парсим время очистки
        try:
            hour, minute = map(int, cleanup_time.split(':'))
            self.cleanup_hour = hour
            self.cleanup_minute = minute
        except ValueError:
            log_error(f"Неверный формат времени очистки: {cleanup_time}. Используется 02:00", module='EventsDatabase')
            self.cleanup_hour = 2
            self.cleanup_minute = 0
    
    def start(self):
        """Запуск планировщика очистки"""
        if not self.enabled:
            log_info("🚫 Автоматическая очистка событий отключена", module='EventsDatabase')
            return
        
        self.running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        log_info(f"🕐 Планировщик очистки событий запущен (время: {self.cleanup_time})", module='EventsDatabase')
    
    def stop(self):
        """Остановка планировщика очистки"""
        if not self.running:
            return
            
        log_info("🛑 Остановка планировщика очистки событий...", module='EventsDatabase')
        self.running = False
        
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            # Ждем завершения потока с таймаутом
            self.cleanup_thread.join(timeout=3)
            
            if self.cleanup_thread.is_alive():
                log_warning("⚠️  Поток планировщика не завершился в течение 3 секунд", module='EventsDatabase')
            else:
                log_info("✅ Поток планировщика успешно завершен", module='EventsDatabase')
        
        log_info("🛑 Планировщик очистки событий остановлен", module='EventsDatabase')
    
    def _cleanup_loop(self):
        """Основной цикл планировщика"""
        while self.running:
            try:
                now = datetime.now()
                
                # Проверяем, нужно ли запустить очистку
                if (now.hour == self.cleanup_hour and 
                    now.minute == self.cleanup_minute):
                    
                    log_info("🧹 Запуск автоматической очистки старых событий...", module='EventsDatabase')
                    deleted_count = self.events_db.cleanup_old_events(self.retention_days)
                    
                    if deleted_count > 0:
                        log_info(f"✅ Очистка завершена: удалено {deleted_count} записей", module='EventsDatabase')
                    else:
                        log_info("✅ Очистка завершена: записи для удаления не найдены", module='EventsDatabase')
                    
                    # Ждем минуту, чтобы не запустить очистку повторно
                    # Используем более короткие интервалы для быстрого реагирования на остановку
                    for _ in range(60):
                        if not self.running:
                            break
                        time.sleep(1)
                else:
                    # Проверяем каждую минуту, но с более короткими интервалами
                    for _ in range(60):
                        if not self.running:
                            break
                        time.sleep(1)
                    
            except Exception as e:
                log_error(f"Ошибка в планировщике очистки: {e}", module='EventsDatabase')
                # При ошибке ждем 5 минут, но с проверкой остановки
                for _ in range(300):
                    if not self.running:
                        break
                    time.sleep(1)


def init_events_database(db_path: str) -> EventsDatabaseManager:
    """Инициализация базы данных событий"""
    print(f"[DEBUG] EventsDatabase: init_events_database called with path: {db_path}")
    try:
        print("[DEBUG] EventsDatabase: Creating EventsDatabaseManager...")
        events_db_manager = EventsDatabaseManager(db_path)
        print("[DEBUG] EventsDatabase: EventsDatabaseManager created successfully")
        return events_db_manager
    except Exception as e:
        print(f"[DEBUG] EventsDatabase: Error creating EventsDatabaseManager: {e}")
        import traceback
        traceback.print_exc()
        raise 