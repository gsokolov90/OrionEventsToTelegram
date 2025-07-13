#!/usr/bin/env python3
"""
Генератор тестовых событий для OrionEventsToTelegram
Генерирует события проходов сотрудников с возможностью эмуляции email или прямой записи в базу
"""

import sys
import os
import random
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path

# Добавляем родительскую директорию в sys.path для работы с модулями проекта
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(parent_dir)
sys.path.insert(0, project_root)

from app.config import get_events_database_path
from app.events_database import init_events_database


class EventsGenerator:
    """Генератор тестовых событий"""
    
    def __init__(self):
        self.employees = ["Иванов И. И.", "Петров П. П."]
        self.smtp_server = '127.0.0.1'
        self.smtp_port = 1025
        
        # Инициализация базы данных
        self.events_db = init_events_database(get_events_database_path())
        print(f"✅ База данных событий инициализирована: {get_events_database_path()}")
    
    def generate_random_time(self, start_hour=0, end_hour=23):
        """Генерация случайного времени в заданном диапазоне"""
        hour = random.randint(start_hour, end_hour)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        return f"{hour:02d}:{minute:02d}:{second:02d}"
    
    def generate_shift_times(self, base_date):
        """Генерация времени входа и выхода для смены"""
        # Случайное время входа (00:00-23:59)
        entry_time = self.generate_random_time(0, 23)
        
        # Продолжительность смены 7-10 часов
        shift_duration = random.randint(7, 10)
        
        # Вычисляем время выхода
        # Используем только дату без времени для создания datetime объекта
        base_date_only = base_date.date()
        entry_dt = datetime.combine(base_date_only, datetime.strptime(entry_time, "%H:%M:%S").time())
        exit_dt = entry_dt + timedelta(hours=shift_duration)
        
        # Если выход в следующий день, корректируем дату
        if exit_dt.date() > entry_dt.date():
            exit_date = exit_dt.strftime("%d.%m.%Y")
        else:
            exit_date = base_date.strftime("%d.%m.%Y")
        
        exit_time = exit_dt.strftime("%H:%M:%S")
        
        return {
            'entry': {
                'date': base_date.strftime("%d.%m.%Y"),
                'time': entry_time
            },
            'exit': {
                'date': exit_date,
                'time': exit_time
            }
        }
    
    def create_event_message(self, employee, direction, date, time):
        """Создание сообщения события в формате ОРИОН"""
        if direction == "Вход":
            zone = "УРВ Проходная"
        else:
            zone = "Внешний мир"
        
        return f"{date} {time} Доступ предоставлен Считыватель {random.randint(1, 2)}, Прибор 19 Дверь:УРВ Проходная режим:{direction} Зона доступа:{zone} Сотрудник:{employee}"
    
    def check_duplicate_event(self, employee, direction, date, time):
        """Проверка на дубликат события"""
        try:
            conn = sqlite3.connect(get_events_database_path())
            cursor = conn.cursor()
            
            # Проверяем существование записи с такими же параметрами
            cursor.execute("""
                SELECT COUNT(*) FROM events 
                WHERE employee_name = ? AND direction = ? AND event_time = ?
            """, (employee, direction, time[:5]))  # Используем только HH:MM для сравнения
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count > 0
        except Exception as e:
            print(f"⚠️  Ошибка проверки дубликата: {e}")
            return False
    
    def send_email_event(self, message):
        """Отправка события через SMTP"""
        try:
            msg = EmailMessage()
            msg['Subject'] = 'Событие УРВ'
            msg['From'] = 'orion@company.com'
            msg['To'] = 'events@company.com'
            msg.set_content(message)
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.send_message(msg)
            
            return True
        except Exception as e:
            print(f"❌ Ошибка отправки email: {e}")
            return False
    
    def add_event_to_database(self, employee, direction, event_time, full_time, raw_message):
        """Добавление события напрямую в базу данных"""
        try:
            # Создаем обработанное сообщение для Telegram
            processed_message = f"🕒 {event_time} | {'⚙️' if direction == 'Вход' else '🏡'} {direction} | 👤 {employee}"
            
            success = self.events_db.add_event(
                employee_name=employee,
                direction=direction,
                event_time=event_time,
                full_time=full_time,
                raw_message=raw_message,
                processed_message=processed_message
            )
            
            return success
        except Exception as e:
            print(f"❌ Ошибка добавления в базу данных: {e}")
            return False
    
    def clear_all_events(self):
        """Очистка всех событий из базы данных"""
        try:
            conn = sqlite3.connect(get_events_database_path())
            cursor = conn.cursor()
            
            # Получаем количество записей для удаления
            cursor.execute("SELECT COUNT(*) FROM events")
            count = cursor.fetchone()[0]
            
            if count > 0:
                # Удаляем все записи
                cursor.execute("DELETE FROM events")
                conn.commit()
                print(f"🗑️  Удалено {count} записей из базы данных событий")
            else:
                print("ℹ️  База данных событий уже пуста")
            
            conn.close()
            return True
        except Exception as e:
            print(f"❌ Ошибка очистки базы данных: {e}")
            return False
    
    def generate_events(self, days_count, use_email=False):
        """Генерация событий на указанное количество дней"""
        print(f"\n🚀 Начинаем генерацию событий на {days_count} дней...")
        print(f"📧 Режим: {'Email эмуляция' if use_email else 'Прямая запись в базу'}")
        
        generated_count = 0
        skipped_count = 0
        
        # Генерируем события для каждого дня
        for day_offset in range(days_count):
            current_date = datetime.now() - timedelta(days=day_offset)
            
            print(f"\n📅 День {day_offset + 1}: {current_date.strftime('%d.%m.%Y')}")
            
            for employee in self.employees:
                # Генерируем время смены
                shift_times = self.generate_shift_times(current_date)
                
                # Событие входа
                entry_time = shift_times['entry']['time']
                entry_date = shift_times['entry']['date']
                entry_message = self.create_event_message(employee, "Вход", entry_date, entry_time)
                
                # Проверяем дубликат
                if self.check_duplicate_event(employee, "Вход", entry_date, entry_time):
                    print(f"  ⏭️  Пропуск дубликата: {employee} - Вход в {entry_time}")
                    skipped_count += 1
                else:
                    if use_email:
                        if self.send_email_event(entry_message):
                            print(f"  📧 Email отправлен: {employee} - Вход в {entry_time}")
                            generated_count += 1
                        else:
                            print(f"  ❌ Ошибка отправки email: {employee} - Вход")
                    else:
                        if self.add_event_to_database(employee, "Вход", entry_time[:5], entry_time, entry_message):
                            print(f"  💾 Записано в БД: {employee} - Вход в {entry_time}")
                            generated_count += 1
                        else:
                            print(f"  ❌ Ошибка записи в БД: {employee} - Вход")
                
                # Событие выхода
                exit_time = shift_times['exit']['time']
                exit_date = shift_times['exit']['date']
                exit_message = self.create_event_message(employee, "Выход", exit_date, exit_time)
                
                # Проверяем дубликат
                if self.check_duplicate_event(employee, "Выход", exit_date, exit_time):
                    print(f"  ⏭️  Пропуск дубликата: {employee} - Выход в {exit_time}")
                    skipped_count += 1
                else:
                    if use_email:
                        if self.send_email_event(exit_message):
                            print(f"  📧 Email отправлен: {employee} - Выход в {exit_time}")
                            generated_count += 1
                        else:
                            print(f"  ❌ Ошибка отправки email: {employee} - Выход")
                    else:
                        if self.add_event_to_database(employee, "Выход", exit_time[:5], exit_time, exit_message):
                            print(f"  💾 Записано в БД: {employee} - Выход в {exit_time}")
                            generated_count += 1
                        else:
                            print(f"  ❌ Ошибка записи в БД: {employee} - Выход")
        
        print(f"\n✅ Генерация завершена!")
        print(f"📊 Статистика:")
        print(f"  • Сгенерировано событий: {generated_count}")
        print(f"  • Пропущено дубликатов: {skipped_count}")
        print(f"  • Всего обработано: {generated_count + skipped_count}")


def main():
    """Основная функция"""
    print("🎯 Генератор тестовых событий OrionEventsToTelegram")
    print("=" * 50)
    
    # Создаем генератор
    generator = EventsGenerator()
    
    # Запрос очистки базы данных
    while True:
        clear_input = input("\n🗑️  Очистить все события в базе данных перед генерацией?\n"
                           "y - Да, очистить все события\n"
                           "n - Нет, оставить существующие события\n"
                           "Ваш выбор (y/n): ").strip().lower()
        
        if clear_input in ['y', 'n']:
            if clear_input == 'y':
                print("\n🧹 Очистка базы данных событий...")
                if generator.clear_all_events():
                    print("✅ База данных очищена")
                else:
                    print("❌ Ошибка очистки базы данных")
                    return
            else:
                print("ℹ️  Существующие события сохранены")
            break
        else:
            print("❌ Введите y или n")
    
    # Запрос количества дней
    while True:
        try:
            days_input = input("\n📅 Сколько дней событий сгенерировать? (1-30): ").strip()
            days_count = int(days_input)
            if 1 <= days_count <= 30:
                break
            else:
                print("❌ Введите число от 1 до 30")
        except ValueError:
            print("❌ Введите корректное число")
    
    # Запрос режима работы
    while True:
        mode_input = input("\n📧 Выберите режим работы:\n"
                          "1 - Прямая запись в базу данных\n"
                          "2 - Эмуляция email (отправка через SMTP)\n"
                          "Ваш выбор (1 или 2): ").strip()
        
        if mode_input in ['1', '2']:
            use_email = (mode_input == '2')
            break
        else:
            print("❌ Введите 1 или 2")
    
    # Запускаем генерацию
    generator.generate_events(days_count, use_email)


if __name__ == '__main__':
    main() 