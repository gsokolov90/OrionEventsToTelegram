#!/usr/bin/env python3
"""
Простой скрипт для исправления BOM в config.ini
"""

import os

def fix_bom():
    config_path = 'config.ini'
    
    if not os.path.exists(config_path):
        print(f"[ERROR] Файл {config_path} не найден!")
        return False
    
    try:
        # Читаем файл в бинарном режиме
        with open(config_path, 'rb') as f:
            content = f.read()
        
        # Проверяем на BOM
        if content.startswith(b'\xef\xbb\xbf'):
            print("[INFO] Обнаружен BOM, исправляем...")
            # Убираем BOM
            content = content[3:]
            
            # Записываем обратно без BOM
            with open(config_path, 'wb') as f:
                f.write(content)
            
            print("[SUCCESS] BOM успешно удален!")
            return True
        else:
            print("[INFO] BOM не обнаружен, файл в порядке")
            return True
            
    except Exception as e:
        print(f"[ERROR] Ошибка при исправлении BOM: {e}")
        return False

if __name__ == '__main__':
    print("=== Исправление BOM в config.ini ===")
    fix_bom()
