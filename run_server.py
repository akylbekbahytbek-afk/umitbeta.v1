# run_server.py
import subprocess
import sys
import os
import signal
import atexit
import psutil
from pathlib import Path

class OncologyChatServer:
    def __init__(self):
        self.processes = []
        
    def start_flask(self):
        """Запуск Flask сервера"""
        try:
            # Запуск Flask с внешним доступом
            env = os.environ.copy()
            proc = subprocess.Popen([
                sys.executable, '-c', 
                'from app import app; app.run(host="0.0.0.0", port=5000, debug=False)'
            ], env=env)
            self.processes.append(proc)
            print("✓ Flask сервер запущен на порту 5000")
            return True
        except Exception as e:
            print(f"× Ошибка запуска Flask: {e}")
            return False
    
    def get_local_ip(self):
        """Получение локального IP"""
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "localhost"
    
    def show_info(self):
        """Показ информации для подключения"""
        ip = self.get_local_ip()
        print("\n" + "="*50)
        print("ОНКОЛОГИЧЕСКИЙ ЧАТ-БОТ ЗАПУЩЕН!")
        print("="*50)
        print(f"💻 Локально: http://localhost:5000")
        print(f"📱 С других устройств: http://{ip}:5000")
        print(f"🔄 Для остановки нажмите Ctrl+C")
        print("="*50)
    
    def cleanup(self):
        """Очистка процессов при завершении"""
        print("\nОстанавливаем сервер...")
        for proc in self.processes:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except:
                proc.kill()
        print("✓ Сервер остановлен")
    
    def run(self):
        """Основной цикл запуска"""
        # Регистрация функции очистки
        atexit.register(self.cleanup)
        
        print("🚀 Запуск системы поддержки онкопациентов...")
        
        # Запуск Flask
        if not self.start_flask():
            print("× Не удалось запустить сервер")
            return
        
        # Показ информации
        self.show_info()
        
        try:
            # Ожидание завершения
            while True:
                for proc in self.processes:
                    if proc.poll() is not None:
                        print("× Один из процессов завершен неожиданно")
                        return
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Получен сигнал остановки...")
        finally:
            self.cleanup()

if __name__ == "__main__":
    server = OncologyChatServer()
    server.run()
