# debug_server.py
from flask import Flask, request
import socket

app = Flask(__name__)

@app.route('/')
def debug_info():
    # Получаем информацию о клиенте
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    headers = dict(request.headers)
    
    # Получаем локальный IP сервера
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    info = f"""
    <h1>Отладочная информация</h1>
    <p><b>Ваш IP (клиент):</b> {client_ip}</p>
    <p><b>Local IP сервера:</b> {local_ip}</p>
    <p><b>Host:</b> {request.host}</p>
    <p><b>Headers:</b></p>
    <ul>
    """
    
    for key, value in headers.items():
        info += f"<li><b>{key}:</b> {value}</li>"
    
    info += "</ul>"
    
    return info

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
