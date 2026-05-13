# test_network.py
import socket
import subprocess
import threading
import time

def test_port_open(port=5000):
    """Проверка открыт ли порт"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

def start_server_temp():
    """Временный запуск сервера для теста"""
    try:
        from app import app
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Ошибка запуска: {e}")

if __name__ == "__main__":
    print("🔍 Тестирование сети и сервера...")
    
    # Проверяем порт
    if test_port_open():
        print("✅ Порт 5000 открыт")
    else:
        print("❌ Порт 5000 закрыт")
        
        # Попробуем запустить сервер
        print("🚀 Запуск тестового сервера...")
        server_thread = threading.Thread(target=start_server_temp)
        server_thread.daemon = True
        server_thread.start()
        
        time.sleep(3)  # Ждем запуск
        
        if test_port_open():
            print("✅ Сервер запущен успешно")
        else:
            print("❌ Не удалось запустить сервер")
