# app.py (исправленный)
import os
import json
import re
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_cors import CORS
import requests
from datetime import datetime
import sqlite3
import uuid

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None

# Используем DATABASE_URL из Heroku или локальную базу
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///database.db')

app = Flask(__name__, template_folder=os.path.join(os.getcwd(), 'templates'))
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-for-development')
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Для Heroku нужно правильно парсить DATABASE_URL
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen2.5:7b')
KNOWLEDGE_BASE_PATH = os.environ.get('KNOWLEDGE_BASE_PATH', 'knowledge_base.json')
CLINIC_KNOWLEDGE_BASE_PATH = os.environ.get('CLINIC_KNOWLEDGE_BASE_PATH', 'clinic_knowledge_base.json')

# Триггеры для онкопациентов
ONCOLOGY_TRIGGERS = {
    'treatment_fear': ['боюсь лечения', 'страшно операция', 'химиотерапия страшно', 'радиация больно'],
    'death_anxiety': ['умру скоро', 'страх смерти', 'не хочу умирать', 'смерть близко'],
    'isolation': ['одиноко', 'никто не понимает', 'все бросили', 'никто рядом'],
    'body_changes': ['изменилось тело', 'выпадают волосы', 'шрамы', 'деформация'],
    'future_fear': ['будущее темно', 'что будет потом', 'не доживу', 'планы рушатся'],
    'family_stress': ['семья страдает', 'тяжесть для родных', 'виню себя перед семьей'],
    'hope_loss': ['нет надежды', 'все бесполезно', 'смысла нет', 'сдаюсь'],
    'pain_concern': ['боль не проходит', 'муки', 'страдания', 'терпеть невмоготу']
}

EMOTION_KEYWORDS = {
    'hopeless': ['нет надежды', 'безнадежно', 'смысла нет', 'не могу больше', 'сдаюсь', 'все бесполезно', 'все зря', 'это зря', 'не помогает'],
    'scared': ['страшно', 'боюсь', 'ужас', 'паника', 'умирать', 'смерть'],
    'anxious': ['тревожно', 'тревога', 'переживаю', 'нервничаю', 'неизвестность', 'жду результатов'],
    'sad': ['грустно', 'плачу', 'тяжело', 'плохо', 'одиноко', 'устал', 'устала', 'жалуюсь'],
    'happy': ['рад', 'рада', 'спокойнее', 'хорошо', 'получше', 'надежда', 'спасибо']
}

EMOTION_LABELS = {
    'sad': 'грусть',
    'anxious': 'тревога',
    'scared': 'страх',
    'hopeless': 'безнадежность',
    'happy': 'радость',
    'neutral': 'нейтральное состояние'
}

TRIGGER_LABELS = {
    'treatment_fear': 'страх лечения',
    'death_anxiety': 'страх смерти',
    'isolation': 'одиночество',
    'body_changes': 'изменения тела',
    'future_fear': 'страх будущего',
    'family_stress': 'семейный стресс',
    'hope_loss': 'потеря надежды',
    'pain_concern': 'боль'
}

STOP_WORDS = {
    'что', 'как', 'где', 'когда', 'зачем', 'почему', 'если', 'это', 'мне',
    'меня', 'мой', 'моя', 'мои', 'вам', 'вас', 'ваш', 'ваша', 'для', 'или',
    'при', 'про', 'без', 'уже', 'еще', 'очень', 'нужно', 'надо', 'можно',
    'будет', 'делать', 'себя', 'есть', 'нет'
}

MEDICAL_QUESTION_KEYWORDS = {
    'биопсия', 'гистология', 'цитология', 'онкомаркер', 'онкомаркеры',
    'химиотерапия', 'лучевая', 'мрт', 'кт', 'пэт', 'пса', 'анализ',
    'анализы', 'обследование', 'обследования', 'лечение', 'операция',
    'стадия', 'рак', 'онколог', 'консилиум', 'мдг', 'метастазы',
    'таргетная', 'иммунотерапия', 'гормонотерапия'
}
SERVICE_QUESTION_KEYWORDS = {
    'контакты', 'телефон', 'регистратура', 'запись', 'записаться',
    'документы', 'прием', 'приём', 'кабинет', 'поддержка', 'координатор',
    'психолог', 'иногородним', 'жалоба', 'обращение'
}

NEXT_STEP_WORDS = ['что делать', 'дальше', 'теперь', 'куда обращаться', 'к кому обращаться', 'только узнал', 'узнал о диагнозе', 'поставили диагноз']
UNCERTAINTY_WORDS = ['неизвестность', 'не знаю', 'непонятно', 'что теперь', 'куда обращаться', 'к кому обращаться']
PAIN_WORDS = ['боль', 'боли', 'болью', 'больно', 'болит', 'болят', 'болезнен', 'ноет', 'колет', 'жжет', 'давит']
CHEST_WORDS = ['грудь', 'груди', 'грудной', 'сердце', 'сердца']
SHORT_TOPIC_WORDS = {'лечение', 'боль', 'маршрут', 'диагноз', 'анализы', 'обследования', 'результаты', 'страх'}
TREATMENT_DOUBT_WORDS = ['лечение не помогает', 'лечение мне не помогает', 'лечение не поможет', 'лечиться зря', 'все зря', 'это все зря', 'трачу время', 'не поможет']
RESULTS_TOPIC_WORDS = ['результаты обследований', 'результаты анализов', 'жду результаты', 'результаты']
NEW_DIAGNOSIS_WORDS = ['только что сказали', 'только что узнал', 'поставили диагноз', 'у меня онкология', 'у меня рак', 'это рак']
CHEMO_FEAR_WORDS = ['боюсь химиотерапии', 'боюсь химии', 'страшно идти на химию', 'страшно идти на химиотерапию', 'химиотерапия страшно']
WAITING_RESULTS_WORDS = ['жду результаты', 'жду анализы', 'жду биопсию', 'схожу с ума', 'не могу спать', 'каждый день проверяю']
TREATMENT_REFUSAL_WORDS = ['не хочу лечиться', 'не пойду на химиотерапию', 'не пойду на химию', 'отказываюсь от лечения', 'не буду лечиться', 'зачем мучиться']
DYSPNEA_WORDS = ['не могу дышать', 'задыхаюсь', 'тяжело дышать', 'нехватка воздуха']
FEVER_WORDS = ['температура', 'жар', 'лихорадка']
BLEEDING_WORDS = ['кровь идет', 'кровь идёт', 'кровотечение', 'кровь из', 'не останавливается кровь']
SEVERE_BLEEDING_WORDS = ['сильное', 'не останавливается', 'много крови']
FAINTING_WORDS = ['потерял сознание', 'потеряла сознание', 'упал в обморок', 'упала в обморок', 'сильное головокружение', 'не могу встать']
ACUTE_CRISIS_WORDS = ['мне очень плохо', 'невыносимо', 'умираю']

# Маршруты для урологической онкологии (MVP)
UROLOGY_ROUTES = {
    'подозрение_простата': {
        'procedures': ['ПСА', 'УЗИ_простаты', 'МРТ_малого_таза', 'Биопсия'],
        'preparations': {
            'ПСА': 'Голодать 8 часов, не катетеризировать мочевой пузырь',
            'УЗИ_простаты': 'Полный мочевой пузырь, за 1 час до исследования выпить 1 литр воды',
            'МРТ_малого_таза': 'При себе направление и паспорт. Без металлических предметов',
            'Биопсия': 'За 3 дня прекратить прием антикоагулянтов. При себе анализы крови'
        }
    },
    'подозрение_почка': {
        'procedures': ['КТ_почек', 'УЗИ_почек', 'Анализы_крови', 'Цистоскопия'],
        'preparations': {
            'КТ_почек': 'При себе контраст и анализы функции почек',
            'УЗИ_почек': 'Подготовка не требуется',
            'Анализы_крови': 'Голодать 8 часов',
            'Цистоскопия': 'За 3 дня прекратить прием антикоагулянтов'
        }
    }
}

# Подключение к базе данных
def get_db_connection():
    if not DATABASE_URL or 'sqlite' in DATABASE_URL:
        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        return conn
    else:
        if psycopg2 is None:
            raise RuntimeError('Для PostgreSQL установите psycopg2-binary или используйте локальный SQLite')
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn

# Создание таблиц
def init_db():
    conn = get_db_connection()
    if not DATABASE_URL or 'sqlite' in DATABASE_URL:
        conn.execute('''CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            sender TEXT,
            text TEXT,
            emotion TEXT,
            triggers TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE,
            session_id TEXT,
            subscription_status TEXT DEFAULT 'free',
            diagnosis TEXT,
            route_stage TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            procedure TEXT,
            appointment_date DATE,
            status TEXT DEFAULT 'scheduled',
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
    else:
        conn.execute('''CREATE TABLE IF NOT EXISTS conversations (
            id SERIAL PRIMARY KEY,
            session_id TEXT,
            sender TEXT,
            text TEXT,
            emotion TEXT,
            triggers TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id TEXT UNIQUE,
            session_id TEXT,
            subscription_status TEXT DEFAULT 'free',
            diagnosis TEXT,
            route_stage TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.execute('''CREATE TABLE IF NOT EXISTS appointments (
            id SERIAL PRIMARY KEY,
            user_id TEXT,
            procedure TEXT,
            appointment_date DATE,
            status TEXT DEFAULT 'scheduled',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
    conn.commit()
    conn.close()

# Инициализация базы
init_db()

def load_knowledge_base():
    if not os.path.exists(KNOWLEDGE_BASE_PATH):
        return {'entries': [], 'admin_triggers': {}, 'source': None}
    with open(KNOWLEDGE_BASE_PATH, 'r', encoding='utf-8') as file:
        return json.load(file)

KNOWLEDGE_BASE = load_knowledge_base()

def load_clinic_knowledge_base():
    if not os.path.exists(CLINIC_KNOWLEDGE_BASE_PATH):
        return {'entries': [], 'source_files': []}
    with open(CLINIC_KNOWLEDGE_BASE_PATH, 'r', encoding='utf-8') as file:
        return json.load(file)

CLINIC_KNOWLEDGE_BASE = load_clinic_knowledge_base()

def all_knowledge_entries():
    clinic_entries = CLINIC_KNOWLEDGE_BASE.get('entries', [])
    legacy_entries = KNOWLEDGE_BASE.get('entries', [])
    return clinic_entries + legacy_entries

def canonicalize_text(text):
    normalized = text.lower()
    replacements = {
        'лечние': 'лечение',
        'личение': 'лечение',
        'лечениее': 'лечение',
        'обследованией': 'обследований',
        'резултаты': 'результаты'
    }
    for typo, replacement in replacements.items():
        normalized = normalized.replace(typo, replacement)
    return normalized

def tokenize_ru(text):
    return {
        token
        for token in re.findall(r'[a-zа-яё0-9]+', canonicalize_text(text))
        if len(token) >= 3 and token not in STOP_WORDS
    }

def entry_search_text(entry):
    return ' '.join([
        entry.get('question', ''),
        ' '.join(entry.get('variations', [])),
        ' '.join(entry.get('key_points', [])),
        entry.get('answer', '')[:800]
    ])

def find_knowledge_entry(question):
    query_tokens = tokenize_ru(question)
    if not query_tokens:
        return None

    normalized_question = canonicalize_text(question)
    best_entry = None
    best_score = 0

    for entry in all_knowledge_entries():
        candidates = [entry.get('question', '')] + entry.get('variations', [])
        phrase_bonus = 0
        for candidate in candidates:
            candidate_lower = candidate.lower()
            if candidate_lower and (candidate_lower in normalized_question or normalized_question in candidate_lower):
                phrase_bonus = 8
                break

        title_tokens = tokenize_ru(' '.join(candidates))
        entry_tokens = tokenize_ru(entry_search_text(entry))
        title_overlap = len(query_tokens & title_tokens)
        body_overlap = len(query_tokens & entry_tokens)
        priority_bonus = min(int(entry.get('priority', 0)) / 10, 6)
        score = (title_overlap * 3) + (body_overlap * 0.5) + phrase_bonus + priority_bonus
        if score > best_score:
            best_score = score
            best_entry = entry

    threshold = 3 if best_entry and best_entry.get('source') else 3
    if best_entry and (best_score >= threshold or (best_score >= 1 and len(query_tokens) <= 3 and '?' in normalized_question)):
        return {'entry': best_entry, 'score': best_score}
    return None

def clean_knowledge_answer(answer):
    internal_markers = [
        'дать разрешение', 'блокировать', 'далее запрет', 'запрет информации',
        'внести ', '???', 'бот:', 'выберите раздел:', 'выберите вопрос:'
    ]
    cleaned_lines = []
    for line in answer.splitlines():
        normalized = line.strip().lower()
        if not normalized:
            continue
        if any(marker in normalized for marker in internal_markers):
            continue
        cleaned_lines.append(line.strip())
    return '\n'.join(cleaned_lines).strip()

def knowledge_response(entry):
    answer = clean_knowledge_answer(entry.get('answer', ''))
    return answer or entry.get('answer', '')

def is_short_topic_fragment(text):
    tokens = tokenize_ru(text)
    return 0 < len(tokens) <= 2 and bool(tokens & SHORT_TOPIC_WORDS)

def looks_like_knowledge_question(text):
    normalized = canonicalize_text(text).strip()
    if '?' in normalized:
        return True
    question_starts = (
        'что ', 'как ', 'где ', 'когда ', 'зачем ', 'почему ',
        'сколько ', 'нужно ли ', 'можно ли '
    )
    if normalized.startswith(question_starts):
        return True
    if is_short_topic_fragment(normalized):
        return False
    tokens = tokenize_ru(normalized)
    return bool((tokens & MEDICAL_QUESTION_KEYWORDS) or (tokens & SERVICE_QUESTION_KEYWORDS))

def contains_any(text, phrases):
    normalized = canonicalize_text(text)
    return any(phrase in normalized for phrase in phrases)

def detect_pain_context(text):
    normalized = canonicalize_text(text)
    tokens = set(re.findall(r'[a-zа-яё0-9]+', normalized))
    has_pain = bool(tokens & set(PAIN_WORDS))
    if not has_pain:
        return None
    if tokens & set(CHEST_WORDS):
        return 'chest_pain'
    if 'невыносим' in normalized or ('сильн' in normalized and 'обезбол' in normalized):
        return 'severe_pain'
    return 'pain'

def detect_red_flag(text):
    normalized = canonicalize_text(text)
    pain_context = detect_pain_context(text)
    if pain_context == 'chest_pain':
        return 'chest_pain'
    if contains_any(normalized, DYSPNEA_WORDS):
        return 'dyspnea'
    if contains_any(normalized, FAINTING_WORDS):
        return 'fainting'
    if contains_any(normalized, BLEEDING_WORDS):
        if contains_any(normalized, SEVERE_BLEEDING_WORDS):
            return 'severe_bleeding'
        return 'bleeding'
    if contains_any(normalized, FEVER_WORDS) and ('хими' in normalized or re.search(r'3[7-9][,.]?\d?', normalized)):
        return 'post_chemo_fever'
    if pain_context == 'severe_pain':
        return 'severe_pain'
    if contains_any(normalized, ACUTE_CRISIS_WORDS):
        return 'acute_crisis'
    return None

def red_flag_response(flag):
    responses = {
        'chest_pain': 'Боль в груди требует немедленной медицинской помощи. Пожалуйста, вызовите скорую помощь или обратитесь в приёмный покой. Не ждите, пока пройдёт само.',
        'dyspnea': 'Затруднённое дыхание — это серьёзный симптом. Пожалуйста, немедленно вызовите скорую помощь или обратитесь в приёмный покой.',
        'fainting': 'Потеря сознания — это серьёзный симптом. Пожалуйста, немедленно вызовите скорую помощь.',
        'severe_bleeding': 'Сильное кровотечение требует немедленной помощи. Вызовите скорую помощь.',
        'bleeding': 'Кровотечение нужно показать врачу. Обратитесь к вашему онкологу на плановый приём.',
        'post_chemo_fever': 'Повышение температуры выше 37°C после химиотерапии требует внимания врача. Пожалуйста, как можно скорее обратитесь к вашему онкологу или химиотерапевту.',
        'severe_pain': 'Сильная боль, особенно если обезболивающие не помогают, требует срочного обращения к врачу. Пожалуйста, свяжитесь с лечащим врачом как можно скорее.',
        'acute_crisis': 'Расскажите, что именно вас беспокоит: боль, затруднённое дыхание, головокружение? Если вы не можете описать состояние или оно быстро ухудшается, пожалуйста, вызовите скорую помощь или обратитесь в приёмный покой.'
    }
    return responses[flag]

def deterministic_support_response(text, emotion, triggers, recent_messages):
    normalized = canonicalize_text(text)
    red_flag = detect_red_flag(text)
    if red_flag:
        return red_flag_response(red_flag)

    pain_context = detect_pain_context(text)

    if normalized in ('нет', 'не знаю', 'пока нет'):
        return (
            'Хорошо, не будем давить. Тогда можно начать с простого: сейчас вам больше нужна эмоциональная поддержка, помощь с маршрутом '
            'или понять, когда обращаться к врачу срочно? Можно ответить одним словом.'
        )

    if 'плохо себя чувствую' in normalized or 'плохо чувствую' in normalized:
        return (
            'Мне жаль, что вам сегодня плохо. Давайте сначала отделим срочное от несрочного: есть ли сильная боль, одышка, высокая температура, '
            'резкая слабость, кровотечение или ощущение, что состояние быстро ухудшается? Если да — лучше сразу связаться с врачом или обратиться за неотложной помощью. '
            'Если нет, напишите, пожалуйста, это больше физическое недомогание или эмоционально тяжело?'
        )

    if contains_any(normalized, TREATMENT_REFUSAL_WORDS):
        return (
            'Я понимаю, как вам тяжело. Мысли об отказе часто появляются, когда сил совсем не остаётся. '
            'Давайте разберём, что именно вас истощает? Что именно в лечении кажется невыносимым? '
            'Очень рекомендую обратиться к психотерапевту — он поможет разобраться с этими чувствами и найти опору.'
        )

    if contains_any(normalized, NEW_DIAGNOSIS_WORDS):
        return (
            'Я понимаю, как это страшно и тяжело сейчас. Шок и растерянность — абсолютно нормальная реакция на такую новость. '
            'Вы не одни — я буду с вами на всех этапах. Как вы сейчас себя чувствуете? Хотите поговорить о том, что сейчас происходит внутри? '
            'Если вам хочется разобраться, что делать дальше, я помогу с планом.'
        )

    if contains_any(normalized, WAITING_RESULTS_WORDS):
        return (
            'Ожидание результатов — один из самых сложных периодов. Неопределённость и тревога в такой ситуации совершенно естественны. '
            'Гистологическое исследование обычно занимает около 10 рабочих дней. Сколько дней уже прошло с момента забора материала? '
            'Если тревога мешает спать, есть или выходить из дома, лучше обсудить это с психотерапевтом.'
        )

    if contains_any(normalized, CHEMO_FEAR_WORDS):
        return (
            'Понимаю ваш страх — химиотерапия вызывает много тревоги, особенно когда вокруг много пугающих рассказов. '
            'Ваш страх абсолютно естественен. Что именно вас больше всего пугает? Вы уже говорили с химиотерапевтом? '
            'Он может ответить на ваши вопросы о том, чего ожидать.'
        )

    if contains_any(normalized, TREATMENT_DOUBT_WORDS):
        return (
            'Понимаю, почему может появляться мысль, что лечение не помогает и силы уходят зря. Такое чувство часто возникает, когда нет быстрых видимых изменений '
            'или приходится много времени проводить в больнице. Я не могу оценить, помогает лечение или нет, но это важный вопрос для лечащего врача. '
            'Можно прямо спросить: по каким признакам оценивают эффективность, когда ждать контрольные обследования и что будут делать, если текущая схема не подходит. '
            'Я могу помочь сформулировать эти вопросы коротко.'
        )

    if pain_context == 'chest_pain':
        return (
            'Боль в груди требует немедленной медицинской помощи. Пожалуйста, вызовите скорую помощь или обратитесь в приёмный покой. Не ждите, пока пройдёт само.'
        )

    if pain_context == 'pain':
        return (
            'Мне очень жаль, что вам больно. Боль обязательно нужно сообщить вашему лечащему врачу — её не нужно терпеть, её можно и нужно контролировать. '
            'Насколько сильная боль: терпимая, сильная или невыносимая? Когда она началась? Принимаете ли вы сейчас обезболивающие?'
        )

    if contains_any(normalized, NEXT_STEP_WORDS):
        opening = 'Понимаю, как страшно и растерянно может быть сразу после такой новости. ' if emotion in ('scared', 'anxious', 'hopeless') else ''
        return (
            f'{opening}Самый практичный следующий шаг — собрать все результаты обследований '
            'и записаться к лечащему онкологу или онкологу по месту жительства. На приеме стоит уточнить три вещи: подтвержден ли диагноз гистологией, '
            'нужны ли дополнительные обследования для стадии и когда ваш случай будет обсуждаться на МДГ/консилиуме. '
            'Я могу помочь составить короткий список вопросов врачу.'
        )

    if contains_any(normalized, UNCERTAINTY_WORDS):
        return (
            'Неизвестность правда сильно тревожит. Давайте разложим ближайший маршрут: 1) уточнить, кто ваш лечащий онколог, '
            '2) взять с собой все анализы, выписки и снимки, 3) спросить, какие обследования нужны до решения о лечении, '
            '4) узнать дату следующего приема или консилиума. Если хотите, напишите, какие документы или назначения у вас уже есть.'
        )

    if is_short_topic_fragment(normalized):
        if 'лечение' in normalized:
            return (
                'Про лечение лучше говорить чуть конкретнее, потому что варианты зависят от диагноза, стадии и результатов обследований. '
                'Обычно план определяет онколог или мультидисциплинарная группа. Сейчас полезно спросить врача: какой метод предлагают, зачем он нужен, '
                'какие обследования нужны до начала и когда старт. Что именно про лечение вас тревожит больше всего?'
            )
        is_direct_question = '?' in normalized or normalized.startswith(('где ', 'как ', 'когда ', 'что '))
        if ('результаты' in normalized or 'обследования' in normalized) and not is_direct_question:
            return (
                'Ожидание и непонимание результатов часто усиливают тревогу. Практически сейчас можно сделать так: уточнить у медсестры или врача, '
                'где смотреть результаты, когда они будут готовы и кто их объяснит. Если результат уже есть, лучше не расшифровывать его в одиночку, '
                'а записать вопросы и обсудить с онкологом.'
            )
        if 'страх' in normalized:
            return fallback_ai_response(text, 'scared', triggers)

    return None

def should_use_knowledge_base(text, emotion):
    if emotion in ('scared', 'anxious', 'hopeless', 'sad') and not looks_like_knowledge_question(text):
        return False
    if detect_pain_context(text):
        return False
    return looks_like_knowledge_question(text)

def detect_admin_alerts(text):
    normalized = canonicalize_text(text)
    alerts = []
    red_flag = detect_red_flag(text)
    if red_flag in ('chest_pain', 'dyspnea', 'fainting', 'severe_bleeding', 'post_chemo_fever', 'severe_pain'):
        alerts.append(red_flag)
    if contains_any(normalized, TREATMENT_REFUSAL_WORDS):
        alerts.append('отказ от лечения')

    triggers = KNOWLEDGE_BASE.get('admin_triggers', {})
    labels = {
        'suicidal': 'суицидальные мысли',
        'treatment_refusal': 'отказ от лечения',
        'acute_crisis': 'острый кризис'
    }
    for key, phrases in triggers.items():
        if key == 'prohibited_phrases':
            continue
        if any(phrase.lower() in normalized for phrase in phrases):
            alerts.append(labels.get(key, key))
    return list(dict.fromkeys(alerts))

def crisis_response(alerts):
    red_flags = ['chest_pain', 'dyspnea', 'fainting', 'severe_bleeding', 'post_chemo_fever', 'severe_pain']
    for flag in red_flags:
        if flag in alerts:
            return red_flag_response(flag)
    if 'суицидальные мысли' in alerts:
        return ('Мне очень жаль, что вам так тяжело. То, что вы чувствуете — это серьёзно, и вам нужна помощь специалиста. '
                'Пожалуйста, обратитесь к психотерапевту или психиатру как можно скорее. Я здесь, чтобы поддержать вас.')
    if 'острый кризис' in alerts:
        return red_flag_response('acute_crisis')
    return ('Я понимаю, как вам тяжело. Мысли об отказе часто появляются, когда сил совсем не остаётся. '
            'Давайте разберём, что именно вас истощает? Очень рекомендую обратиться к психотерапевту — он поможет разобраться с этими чувствами и найти опору.')

def analyze_emotion(text):
    """Простой словарный анализ эмоций для MVP."""
    normalized = canonicalize_text(text)
    scores = {
        emotion: sum(1 for keyword in keywords if keyword in normalized)
        for emotion, keywords in EMOTION_KEYWORDS.items()
    }
    emotion, score = max(scores.items(), key=lambda item: item[1])
    return emotion if score > 0 else 'neutral'

def detect_triggers(text):
    """Находит онкологические триггеры в сообщении пациента."""
    normalized = canonicalize_text(text)
    return [
        trigger
        for trigger, keywords in ONCOLOGY_TRIGGERS.items()
        if any(keyword in normalized for keyword in keywords)
    ]

def save_conversation_message(session_id, sender, text, emotion=None, triggers=None):
    triggers_json = json.dumps(triggers or [], ensure_ascii=False)
    conn = get_db_connection()
    if not DATABASE_URL or 'sqlite' in DATABASE_URL:
        conn.execute('''INSERT INTO conversations (session_id, sender, text, emotion, triggers)
                        VALUES (?, ?, ?, ?, ?)''', (session_id, sender, text, emotion, triggers_json))
    else:
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO conversations (session_id, sender, text, emotion, triggers)
                          VALUES (%s, %s, %s, %s, %s)''', (session_id, sender, text, emotion, triggers_json))
    conn.commit()
    conn.close()

def get_recent_messages(session_id, limit=8):
    conn = get_db_connection()
    if not DATABASE_URL or 'sqlite' in DATABASE_URL:
        cursor = conn.execute('''SELECT sender, text FROM conversations
                                 WHERE session_id = ?
                                 ORDER BY id DESC LIMIT ?''', (session_id, limit))
        rows = cursor.fetchall()
    else:
        cursor = conn.cursor()
        cursor.execute('''SELECT sender, text FROM conversations
                          WHERE session_id = %s
                          ORDER BY id DESC LIMIT %s''', (session_id, limit))
        rows = cursor.fetchall()
    conn.close()
    return list(reversed([dict(row) for row in rows]))

def build_ai_prompt(user_text, emotion, triggers, recent_messages):
    history = '\n'.join(
        f"{'Пациент' if item['sender'] == 'user' else 'Ассистент'}: {item['text']}"
        for item in recent_messages
    )
    trigger_text = ', '.join(TRIGGER_LABELS[item] for item in triggers) if triggers else 'не выявлены'
    prohibited = '; '.join(KNOWLEDGE_BASE.get('admin_triggers', {}).get('prohibited_phrases', []))
    return f"""Ты русскоязычный ИИ-помощник онкологического центра.
Твоя задача: эмоциональная поддержка пациента и мягкая маршрутизация по клинике.

Правила:
- отвечай тепло, спокойно, коротко и по-человечески;
- не ставь диагнозы, не назначай и не отменяй лечение;
- при сильной боли, резком ухудшении, суицидальных мыслях или угрозе жизни советуй срочно обратиться к врачу, в приемное отделение или экстренные службы;
- если вопрос медицинский, предлагай обсудить его с лечащим врачом;
- если уместно, предложи один маленький следующий шаг.
- не используй запрещенные фразы: {prohibited}.

Текущее состояние пациента: {EMOTION_LABELS.get(emotion, emotion)}.
Выявленные триггеры: {trigger_text}.

Короткая история диалога:
{history}

Новое сообщение пациента: {user_text}

Ответ:"""

def fallback_ai_response(user_text, emotion, triggers):
    if emotion in ('scared', 'anxious'):
        base = 'Похоже, сейчас много тревоги и страха. Это понятная реакция в такой ситуации.'
    elif emotion == 'hopeless':
        base = 'Мне очень жаль, что сейчас ощущается так тяжело. В такие моменты важно не оставаться одному с этим состоянием.'
    elif emotion == 'sad':
        base = 'Слышу, что вам сейчас грустно и тяжело. Спасибо, что написали об этом.'
    elif emotion == 'happy':
        base = 'Рад, что у вас появилось немного больше опоры. Это правда важно.'
    else:
        base = 'Я рядом и готов вас выслушать.'

    if 'pain_concern' in triggers:
        return f'{base} Если боль усиливается или не проходит, пожалуйста, свяжитесь с лечащим врачом или обратитесь за неотложной помощью. Можем вместе сформулировать, что именно сказать врачу.'
    if 'death_anxiety' in triggers or 'hope_loss' in triggers:
        return f'{base} Если появляются мысли причинить себе вред или ощущение, что вы не справитесь, пожалуйста, сразу обратитесь к близкому человеку, врачу или в экстренную службу. Сейчас можно начать с одного шага: написать, что больше всего пугает в эту минуту.'
    return f'{base} Можете написать, что именно беспокоит сильнее всего: лечение, результаты обследований, боль, семья или дорога по клинике.'

def has_cjk_text(text):
    return bool(re.search(r'[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]', text))

def generate_ai_response(user_text, emotion, triggers, session_id):
    prompt = build_ai_prompt(user_text, emotion, triggers, get_recent_messages(session_id))
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                'model': OLLAMA_MODEL,
                'prompt': prompt,
                'stream': False,
                'options': {'temperature': 0.4, 'num_predict': 350}
            },
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        answer = data.get('response', '').strip()
        if answer and not has_cjk_text(answer):
            return answer, 'ollama'
    except requests.RequestException:
        pass

    return fallback_ai_response(user_text, emotion, triggers), 'fallback'

# ========== МАРШРУТЫ ========== #

@app.route('/')
def index():
    """Главная страница с авторизацией"""
    if 'user_id' in session:
        return redirect(url_for('chat'))
    return render_template('index.html')

@app.route('/chat')
def chat():
    """Основной чат с тремя панелями"""
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('chat.html')

@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Проверка статуса авторизации"""
    if 'user_id' in session:
        conn = get_db_connection()
        if not DATABASE_URL or 'sqlite' in DATABASE_URL:
            cursor = conn.execute('SELECT * FROM users WHERE user_id = ?', (session['user_id'],))
            user = cursor.fetchone()
        else:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = %s', (session['user_id'],))
            user = cursor.fetchone()
        conn.close()
        
        if user:
            return jsonify({
                'authenticated': True,
                'user_id': session['user_id'],
                'subscription_status': user['subscription_status'] if user['subscription_status'] else 'free',
                'diagnosis': user['diagnosis'],
                'route_stage': user['route_stage']
            })
    
    return jsonify({
        'authenticated': False,
        'subscription_status': 'free'
    })

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Авторизация по ID от врача"""
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'error': 'Требуется ID пользователя'}), 400
    
    conn = get_db_connection()
    if not DATABASE_URL or 'sqlite' in DATABASE_URL:
        cursor = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            # Создаем нового пользователя
            session_id = str(uuid.uuid4())
            conn.execute('''INSERT INTO users (user_id, session_id, subscription_status) 
                           VALUES (?, ?, ?)''', (user_id, session_id, 'demo'))
            conn.commit()
            user_data = {'user_id': user_id, 'session_id': session_id, 'subscription_status': 'demo'}
        else:
            user_data = dict(user)
    else:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            session_id = str(uuid.uuid4())
            cursor.execute('''INSERT INTO users (user_id, session_id, subscription_status) 
                             VALUES (%s, %s, %s)''', (user_id, session_id, 'demo'))
            conn.commit()
            user_data = {'user_id': user_id, 'session_id': session_id, 'subscription_status': 'demo'}
        else:
            user_data = dict(user)
    
    conn.close()
    
    # Устанавливаем сессию
    session['user_id'] = user_data['user_id']
    session['session_id'] = user_data['session_id']
    
    return jsonify({
        'success': True,
        'subscription_status': user_data['subscription_status'],
        'redirect_url': '/chat'
    })

@app.route('/api/auth/register-demo', methods=['POST'])
def register_demo():
    """Регистрация демо-пользователя"""
    demo_id = 'DEMO_' + str(uuid.uuid4())[:8]
    
    conn = get_db_connection()
    session_id = str(uuid.uuid4())
    
    if not DATABASE_URL or 'sqlite' in DATABASE_URL:
        conn.execute('''INSERT INTO users (user_id, session_id, subscription_status) 
                       VALUES (?, ?, ?)''', (demo_id, session_id, 'demo'))
    else:
        conn.execute('''INSERT INTO users (user_id, session_id, subscription_status) 
                       VALUES (%s, %s, %s)''', (demo_id, session_id, 'demo'))
    
    conn.commit()
    conn.close()
    
    # Устанавливаем сессию
    session['user_id'] = demo_id
    session['session_id'] = session_id
    
    return jsonify({
        'success': True,
        'user_id': demo_id,
        'redirect_url': '/chat'
    })

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Выход из аккаунта"""
    session.pop('user_id', None)
    session.pop('session_id', None)
    return jsonify({'success': True, 'redirect_url': '/'})

# ========== МАРШРУТНЫЙ ФУНКЦИОНАЛ ========== #

@app.route('/api/route/setup', methods=['POST'])
def setup_route():
    """Настройка маршрута пациента через чат"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
    
    data = request.json
    diagnosis = data.get('diagnosis')
    stage = data.get('stage')
    procedures = data.get('procedures', [])
    
    conn = get_db_connection()
    if not DATABASE_URL or 'sqlite' in DATABASE_URL:
        conn.execute('''UPDATE users SET diagnosis = ?, route_stage = ? 
                       WHERE user_id = ?''', (diagnosis, stage, session['user_id']))
        
        # Очищаем старые назначения
        conn.execute('DELETE FROM appointments WHERE user_id = ?', (session['user_id'],))
        
        # Добавляем новые процедуры
        for proc in procedures:
            conn.execute('''INSERT INTO appointments (user_id, procedure, status) 
                           VALUES (?, ?, ?)''', (session['user_id'], proc, 'scheduled'))
    else:
        conn.execute('''UPDATE users SET diagnosis = %s, route_stage = %s 
                       WHERE user_id = %s''', (diagnosis, stage, session['user_id']))
        
        cursor = conn.cursor()
        cursor.execute('DELETE FROM appointments WHERE user_id = %s', (session['user_id'],))
        
        for proc in procedures:
            cursor.execute('''INSERT INTO appointments (user_id, procedure, status) 
                             VALUES (%s, %s, %s)''', (session['user_id'], proc, 'scheduled'))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Маршрут настроен успешно!'})

@app.route('/api/route/current', methods=['GET'])
def get_current_route():
    """Получение текущего маршрута пациента"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
    
    conn = get_db_connection()
    if not DATABASE_URL or 'sqlite' in DATABASE_URL:
        cursor = conn.execute('''SELECT u.diagnosis, u.route_stage, a.procedure, a.appointment_date, a.status 
                                 FROM users u 
                                 LEFT JOIN appointments a ON u.user_id = a.user_id 
                                 WHERE u.user_id = ? 
                                 ORDER BY a.id''', (session['user_id'],))
        rows = cursor.fetchall()
    else:
        cursor = conn.cursor()
        cursor.execute('''SELECT u.diagnosis, u.route_stage, a.procedure, a.appointment_date, a.status 
                         FROM users u 
                         LEFT JOIN appointments a ON u.user_id = a.user_id 
                         WHERE u.user_id = %s 
                         ORDER BY a.id''', (session['user_id'],))
        rows = cursor.fetchall()
    
    conn.close()
    
    # Формируем ответ
    user_info = dict(rows[0]) if rows else {}
    appointments = []
    for row in rows:
        if row['procedure']:
            appointments.append({
                'procedure': row['procedure'],
                'date': row['appointment_date'],
                'status': row['status']
            })
    
    preparation_info = {}
    if user_info.get('diagnosis') and user_info['diagnosis'] in UROLOGY_ROUTES:
        preparation_info = UROLOGY_ROUTES[user_info['diagnosis']]['preparations']
    
    return jsonify({
        'success': True,
        'route': {
            'diagnosis': user_info.get('diagnosis'),
            'stage': user_info.get('route_stage'),
            'appointments': appointments,
            'preparations': preparation_info
        }
    })

@app.route('/api/route/chat', methods=['POST'])
def route_chat():
    """Чат по маршрутным вопросам"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401
    
    data = request.json
    question = data.get('question', '')
    knowledge_match = find_knowledge_entry(question)
    
    # Простой роутер вопросов
    question_lower = question.lower()
    source = 'route_rules'
    
    if 'пса' in question_lower and ('подготовка' in question_lower or 'готовить' in question_lower):
        response = "Для сдачи ПСА необходимо голодать 8 часов. Не катетеризировать мочевой пузырь перед исследованием. При себе иметь направление и паспорт."
    elif 'биопси' in question_lower and ('готовить' in question_lower or 'подготовка' in question_lower):
        response = "Подготовка к биопсии: за 3 дня прекратить прием антикоагулянтов. Вечером накануне - легкий ужин. Утром натощак. При себе анализы крови и направление."
    elif 'мрт' in question_lower and ('подготовка' in question_lower):
        response = "К МРТ малого таза: при себе направление и паспорт. Без металлических предметов (часы, украшения). Полный мочевой пузырь не требуется."
    elif 'уролог' in question_lower and ('куда' in question_lower or 'адрес' in question_lower):
        response = "Отделение урологии находится на 3 этаже, кабинет 305. Часы работы: пн-пт 8:00-17:00. Запись по телефону: 55-55-55"
    elif 'результа' in question_lower and ('когда' in question_lower or 'срок' in question_lower):
        response = "Сроки получения результатов: ПСА - 2 рабочих дня, УЗИ - сразу, МРТ - 3 рабочих дня, биопсия - 5 рабочих дней."
    elif knowledge_match:
        response = knowledge_response(knowledge_match['entry'])
        source = 'knowledge_base'
    else:
        response = "Я помогу вам с маршрутом лечения. Вы можете спросить о подготовке к обследованиям, сроках получения результатов или адресах отделений. Что вас интересует?"
    
    return jsonify({
        'success': True,
        'response': response,
        'knowledge_id': knowledge_match['entry']['id'] if knowledge_match and source == 'knowledge_base' else None,
        'source': source
    })

# ========== СУЩЕСТВУЮЩИЙ КОД ЧАТА ========== #
# (оставляем все остальные функции как есть)

@app.route('/api/messages', methods=['GET'])
def get_messages():
    if 'session_id' not in session:
        return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401

    messages = get_recent_messages(session['session_id'], limit=50)
    return jsonify({'success': True, 'messages': messages})

@app.route('/api/send', methods=['POST'])
def send_message():
    if 'session_id' not in session:
        return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401

    data = request.json or {}
    text = data.get('text', '').strip()
    if not text:
        return jsonify({'success': False, 'error': 'Сообщение не должно быть пустым'}), 400

    emotion = analyze_emotion(text)
    triggers = detect_triggers(text)
    admin_alerts = detect_admin_alerts(text)
    session_id = session['session_id']
    recent_messages = get_recent_messages(session_id)
    deterministic_response = deterministic_support_response(text, emotion, triggers, recent_messages)
    knowledge_match = find_knowledge_entry(text) if should_use_knowledge_base(text, emotion) else None

    save_conversation_message(session_id, 'user', text, emotion, triggers)
    if admin_alerts:
        response_text = crisis_response(admin_alerts)
        source = 'crisis_rules'
    elif deterministic_response:
        response_text = deterministic_response
        source = 'support_rules'
    elif knowledge_match:
        response_text = knowledge_response(knowledge_match['entry'])
        source = 'knowledge_base'
    else:
        response_text, source = generate_ai_response(text, emotion, triggers, session_id)
    save_conversation_message(session_id, 'ai', response_text, emotion, triggers)

    return jsonify({
        'success': True,
        'response': response_text,
        'emotion': emotion,
        'emotion_label': EMOTION_LABELS.get(emotion, emotion),
        'triggers': triggers,
        'trigger_labels': [TRIGGER_LABELS[item] for item in triggers],
        'admin_alerts': admin_alerts,
        'knowledge_id': knowledge_match['entry']['id'] if knowledge_match and source == 'knowledge_base' else None,
        'source': source
    })

@app.route('/api/status', methods=['GET'])
def get_status():
    if 'session_id' not in session:
        return jsonify({'success': False, 'error': 'Требуется авторизация'}), 401

    conn = get_db_connection()
    if not DATABASE_URL or 'sqlite' in DATABASE_URL:
        cursor = conn.execute('''SELECT emotion, triggers, timestamp FROM conversations
                                 WHERE session_id = ? AND sender = 'user'
                                 ORDER BY id DESC LIMIT 1''', (session['session_id'],))
        row = cursor.fetchone()
    else:
        cursor = conn.cursor()
        cursor.execute('''SELECT emotion, triggers, timestamp FROM conversations
                          WHERE session_id = %s AND sender = 'user'
                          ORDER BY id DESC LIMIT 1''', (session['session_id'],))
        row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({'success': True, 'status': 'neutral', 'triggers': []})

    data = dict(row)
    triggers = json.loads(data.get('triggers') or '[]')
    return jsonify({
        'success': True,
        'status': data.get('emotion') or 'neutral',
        'emotion_label': EMOTION_LABELS.get(data.get('emotion'), data.get('emotion')),
        'triggers': triggers,
        'trigger_labels': [TRIGGER_LABELS[item] for item in triggers],
        'timestamp': data.get('timestamp')
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
