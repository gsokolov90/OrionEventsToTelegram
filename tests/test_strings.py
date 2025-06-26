import re

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

# Пример использования
input_strings = [
    "16.09.2024 5:02:49 Доступ предоставлен Считыватель 2, Прибор 19 Дверь:УРВ Проходная режим:Вход Зона доступа: Сотрудник:Иванов И. И.",
    "16.09.2024 4:49:44 Доступ предоставлен Считыватель 1, Прибор 19 Дверь:УРВ Проходная режим:Выход Зона доступа:Внешний мир Сотрудник:Петров П. П."
]

for s in input_strings:
    print(process_string(s))
