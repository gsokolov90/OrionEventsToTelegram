"""
Модуль управления пользователями и фильтрами с использованием SQLite
"""

import os
from typing import Set, Dict, Optional, List, Tuple, Any
from datetime import datetime

# Простые функции логирования для Windows
def log_info(message: str, module: str = 'UserManager') -> None:
    print(f"[INFO] {module}: {message}")

def log_warning(message: str, module: str = 'UserManager') -> None:
    print(f"[WARNING] {module}: {message}")

def log_error(message: str, module: str = 'UserManager') -> None:
    print(f"[ERROR] {module}: {message}")

# Пытаемся получить логгер только для Unix систем
logger = None
if os.name != 'nt':  # Не Windows
    try:
        from logger import get_logger
        logger = get_logger('UserManager')
        # Переопределяем функции если логгер доступен
        def log_info(message: str, module: str = 'UserManager') -> None:
            logger.info(message)
        def log_warning(message: str, module: str = 'UserManager') -> None:
            logger.warning(message)
        def log_error(message: str, module: str = 'UserManager') -> None:
            logger.error(message)
    except ImportError:
        pass  # Используем простые функции


class UserManager:
    """Менеджер пользователей и фильтров с SQLite"""
    
    def __init__(self, db_manager: Any):
        self.db_manager = db_manager
        # База данных будет инициализирована через DatabaseManager
    
    def get_authorized_users(self) -> Set[int]:
        """Получение списка авторизованных пользователей"""
        try:
            cursor = self.db_manager.execute_query("SELECT user_id FROM authorized_users")
            if cursor:
                users = {row[0] for row in cursor.fetchall()}
                cursor.connection.close()
                return users
            return set()
        except Exception as e:
            log_error(f"Ошибка чтения авторизованных пользователей: {e}", module='UserManager')
            return set()
    
    def add_authorized_user(self, user_id: int, username: Optional[str] = None, 
                           first_name: Optional[str] = None, last_name: Optional[str] = None, 
                           added_by: Optional[int] = None) -> bool:
        """Добавление авторизованного пользователя"""
        try:
            cursor = self.db_manager.execute_query("SELECT user_id FROM authorized_users WHERE user_id = ?", (user_id,))
            if cursor and cursor.fetchone():
                log_info(f"Пользователь {user_id} уже авторизован", module='UserManager')
                cursor.connection.close()
                return False
            
            # Добавляем пользователя
            cursor = self.db_manager.execute_query("""
                INSERT INTO authorized_users (user_id, username, first_name, last_name, added_by, added_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, added_by, datetime.now()))
            
            if cursor:
                cursor.connection.commit()
                cursor.connection.close()
                log_info(f"Пользователь {user_id} успешно авторизован", module='UserManager')
                return True
            return False
        except Exception as e:
            log_error(f"Ошибка добавления авторизованного пользователя: {e}", module='UserManager')
            return False
    
    def remove_authorized_user(self, user_id: int) -> bool:
        """Удаление авторизованного пользователя"""
        try:
            queries = [
                ("DELETE FROM user_filters WHERE user_id = ?", (user_id,)),
                ("DELETE FROM authorized_users WHERE user_id = ?", (user_id,))
            ]
            
            success = self.db_manager.execute_transaction(queries)
            if success:
                log_info(f"Пользователь {user_id} удален", module='UserManager')
                return True
            else:
                log_info(f"Пользователь {user_id} не найден", module='UserManager')
                return False
        except Exception as e:
            log_error(f"Ошибка удаления пользователя: {e}", module='UserManager')
            return False
    
    def is_authorized(self, user_id: int) -> bool:
        """Проверка авторизации пользователя"""
        return user_id in self.get_authorized_users()
    
    def get_user_info(self, user_id: int) -> Optional[Dict]:
        """Получение информации о пользователе"""
        try:
            cursor = self.db_manager.execute_query("""
                SELECT user_id, username, first_name, last_name, added_at
                FROM authorized_users WHERE user_id = ?
            """, (user_id,))
            
            if cursor:
                row = cursor.fetchone()
                cursor.connection.close()
                
                if row:
                    return {
                        'user_id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3],
                        'added_at': row[4]
                    }
            return None
        except Exception as e:
            log_error(f"Ошибка получения информации о пользователе: {e}", module='UserManager')
            return None
    
    def get_all_users_info(self) -> List[Dict]:
        """Получение информации о всех авторизованных пользователях"""
        try:
            cursor = self.db_manager.execute_query("""
                SELECT user_id, username, first_name, last_name, added_at
                FROM authorized_users ORDER BY user_id
            """)
            
            users = []
            if cursor:
                for row in cursor.fetchall():
                    users.append({
                        'user_id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3],
                        'added_at': row[4]
                    })
                cursor.connection.close()
            return users
        except Exception as e:
            log_error(f"Ошибка получения списка пользователей: {e}", module='UserManager')
            return []
    
    def create_auth_request(self, user_id: int, username: Optional[str] = None, 
                           first_name: Optional[str] = None, last_name: Optional[str] = None, 
                           request_text: str = "") -> int:
        """Создание запроса на авторизацию"""
        try:
            cursor = self.db_manager.execute_query("""
                INSERT INTO auth_requests (user_id, username, first_name, last_name, request_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, request_text, datetime.now()))
            
            if cursor:
                request_id = cursor.lastrowid
                cursor.connection.commit()
                cursor.connection.close()
                
                if request_id is not None:
                    log_info(f"Создан запрос на авторизацию {request_id} для пользователя {user_id}", module='UserManager')
                    return request_id
                else:
                    log_error(f"Не удалось создать запрос на авторизацию для пользователя {user_id}", module='UserManager')
            return 0
        except Exception as e:
            log_error(f"Ошибка создания запроса на авторизацию: {e}", module='UserManager')
            return 0
    
    def get_auth_request_user_id(self, request_id: int) -> Optional[int]:
        """Получение ID пользователя по ID запроса"""
        try:
            cursor = self.db_manager.execute_query("""
                SELECT user_id FROM auth_requests WHERE id = ? AND status = 'pending'
            """, (request_id,))
            
            if cursor:
                row = cursor.fetchone()
                cursor.connection.close()
                return row[0] if row else None
            return None
        except Exception as e:
            log_error(f"Ошибка получения ID пользователя для запроса {request_id}: {e}", module='UserManager')
            return None
    
    def get_pending_auth_requests(self) -> List[Dict]:
        """Получение всех ожидающих запросов на авторизацию"""
        try:
            cursor = self.db_manager.execute_query("""
                SELECT id, user_id, username, first_name, last_name, request_text, created_at
                FROM auth_requests WHERE status = 'pending' ORDER BY created_at
            """)
            
            requests = []
            if cursor:
                for row in cursor.fetchall():
                    requests.append({
                        'id': row[0],
                        'user_id': row[1],
                        'username': row[2],
                        'first_name': row[3],
                        'last_name': row[4],
                        'request_text': row[5],
                        'created_at': row[6]
                    })
                cursor.connection.close()
            return requests
        except Exception as e:
            log_error(f"Ошибка получения запросов на авторизацию: {e}", module='UserManager')
            return []
    
    def process_auth_request(self, request_id: int, approved: bool, processed_by: int) -> bool:
        """Обработка запроса на авторизацию"""
        try:
            cursor = self.db_manager.execute_query("""
                SELECT user_id, username, first_name, last_name, request_text
                FROM auth_requests WHERE id = ? AND status = 'pending'
            """, (request_id,))
            
            if not cursor:
                log_warning(f"Запрос {request_id} не найден или уже обработан", module='UserManager')
                return False
            
            row = cursor.fetchone()
            cursor.connection.close()
            
            if not row:
                log_warning(f"Запрос {request_id} не найден или уже обработан", module='UserManager')
                return False
            
            user_id, username, first_name, last_name, request_text = row
            status = 'approved' if approved else 'rejected'
            
            # Обновляем статус запроса
            cursor = self.db_manager.execute_query("""
                UPDATE auth_requests 
                SET status = ?, processed_by = ?, processed_at = ?
                WHERE id = ?
            """, (status, processed_by, datetime.now(), request_id))
            
            if cursor:
                cursor.connection.commit()
                cursor.connection.close()
                
                # Если одобрено, добавляем пользователя
                if approved:
                    self.add_authorized_user(user_id, username, first_name, last_name, processed_by)
                
                action = "одобрен" if approved else "отклонен"
                log_info(f"Запрос {request_id} {action} администратором {processed_by}", module='UserManager')
                return True
            return False
        except Exception as e:
            log_error(f"Ошибка обработки запроса на авторизацию: {e}", module='UserManager')
            return False
    
    def get_user_filters(self) -> Dict[int, str]:
        """Получение фильтров пользователей"""
        try:
            cursor = self.db_manager.execute_query("SELECT user_id, filter_text FROM user_filters")
            
            filters = {}
            if cursor:
                for row in cursor.fetchall():
                    filters[row[0]] = row[1]
                cursor.connection.close()
            return filters
        except Exception as e:
            log_error(f"Ошибка чтения фильтров пользователей: {e}", module='UserManager')
            return {}
    
    def set_user_filter(self, user_id: int, filter_text: str) -> bool:
        """Установка фильтра для пользователя"""
        try:
            # Проверяем, что пользователь авторизован
            if not self.is_authorized(user_id):
                log_warning(f"Попытка установить фильтр для неавторизованного пользователя {user_id}", module='UserManager')
                return False
            
            cursor = self.db_manager.execute_query("""
                INSERT OR REPLACE INTO user_filters (user_id, filter_text, created_at)
                VALUES (?, ?, ?)
            """, (user_id, filter_text, datetime.now()))
            
            if cursor:
                cursor.connection.commit()
                cursor.connection.close()
                log_info(f"Фильтр '{filter_text}' установлен для пользователя {user_id}", module='UserManager')
                return True
            return False
        except Exception as e:
            log_error(f"Ошибка установки фильтра: {e}", module='UserManager')
            return False
    
    def remove_user_filter(self, user_id: int) -> bool:
        """Удаление фильтра пользователя"""
        try:
            cursor = self.db_manager.execute_query("DELETE FROM user_filters WHERE user_id = ?", (user_id,))
            
            if cursor:
                success = cursor.rowcount > 0
                cursor.connection.commit()
                cursor.connection.close()
                
                if success:
                    log_info(f"Фильтр отключен для пользователя {user_id}", module='UserManager')
                else:
                    log_info(f"Попытка отключить несуществующий фильтр от пользователя {user_id}", module='UserManager')
                return success
            return False
        except Exception as e:
            log_error(f"Ошибка удаления фильтра: {e}", module='UserManager')
            return False
    
    def get_user_filter(self, user_id: int) -> Optional[str]:
        """Получение фильтра пользователя"""
        filters = self.get_user_filters()
        return filters.get(user_id)
    
    def should_send_message(self, user_id: int, message_text: str) -> bool:
        """Проверка, нужно ли отправлять сообщение пользователю"""
        if not self.is_authorized(user_id):
            return False
        
        user_filter = self.get_user_filter(user_id)
        if not user_filter:
            return True  # Нет фильтра - отправляем все
        
        return user_filter.lower() in message_text.lower() 