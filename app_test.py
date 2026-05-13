# app_test.py
from flask import Flask, render_template
import os

app = Flask(__name__, template_folder=os.path.join(os.getcwd(), 'templates'))

@app.route('/')
def index():
    return render_template('index.html')  # Вернуть к основному чату



if __name__ == '__main__':
    print("Путь к шаблонам:", os.path.join(os.getcwd(), 'templates'))
    app.run(debug=True, host='127.0.0.1', port=5000)
