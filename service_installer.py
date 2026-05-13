# service_installer.py
import os
import sys
import winreg

def create_batch_script():
    """Создание batch скрипта для службы"""
    batch_content = '''@echo off
cd /d "%~dp0"
python run_server.py
'''
    
    with open('start_service.bat', 'w', encoding='utf-8') as f:
        f.write(batch_content)
    print("✓ Создан служебный batch скрипт")

def install_as_startup():
    """Добавление в автозагрузку"""
    try:
        # Получаем путь к текущей папке
        current_dir = os.path.dirname(os.path.abspath(__file__))
        batch_path = os.path.join(current_dir, 'start_service.bat')
        
        # Создаем bat файл для автозагрузки
        startup_bat = f'''@echo off
cd /d "{current_dir}"
start "" python run_server.py
'''
        
        # Путь к папке автозагрузки
        startup_folder = os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
        startup_script = os.path.join(startup_folder, 'onco_chat_startup.bat')
        
        with open(startup_script, 'w') as f:
            f.write(startup_bat)
        
        print("✓ Добавлено в автозагрузку")
        return True
    except Exception as e:
        print(f"× Ошибка добавления в автозагрузку: {e}")
        return False

def create_desktop_shortcut():
    """Создание ярлыка на рабочем столе"""
    try:
        import winshell
        from win32com.client import Dispatch
        
        desktop = winshell.desktop()
        path = os.path.join(desktop, "Онко-чат.lnk")
        
        target = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'start_service.bat')
        wDir = os.path.dirname(os.path.abspath(__file__))
        
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(path)
        shortcut.Targetpath = target
        shortcut.WorkingDirectory = wDir
        shortcut.IconLocation = "shell32.dll,140"
        shortcut.save()
        
        print("✓ Создан ярлык на рабочем столе")
        return True
    except:
        print("× Не удалось создать ярлык (установите pywin32)")
        return False

def main():
    print("🔧 Установка системы онко-чата как службы...")
    
    # Создаем служебные файлы
    create_batch_script()
    
    # Добавляем в автозагрузку
    install_as_startup()
    
    # Создаем ярлык
    create_desktop_shortcut()
    
    print("\n✅ Установка завершена!")
    print("Теперь приложение будет запускаться автоматически")

if __name__ == "__main__":
    main()
