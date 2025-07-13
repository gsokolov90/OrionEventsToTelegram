"""
Модуль для работы с базой данных SQLite
"""

import os
import sqlite3
from pathlib import Path
from typing import Optional
try:
    from app.logger import get_logger
    logger = get_logger('Database')
    def log_info(message, module='Database'):
        logger.info(message)
    def log_error(message, module='Database'):
        logger.error(message)
except ImportError:
    # Fallback для прямого запуска файла
    from .logger import get_logger
    logger = get_logger('Database')
    def log_info(message, module='Database'):
        logger.info(message)
    def log_error(message, module='Database'):
        logger.error(message)


class DatabaseManager:
    """Менеджер базы данных с автоматическим созданием схемы"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_database_exists()
    
    def _ensure_database_exists(self) -> None:
        """Создает базу данных и таблицы если их нет"""
        # Проверяем, что база данных создается в правильном месте
        # Если путь содержит 'app/db', исправляем его на корневую папку db
        if 'app/db' in self.db_path:
            corrected_path = self.db_path.replace('app/db', 'db')
            log_info(f"🔄 Исправляем путь базы данных: {self.db_path} → {corrected_path}", module='Database')
            self.db_path = corrected_path
        
        # Проверяем, существует ли база данных
        if not os.path.exists(self.db_path):
            log_info(f"🗄️  База данных не найдена: {self.db_path}", module='Database')
            log_info("📝 Создаем новую базу данных...", module='Database')
        else:
            log_info(f"✅ База данных найдена: {self.db_path}", module='Database')
        
        # Создаем папку db если её нет
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            log_info(f"📁 Папка {db_dir} создана", module='Database')
        
        # Создаем базу данных и таблицы
        self._create_tables()
    
    def _create_tables(self) -> None:
        """Создает все необходимые таблицы"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Схема базы данных
        schema = {
            'authorized_users': '''
                CREATE TABLE IF NOT EXISTS authorized_users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    added_by INTEGER,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'auth_requests': '''
                CREATE TABLE IF NOT EXISTS auth_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    request_text TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_by INTEGER,
                    processed_at TIMESTAMP
                )
            ''',
            'user_filters': '''
                CREATE TABLE IF NOT EXISTS user_filters (
                    user_id INTEGER PRIMARY KEY,
                    filter_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES authorized_users(user_id)
                )
            '''
        }
        
        # Создаем таблицы
        for table_name, create_sql in schema.items():
            try:
                cursor.execute(create_sql)
                log_info(f"✅ Таблица '{table_name}' готова", module='Database')
            except Exception as e:
                log_error(f"Ошибка создания таблицы '{table_name}': {e}", module='Database')
        
        conn.commit()
        conn.close()
        log_info(f"✅ База данных {self.db_path} инициализирована", module='Database')
    
    def get_connection(self) -> sqlite3.Connection:
        """Получение соединения с базой данных"""
        return sqlite3.connect(self.db_path)
    
    def execute_query(self, query: str, params: tuple = ()) -> Optional[sqlite3.Cursor]:
        """Выполнение запроса к базе данных"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor
        except Exception as e:
            log_error(f"Ошибка выполнения запроса: {e}", module='Database')
            return None
    
    def execute_transaction(self, queries: list) -> bool:
        """Выполнение транзакции с несколькими запросами"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            for query, params in queries:
                cursor.execute(query, params)
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            log_error(f"Ошибка выполнения транзакции: {e}", module='Database')
            return False
    
    def table_exists(self, table_name: str) -> bool:
        """Проверка существования таблицы"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
            """, (table_name,))
            result = cursor.fetchone() is not None
            conn.close()
            return result
        except Exception as e:
            log_error(f"Ошибка проверки таблицы '{table_name}': {e}", module='Database')
            return False
    
    def get_table_info(self, table_name: str) -> list:
        """Получение информации о структуре таблицы"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            conn.close()
            return columns
        except Exception as e:
            log_error(f"Ошибка получения информации о таблице '{table_name}': {e}", module='Database')
            return []
    
    def backup_database(self, backup_path: str) -> bool:
        """Создание резервной копии базы данных"""
        try:
            import shutil
            shutil.copy2(self.db_path, backup_path)
            log_info(f"✅ Резервная копия создана: {backup_path}", module='Database')
            return True
        except Exception as e:
            log_error(f"Ошибка создания резервной копии: {e}", module='Database')
            return False


def init_database(db_path: str) -> DatabaseManager:
    """Инициализация базы данных"""
    return DatabaseManager(db_path) 