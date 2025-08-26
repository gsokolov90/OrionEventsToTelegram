#!/usr/bin/env python3
"""
Скрипт для исправления BOM в config.ini
"""

import sys
import os

def fix_bom_in_config():
    """Исправляет BOM в config.ini если он есть"""
    config_path = 'config.ini'
    
    if not os.path.exists(config_path):
        print(f"[ERROR] Файл {config_path} не найден!")
        return False
    
    try:
        with open(config_path, 'rb') as f:
            content = f.read()
        
        if content.startswith(b'\xef\xbb\xbf'):
            print("[WARNING] BOM обнаружен в config.ini, исправляем...")
            # Убираем BOM
            content = content[3:]
            with open(config_path, 'wb') as f:
                f.write(content)
            print("[SUCCESS] BOM удален из config.ini")
            return True
        else:
            print("[INFO] Кодировка config.ini корректна")
            return True
            
    except Exception as e:
        print(f"[ERROR] Ошибка при проверке {config_path}: {e}")
        return False

if __name__ == "__main__":
    success = fix_bom_in_config()
    sys.exit(0 if success else 1)
