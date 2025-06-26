# send_test_email.py

import smtplib
from email.message import EmailMessage
import random

SMTP_SERVER = '127.0.0.1'
SMTP_PORT = 1025


# Пример использования
input_strings = [
    "16.09.2024 5:02:49 Доступ предоставлен Считыватель 2, Прибор 19 Дверь:УРВ Проходная режим:Вход Зона доступа: Сотрудник:Иванов И. И.",
    "16.09.2024 4:49:44 Доступ предоставлен Считыватель 1, Прибор 19 Дверь:УРВ Проходная режим:Выход Зона доступа:Внешний мир Сотрудник:Петров П. П."
]

msg = EmailMessage()
msg['Subject'] = 'Тестовое сообщение'
msg['From'] = 'тестовый отправитель <test@example.com>'
msg['To'] = 'получатель <recipient@example.com>'
msg.set_content(random.choice(input_strings))

with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
    server.send_message(msg)

print("Сообщение отправлено на локальный SMTP сервер.")
