"""
Модуль обработки сообщений
"""

import re
from datetime import datetime
from typing import Optional, Tuple
from .logger import log_debug


class MessageProcessor:
    """Обработчик сообщений от системы ОРИОН"""
    
    def __init__(self):
        # Регулярные выражения для парсинга сообщений
        self.time_pattern = re.compile(r'(\d{1,2}):(\d{2})')
        self.date_pattern = re.compile(r'(\d{1,2})\.(\d{1,2})\.(\d{4})')
    
    def process_string(self, message: str) -> str:
        """
        Обработка строки сообщения
        
        Args:
            message: Исходное сообщение
            
        Returns:
            Обработанное сообщение
        """
        if not message:
            return message
        
        # Извлекаем время (часы и минуты)
        time_match = self.time_pattern.search(message)
        if time_match:
            hours, minutes = time_match.groups()
            current_time = datetime.now()
            
            # Формируем полную дату
            try:
                # Пытаемся найти дату в сообщении
                date_match = self.date_pattern.search(message)
                if date_match:
                    day, month, year = date_match.groups()
                    event_time = datetime(int(year), int(month), int(day), int(hours), int(minutes))
                else:
                    # Если даты нет, используем текущую дату
                    event_time = current_time.replace(hour=int(hours), minute=int(minutes))
                
                # Форматируем время
                formatted_time = event_time.strftime("%H:%M")
                
                # Заменяем время в сообщении
                message = self.time_pattern.sub(formatted_time, message)
                
                log_debug(f"Обработано время: {formatted_time}", module='MessageProcessor')
            except ValueError as e:
                log_debug(f"Ошибка обработки времени: {e}", module='MessageProcessor')
        
        return message
    
    def extract_time_info(self, message: str) -> Optional[Tuple[int, int]]:
        """
        Извлекает информацию о времени из сообщения
        
        Args:
            message: Сообщение для анализа
            
        Returns:
            Кортеж (часы, минуты) или None
        """
        time_match = self.time_pattern.search(message)
        if time_match:
            hours, minutes = time_match.groups()
            try:
                return int(hours), int(minutes)
            except ValueError:
                return None
        return None
    
    def format_message_for_telegram(self, original_message: str) -> str:
        """
        Форматирует сообщение для отправки в Telegram
        
        Args:
            original_message: Исходное сообщение
            
        Returns:
            Отформатированное сообщение
        """
        if not original_message:
            return "Пустое сообщение"
        
        # Обрабатываем сообщение
        processed_message = self.process_string(original_message)
        
        # Добавляем эмодзи и форматирование
        formatted_message = f"🔔 **Событие ОРИОН**\n\n{processed_message}"
        
        return formatted_message
    
    def is_valid_orion_message(self, message: str) -> bool:
        """
        Проверяет, является ли сообщение валидным сообщением от ОРИОН
        
        Args:
            message: Сообщение для проверки
            
        Returns:
            True если сообщение валидно
        """
        if not message:
            return False
        
        # Проверяем наличие времени в сообщении
        if not self.time_pattern.search(message):
            return False
        
        # Проверяем минимальную длину
        if len(message.strip()) < 10:
            return False
        
        return True 