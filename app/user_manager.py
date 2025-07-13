"""
Модуль управления пользователями и фильтрами
"""

import os
from typing import Set, Dict, Optional
from .logger import log_info, log_warning, log_error


class UserManager:
    """Менеджер пользователей и фильтров"""
    
    def __init__(self, authorized_users_file: str, user_filters_file: str):
        self.authorized_users_file = authorized_users_file
        self.user_filters_file = user_filters_file
        self._ensure_files_exist()
    
    def _ensure_files_exist(self) -> None:
        """Создает файлы данных если их нет"""
        # Создаем папку db если её нет
        db_dir = os.path.dirname(self.authorized_users_file)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
            log_info(f"📁 Папка {db_dir} создана", module='UserManager')
        
        # Создаем файлы если их нет
        for file_path in [self.authorized_users_file, self.user_filters_file]:
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    pass  # Создаем пустой файл
                log_info(f"📄 Файл {file_path} создан", module='UserManager')
    
    def get_authorized_users(self) -> Set[int]:
        """Получение списка авторизованных пользователей"""
        try:
            if not os.path.exists(self.authorized_users_file):
                return set()
            
            with open(self.authorized_users_file, 'r', encoding='utf-8') as f:
                users = set()
                for line in f:
                    line = line.strip()
                    if line and line.isdigit():
                        users.add(int(line))
                return users
        except Exception as e:
            log_error(f"Ошибка чтения файла авторизованных пользователей: {e}", module='UserManager')
            return set()
    
    def add_authorized_user(self, user_id: int) -> bool:
        """Добавление авторизованного пользователя"""
        try:
            authorized_users = self.get_authorized_users()
            if user_id not in authorized_users:
                with open(self.authorized_users_file, 'a', encoding='utf-8') as f:
                    f.write(f"{user_id}\n")
                log_info(f"Пользователь {user_id} успешно авторизован", module='UserManager')
                return True
            else:
                log_info(f"Пользователь {user_id} уже авторизован", module='UserManager')
                return False
        except Exception as e:
            log_error(f"Ошибка добавления авторизованного пользователя: {e}", module='UserManager')
            return False
    
    def is_authorized(self, user_id: int) -> bool:
        """Проверка авторизации пользователя"""
        return user_id in self.get_authorized_users()
    
    def get_user_filters(self) -> Dict[int, str]:
        """Получение фильтров пользователей"""
        try:
            if not os.path.exists(self.user_filters_file):
                return {}
            
            filters = {}
            with open(self.user_filters_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and ':' in line:
                        user_id_str, filter_text = line.split(':', 1)
                        if user_id_str.isdigit():
                            filters[int(user_id_str)] = filter_text.strip()
            return filters
        except Exception as e:
            log_error(f"Ошибка чтения файла фильтров пользователей: {e}", module='UserManager')
            return {}
    
    def set_user_filter(self, user_id: int, filter_text: str) -> bool:
        """Установка фильтра для пользователя"""
        try:
            filters = self.get_user_filters()
            filters[user_id] = filter_text
            
            with open(self.user_filters_file, 'w', encoding='utf-8') as f:
                for uid, flt in filters.items():
                    f.write(f"{uid}:{flt}\n")
            
            log_info(f"Фильтр '{filter_text}' установлен для пользователя {user_id}", module='UserManager')
            return True
        except Exception as e:
            log_error(f"Ошибка установки фильтра: {e}", module='UserManager')
            return False
    
    def remove_user_filter(self, user_id: int) -> bool:
        """Удаление фильтра пользователя"""
        try:
            filters = self.get_user_filters()
            if user_id in filters:
                del filters[user_id]
                
                with open(self.user_filters_file, 'w', encoding='utf-8') as f:
                    for uid, flt in filters.items():
                        f.write(f"{uid}:{flt}\n")
                
                log_info(f"Фильтр отключен для пользователя {user_id}", module='UserManager')
                return True
            else:
                log_info(f"Попытка отключить несуществующий фильтр от пользователя {user_id}", module='UserManager')
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