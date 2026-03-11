import random
import re
import sqlite3
from datetime import datetime, timedelta
from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text, Callback

# Импортируем утилиты и start модуль
from utils import (
    format_number, parse_amount_with_suffix,
    format_transaction_message
)
import start

# Конфигурация бота
TOKEN = "ВАШ_ТОКЕН_ГРУППЫ"  # Замените на токен вашей группы
bot = Bot(token=TOKEN)

# Список мастей (только текст, без эмодзи)
SUITS = ["Вор в законе", "Блатной", "Мужик", "Козел", "Петух"]

# Функция для проверки допустимых символов (только русские и английские буквы)
def is_valid_name(name):
    pattern = r'^[а-яА-Яa-zA-Z\s-]+$'
    return bool(re.match(pattern, name)) and len(name) <= 50

# Функция для получения ID из упоминания или ответа
async def get_target_user(message: Message):
    """Получает целевого пользователя из ответа или упоминания"""
    # Если это ответ на сообщение
    if message.reply_message:
        return message.reply_message.from_id
    
    # Если есть упоминание в тексте
    if message.text and '[' in message.text and '|' in message.text:
        # Ищем паттерн [id123|Имя]
        pattern = r'\[id(\d+)\|.*?\]'
        match = re.search(pattern, message.text)
        if match:
            return int(match.group(1))
    
    return None

# Инициализация базы данных
def init_database():
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    # Создаем таблицу для пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            vk_name TEXT NOT NULL,
            vk_last_name TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            article TEXT NOT NULL,
            prison_id INTEGER UNIQUE,
            cigarettes INTEGER DEFAULT 0,
            dollars REAL DEFAULT 0,
            suit TEXT DEFAULT 'Петух',
            authority INTEGER DEFAULT 0,
            total_donations INTEGER DEFAULT 0,
            
            -- Счетчики для заданий
            daily_malyava INTEGER DEFAULT 0,
            daily_donations INTEGER DEFAULT 0,
            daily_bonus INTEGER DEFAULT 0,
            daily_chifir INTEGER DEFAULT 0,
            daily_read INTEGER DEFAULT 0,
            
            -- Время последнего обновления заданий
            last_daily_reset TIMESTAMP,
            
            -- Кулдауны
            last_bonus TIMESTAMP,
            last_malyava TIMESTAMP,
            last_chifir TIMESTAMP,
            last_read TIMESTAMP,
            
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_registered INTEGER DEFAULT 1
        )
    ''')
    
    # Создаем таблицу для общака
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS obshak (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total_cigarettes INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Создаем таблицу для донатов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            donation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Проверяем, есть ли запись в общаке
    cursor.execute("SELECT * FROM obshak WHERE id = 1")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO obshak (id, total_cigarettes) VALUES (1, 0)")
    
    conn.commit()
    conn.close()
    print("База данных инициализирована")

# Функции для работы с авторитетом и заданиями
def reset_daily_tasks(user_id):
    """Сброс ежедневных заданий"""
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE users SET 
        daily_malyava = 0,
        daily_donations = 0,
        daily_bonus = 0,
        daily_chifir = 0,
        daily_read = 0,
        last_daily_reset = CURRENT_TIMESTAMP
        WHERE user_id = ?
    ''', (user_id,))
    
    conn.commit()
    conn.close()

def check_and_reset_daily(user_id):
    """Проверяет, нужно ли сбросить ежедневные задания (сброс в 00:01)"""
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT last_daily_reset FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    conn.close()
    
    if result and result[0]:
        last_reset = datetime.fromisoformat(result[0].replace(' ', 'T'))
        now = datetime.now()
        
        # Создаем время сегодняшнего сброса (00:01)
        today_reset = datetime(now.year, now.month, now.day, 0, 1, 0)
        
        # Если сейчас позже времени сброса и последний сброс был до сегодняшнего сброса
        if now >= today_reset and last_reset < today_reset:
            reset_daily_tasks(user_id)
            return True
    else:
        # Если никогда не сбрасывали
        reset_daily_tasks(user_id)
        return True
    return False

def get_suit_by_authority(authority):
    """Получение масти по уровню авторитета (от 0 до 5)"""
    if authority >= 5:
        return SUITS[0]  # Вор в законе
    elif authority >= 4:
        return SUITS[1]  # Блатной
    elif authority >= 2:
        return SUITS[2]  # Мужик
    elif authority >= 1:
        return SUITS[3]  # Козел
    else:
        return SUITS[4]  # Петух

def add_authority(user_id, amount=1):
    """Добавление авторитета (не больше 5)"""
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT authority FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if result:
        current_auth = result[0]
        new_auth = min(current_auth + amount, 5)
        
        # Получаем новую масть
        new_suit = get_suit_by_authority(new_auth)
        
        cursor.execute('''
            UPDATE users 
            SET authority = ?, suit = ? 
            WHERE user_id = ?
        ''', (new_auth, new_suit, user_id))
        
        conn.commit()
        conn.close()
        return new_auth
    conn.close()
    return 0

def get_daily_progress(user_id):
    """Получение прогресса ежедневных заданий"""
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT daily_malyava, daily_donations, daily_bonus, 
               daily_chifir, daily_read 
        FROM users WHERE user_id = ?
    ''', (user_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'malyava': result[0],
            'donations': result[1],
            'bonus': result[2],
            'chifir': result[3],
            'read': result[4]
        }
    return None

def update_daily_progress(user_id, task, max_value, increment=1):
    """Обновление прогресса задания и проверка на выполнение"""
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    # Получаем текущее значение
    cursor.execute(f"SELECT {task}, authority FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    if result:
        current = result[0]
        current_auth = result[1]
        
        if current < max_value:
            new_value = min(current + increment, max_value)
            cursor.execute(f"UPDATE users SET {task} = ? WHERE user_id = ?", (new_value, user_id))
            
            # Если задание выполнено (достигнут максимум), добавляем авторитет
            if new_value >= max_value and current_auth < 5:
                add_authority(user_id, 1)
    
    conn.commit()
    conn.close()

def get_tasks_text(user_id):
    """Получение текста с заданиями"""
    progress = get_daily_progress(user_id)
    if not progress:
        return "Ошибка получения заданий"
    
    tasks_text = (
        "📋 ЕЖЕДНЕВНЫЕ ЗАДАНИЯ\n\n"
        f"1. Раскидать малявы по камерам [{progress['malyava']}/5]\n"
        "   ❓ - Используйте команду Малява\n\n"
        f"2. Сделать пожертвование в общак [{progress['donations']}/150]\n"
        "   ❓ - Используйте команду Пожертвовать\n\n"
        f"3. Соберите ежедневный бонус [{progress['bonus']}/1]\n"
        "   ❓ - Используйте команду Бонус\n\n"
        f"4. Чифирните с блатными [{progress['chifir']}/5]\n"
        "   ❓ - Используйте команду Чифирнуть\n\n"
        f"5. Прочтите свежую газету [{progress['read']}/1]\n"
        "   ❓ - Используйте команду Почитать\n\n"
        "🏆 За каждое выполненное задание +1 к авторитету!"
    )
    
    return tasks_text

def get_next_reset_time():
    """Получение времени до следующего сброса"""
    now = datetime.now()
    tomorrow_reset = datetime(now.year, now.month, now.day, 0, 1, 0) + timedelta(days=1)
    time_diff = tomorrow_reset - now
    
    hours = int(time_diff.total_seconds() // 3600)
    minutes = int((time_diff.total_seconds() % 3600) // 60)
    
    return f"{hours}ч {minutes}мин"

# Получение данных пользователя
def get_user_data(user_id):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT vk_name, vk_last_name, first_name, last_name, article, 
               prison_id, cigarettes, dollars, suit, authority, total_donations,
               registration_date
        FROM users WHERE user_id = ?
    """, (user_id,))
    
    result = cursor.fetchone()
    conn.close()
    return result

# Получение имени пользователя для отображения
def get_user_display_name(user_id):
    """Получает отображаемое имя пользователя"""
    user_data = get_user_data(user_id)
    if user_data:
        return f"{user_data[2]} {user_data[3]}".strip()
    return "Неизвестно"

# Обновление имени пользователя
def update_first_name(user_id, new_name):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET first_name = ? WHERE user_id = ?", (new_name, user_id))
    conn.commit()
    conn.close()

# Обновление фамилии пользователя
def update_last_name(user_id, new_name):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_name = ? WHERE user_id = ?", (new_name, user_id))
    conn.commit()
    conn.close()

# Получение баланса сигарет
def get_cigarettes(user_id):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT cigarettes FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

# Получение баланса баксов
def get_dollars(user_id):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT dollars FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

# Получение баланса общака
def get_obshak_balance():
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT total_cigarettes FROM obshak WHERE id = 1")
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

# Получение общего количества донатов пользователя
def get_total_donations(user_id):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT total_donations FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

# Добавление сигарет
def add_cigarettes(user_id, amount):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET cigarettes = cigarettes + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# Снятие сигарет
def remove_cigarettes(user_id, amount):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET cigarettes = cigarettes - ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# Добавление баксов
def add_dollars(user_id, amount):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET dollars = dollars + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# Снятие баксов
def remove_dollars(user_id, amount):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET dollars = dollars - ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# Добавление в общак
def add_to_obshak(amount):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE obshak SET total_cigarettes = total_cigarettes + ?, last_updated = CURRENT_TIMESTAMP WHERE id = 1", (amount,))
    conn.commit()
    conn.close()

# Добавление записи о донате
def add_donation_record(user_id, amount):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO donations (user_id, amount) VALUES (?, ?)", (user_id, amount))
    cursor.execute("UPDATE users SET total_donations = total_donations + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# Обновление времени последнего действия
def update_last_bonus(user_id):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_bonus = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def update_last_malyava(user_id):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_malyava = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def update_last_chifir(user_id):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_chifir = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def update_last_read(user_id):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_read = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# Проверка кулдауна
def can_do_action(user_id, action, cooldown_hours):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    cursor.execute(f"SELECT last_{action} FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    conn.close()
    
    if result and result[0]:
        last_time = datetime.fromisoformat(result[0].replace(' ', 'T'))
        time_diff = datetime.now() - last_time
        return time_diff.total_seconds() >= cooldown_hours * 3600
    return True

def get_cooldown_time(user_id, action, cooldown_hours):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    cursor.execute(f"SELECT last_{action} FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    conn.close()
    
    if result and result[0]:
        last_time = datetime.fromisoformat(result[0].replace(' ', 'T'))
        time_diff = datetime.now() - last_time
        remaining = cooldown_hours * 3600 - time_diff.total_seconds()
        if remaining > 0:
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            return f"{hours}ч {minutes}мин"
    return "доступно"

# Список доступных команд
AVAILABLE_COMMANDS = [
    "профиль", "помощь", "имя", "фамилия", 
    "бонус", "малява", "продать", "пожертвовать", "общак",
    "чифирнуть", "почитать", "задания", "перевести"
]

# Создание клавиатуры с кнопкой назад
def get_back_keyboard(target_command=None):
    """Создает клавиатуру с кнопкой назад"""
    keyboard = Keyboard(inline=False)
    if target_command:
        keyboard.add(Callback("🔙 Назад", payload={"command": target_command}), color=KeyboardButtonColor.PRIMARY)
    else:
        keyboard.add(Callback("🔙 Назад", payload={"command": "back_to_main"}), color=KeyboardButtonColor.PRIMARY)
    return keyboard

# Создание основной клавиатуры
def get_main_keyboard():
    keyboard = Keyboard(inline=False)
    keyboard.add(Callback("📜 Профиль", payload={"command": "profile"}), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Callback("📑 Малява", payload={"command": "malyava"}), color=KeyboardButtonColor.SECONDARY)
    keyboard.row()
    keyboard.add(Callback("🎁 Бонус", payload={"command": "bonus"}), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Callback("📋 Задания", payload={"command": "tasks"}), color=KeyboardButtonColor.SECONDARY)
    keyboard.row()
    keyboard.add(Callback("☕ Чифирнуть", payload={"command": "chifir"}), color=KeyboardButtonColor.SECONDARY)
    keyboard.add(Callback("📰 Почитать", payload={"command": "read"}), color=KeyboardButtonColor.SECONDARY)
    keyboard.row()
    keyboard.add(Callback("❓ Помощь", payload={"command": "help"}), color=KeyboardButtonColor.PRIMARY)
    return keyboard

# Инициализация БД
init_database()

# Инициализируем обработчики start
start.init_start_handlers(bot)

# Обработчик callback-кнопок
@bot.on.callback_query()
async def handle_callback(call):
    user_id = call.from_id
    payload = call.payload
    
    if not payload or "command" not in payload:
        await call.answer("Ошибка")
        return
    
    command = payload["command"]
    
    # Проверяем и сбрасываем ежедневные задания
    check_and_reset_daily(user_id)
    
    if command == "profile":
        user_data = get_user_data(user_id)
        if user_data:
            current_first_name = user_data[2] if user_data[2] else user_data[0]
            current_last_name = user_data[3] if user_data[3] else user_data[1]
            article = user_data[4]
            prison_id = user_data[5]
            cigarettes = user_data[6]
            dollars = user_data[7]
            suit = user_data[8]
            authority = user_data[9]
            total_donations = user_data[10]
            reg_date = datetime.fromisoformat(user_data[11].replace(' ', 'T')).strftime("%d.%m.%Y")
            
            profile_text = (
                f"📑 Личное дело заключенного #{prison_id}\n"
                f"📒 Имя: {current_first_name}\n"
                f"📒 фамилия: {current_last_name}\n"
                f"⚖ Статья: {article}\n"
                f"📒 Под стражей с: {reg_date}\n"
                f"📜 Статус: Пожизненно\n\n"
                f"👱‍♂️ Масть: {suit}\n"
                f"👑 Авторитет: {authority} из 5\n"
                f"🚬 Сигареты: {format_number(cigarettes)}\n"
                f"💲 Баксы: {format_number(dollars)}\n"
                f"📦 Пожертвовано: {format_number(total_donations)}"
            )
            await call.message.answer(profile_text, keyboard=get_main_keyboard())
            await call.answer()
    
    elif command == "malyava":
        if can_do_action(user_id, "malyava", 1):
            malyava = random.randint(50, 75)
            add_cigarettes(user_id, malyava)
            update_last_malyava(user_id)
            update_daily_progress(user_id, "daily_malyava", 5)
            
            await call.message.answer(
                f"📨 Вы раскидали маляву по камерам и получили {format_number(malyava)} сигарет!\n"
                f"Следующая малява будет доступна через 1 час.",
                keyboard=get_back_keyboard("profile")
            )
            await call.answer()
        else:
            cooldown = get_cooldown_time(user_id, "malyava", 1)
            await call.answer(f"⏳ Малява ещё не доступна! Подождите {cooldown}", show_alert=True)
    
    elif command == "bonus":
        if can_do_action(user_id, "bonus", 12):
            bonus = random.randint(50, 100)
            add_cigarettes(user_id, bonus)
            update_last_bonus(user_id)
            update_daily_progress(user_id, "daily_bonus", 1)
            
            await call.message.answer(
                f"🎁 Вы получили бонус: {format_number(bonus)} сигарет!\n"
                f"Следующий бонус будет доступен через 12 часов.",
                keyboard=get_back_keyboard("profile")
            )
            await call.answer()
        else:
            cooldown = get_cooldown_time(user_id, "bonus", 12)
            await call.answer(f"⏳ Бонус ещё не доступен! Подождите {cooldown}", show_alert=True)
    
    elif command == "tasks":
        tasks_text = get_tasks_text(user_id)
        reset_time = get_next_reset_time()
        
        tasks_text += f"\n\n⏳ Сброс заданий через: {reset_time}"
        
        await call.message.answer(tasks_text, keyboard=get_back_keyboard("profile"))
        await call.answer()
    
    elif command == "chifir":
        if can_do_action(user_id, "chifir", 1):
            update_last_chifir(user_id)
            update_daily_progress(user_id, "daily_chifir", 5)
            add_authority(user_id, 1)
            
            await call.message.answer(
                "☕ Вы успешно чифирнули с блатными.\n"
                "👑 Ваш авторитет повышен на 1",
                keyboard=get_back_keyboard("profile")
            )
            await call.answer()
        else:
            cooldown = get_cooldown_time(user_id, "chifir", 1)
            await call.answer(f"⏳ Чифирнуть ещё нельзя! Подождите {cooldown}", show_alert=True)
    
    elif command == "read":
        cigarettes = get_cigarettes(user_id)
        
        if cigarettes < 1:
            await call.answer("❌ У вас нет сигареты, чтобы почитать газету!", show_alert=True)
            return
        
        if can_do_action(user_id, "read", 0):
            remove_cigarettes(user_id, 1)
            update_last_read(user_id)
            update_daily_progress(user_id, "daily_read", 1)
            
            await call.message.answer(
                "📰 Вы спокойно прочли свежие новости покуривая сигарету.",
                keyboard=get_back_keyboard("profile")
            )
            await call.answer()
    
    elif command == "help":
        help_text = (
            "📌 Список доступных команд:\n\n"
            "🎓 ОСНОВНЫЕ\n"
            "📒 Помощь - показать это сообщение\n"
            "📒 Профиль - информация о заключенном\n"
            "📒 Задания - ежедневные задания\n"
            "📒 Имя - установить имя для профиля\n"
            "📒 Фамилия - установить фамилию для профиля\n\n"
            "💰 ЭКОНОМИКА\n"
            "📒 Продать - продать сигареты\n"
            "📒 Пожертвовать - пожертвовать сигареты в общак\n"
            "📒 Общак - показать баланс общака\n"
            "📒 Перевести - перевести баксы другому игроку\n\n"
            "☕ РУТИНА\n"
            "📒 Бонус - получить бонус\n"
            "📒 Малява - раскидать маляву\n"
            "📒 Чифирнуть - повысить авторитет\n"
            "📒 Почитать - прочесть новости"
        )
        await call.message.answer(help_text, keyboard=get_main_keyboard())
        await call.answer()
    
    elif command == "back_to_main":
        await call.message.answer("Главное меню:", keyboard=get_main_keyboard())
        await call.answer()

# Обработчик сообщений для зарегистрированных пользователей
@bot.on.message()
async def handle_registered_message(message: Message):
    user_id = message.from_id
    
    # Проверяем, зарегистрирован ли пользователь
    if not start.is_user_registered(user_id):
        return  # Пропускаем, обработчик из start.py перехватит
    
    # Проверяем и сбрасываем ежедневные задания
    check_and_reset_daily(user_id)
    
    text = message.text.lower()
    
    # Команда помощи
    if text == "помощь":
        help_text = (
            "📌 Список доступных команд:\n\n"
            "🎓 ОСНОВНЫЕ\n"
            "📒 Помощь - показать это сообщение\n"
            "📒 Профиль - информация о заключенном\n"
            "📒 Задания - ежедневные задания\n"
            "📒 Имя - установить имя для профиля\n"
            "📒 Фамилия - установить фамилию для профиля\n\n"
            "💰 ЭКОНОМИКА\n"
            "📒 Продать - продать сигареты\n"
            "📒 Пожертвовать - пожертвовать сигареты в общак\n"
            "📒 Общак - показать баланс общака\n"
            "📒 Перевести - перевести баксы другому игроку\n\n"
            "☕ РУТИНА\n"
            "📒 Бонус - получить бонус\n"
            "📒 Малява - раскидать маляву\n"
            "📒 Чифирнуть - повысить авторитет\n"
            "📒 Почитать - прочесть новости"
        )
        await message.answer(help_text, keyboard=get_main_keyboard())
    
    # Команда общак
    elif text == "общак":
        obshak_balance = get_obshak_balance()
        await message.answer(
            f"🏘 Общак камеры\n"
            f"Всего собрано: {format_number(obshak_balance)} 🚬",
            keyboard=get_main_keyboard()
        )
    
    # Команда задания
    elif text == "задания":
        tasks_text = get_tasks_text(user_id)
        reset_time = get_next_reset_time()
        
        tasks_text += f"\n\n⏳ Сброс заданий через: {reset_time}"
        
        await message.answer(tasks_text, keyboard=get_back_keyboard("profile"))
    
    # Команда чифирнуть
    elif text == "чифирнуть":
        if can_do_action(user_id, "chifir", 1):
            update_last_chifir(user_id)
            update_daily_progress(user_id, "daily_chifir", 5)
            add_authority(user_id, 1)
            
            await message.answer(
                "☕ Вы успешно чифирнули с блатными.\n"
                "👑 Ваш авторитет повышен на 1",
                keyboard=get_back_keyboard("profile")
            )
        else:
            cooldown = get_cooldown_time(user_id, "chifir", 1)
            await message.answer(f"⏳ Чифирнуть ещё нельзя! Подождите {cooldown}", keyboard=get_main_keyboard())
    
    # Команда почитать
    elif text == "почитать":
        cigarettes = get_cigarettes(user_id)
        
        if cigarettes < 1:
            await message.answer(
                "❌ У вас нет сигареты, чтобы почитать газету!",
                keyboard=get_main_keyboard()
            )
            return
        
        if can_do_action(user_id, "read", 0):
            remove_cigarettes(user_id, 1)
            update_last_read(user_id)
            update_daily_progress(user_id, "daily_read", 1)
            
            await message.answer(
                "📰 Вы спокойно прочли свежие новости покуривая сигарету.",
                keyboard=get_back_keyboard("profile")
            )
    
    # Команда пожертвовать
    elif text.startswith("пожертвовать "):
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await message.answer("❌ Используйте: Пожертвовать [количество]\nНапример: Пожертвовать 1к", keyboard=get_main_keyboard())
            return
        
        amount_str = parts[1].strip()
        amount, success = parse_amount_with_suffix(amount_str, allow_float=False)
        
        if not success:
            await message.answer("❌ Укажите корректное число! Можно использовать: 100, 1к, 2.5кк", keyboard=get_main_keyboard())
            return
        
        cigarettes = get_cigarettes(user_id)
        
        if cigarettes < amount:
            await message.answer(f"❌ У вас недостаточно сигарет! Есть: {format_number(cigarettes)}", keyboard=get_main_keyboard())
            return
        
        remove_cigarettes(user_id, amount)
        add_to_obshak(amount)
        add_donation_record(user_id, amount)
        
        # Обновляем прогресс пожертвований
        increments = min(amount, 150)
        for _ in range(increments):
            update_daily_progress(user_id, "daily_donations", 150)
        
        await message.answer(
            f"✅ Пожертвование успешно!\n"
            f"Пожертвовано: {format_number(amount)} 🚬 в общак\n\n"
            f"Блатные запомнят ваш поступок 🤝",
            keyboard=get_back_keyboard("profile")
        )
    
    elif text == "пожертвовать":
        await message.answer("📝 Используйте: Пожертвовать [количество]\nНапример: Пожертвовать 1к", keyboard=get_main_keyboard())
    
    # Команда продать
    elif text.startswith("продать "):
        parts = message.text.split(maxsplit=1)
        if len(parts) != 2:
            await message.answer("❌ Используйте: Продать [количество]\nНапример: Продать 1к", keyboard=get_main_keyboard())
            return
        
        amount_str = parts[1].strip()
        amount, success = parse_amount_with_suffix(amount_str, allow_float=False)
        
        if not success:
            await message.answer("❌ Укажите корректное число! Можно использовать: 100, 1к, 2.5кк", keyboard=get_main_keyboard())
            return
        
        cigarettes = get_cigarettes(user_id)
        
        if cigarettes < amount:
            await message.answer(f"❌ У вас недостаточно сигарет! Есть: {format_number(cigarettes)}", keyboard=get_main_keyboard())
            return
        
        dollars_earned = amount * 0.1
        remove_cigarettes(user_id, amount)
        add_dollars(user_id, dollars_earned)
        
        await message.answer(
            f"✅ Продажа успешна!\n"
            f"Продано: {format_number(amount)} 🚬\n"
            f"Получено: {format_number(dollars_earned)} 💲",
            keyboard=get_back_keyboard("profile")
        )
    
    elif text == "продать":
        await message.answer("📝 Используйте: Продать [количество]\nНапример: Продать 1к", keyboard=get_main_keyboard())
    
    # Команда перевести
    elif text.startswith("перевести "):
        target_id = await get_target_user(message)
        
        if not target_id:
            await message.answer(
                "❌ Укажите получателя через ответ на сообщение или упоминание\n"
                "Пример: Перевести 1к [id123|Имя]",
                keyboard=get_main_keyboard()
            )
            return
        
        if target_id == user_id:
            await message.answer("❌ Нельзя перевести баксы самому себе!", keyboard=get_main_keyboard())
            return
        
        if not start.is_user_registered(target_id):
            await message.answer("❌ Получатель не зарегистрирован в боте!", keyboard=get_main_keyboard())
            return
        
        parts = message.text.split(maxsplit=2)
        if len(parts) < 2:
            await message.answer("❌ Используйте: Перевести [сумма] [получатель]", keyboard=get_main_keyboard())
            return
        
        amount_str = parts[1].strip()
        amount, success = parse_amount_with_suffix(amount_str, allow_float=True)
        
        if not success or amount <= 0:
            await message.answer("❌ Укажите корректную сумму! Можно использовать: 100, 1к, 2.5кк", keyboard=get_main_keyboard())
            return
        
        dollars = get_dollars(user_id)
        
        if dollars < amount:
            await message.answer(f"❌ У вас недостаточно баксов! Есть: {format_number(dollars)} 💲", keyboard=get_main_keyboard())
            return
        
        remove_dollars(user_id, amount)
        add_dollars(target_id, amount)
        
        target_name = get_user_display_name(target_id)
        new_balance = get_dollars(user_id)
        
        await message.answer(
            f"✅ Перевод успешно выполнен!\n"
            f"Переведено: {format_number(amount)} 💲\n"
            f"Получатель: {target_name}\n\n"
            f"💰 Ваш баланс: {format_number(new_balance)} 💲",
            keyboard=get_main_keyboard()
        )
    
    elif text == "перевести":
        await message.answer(
            "📝 Используйте: Перевести [сумма] [получатель]\n"
            "Получателя можно указать через ответ на сообщение или упоминание\n"
            "Например: Перевести 1к [id123|Имя]",
            keyboard=get_main_keyboard()
        )
    
    # Команда имя
    elif text.startswith("имя "):
        new_name = message.text[4:].strip()
        
        if not new_name:
            await message.answer("❌ Укажите имя после команды. Например: Имя Александр")
            return
        
        if not is_valid_name(new_name):
            await message.answer("❌ Имя может содержать только русские и английские буквы, пробел и дефис.")
            return
        
        update_first_name(user_id, new_name)
        await message.answer(f"✅ Имя успешно изменено на: {new_name}", keyboard=get_back_keyboard("profile"))
    
    elif text == "имя":
        user_data = get_user_data(user_id)
        if user_data:
            current_name = user_data[2] if user_data[2] else user_data[0]
            await message.answer(f"📝 Ваше текущее имя: {current_name}\n\nЧтобы изменить имя, напишите: Имя [новое имя]")
    
    # Команда фамилия
    elif text.startswith("фамилия "):
        new_name = message.text[8:].strip()
        
        if not new_name:
            await message.answer("❌ Укажите фамилию после команды. Например: Фамилия Иванов")
            return
        
        if not is_valid_name(new_name):
            await message.answer("❌ Фамилия может содержать только русские и английские буквы, пробел и дефис.")
            return
        
        update_last_name(user_id, new_name)
        await message.answer(f"✅ Фамилия успешно изменена на: {new_name}", keyboard=get_back_keyboard("profile"))
    
    elif text == "фамилия":
        user_data = get_user_data(user_id)
        if user_data:
            current_last_name = user_data[3] if user_data[3] else user_data[1]
            await message.answer(f"📝 Ваша текущая фамилия: {current_last_name}\n\nЧтобы изменить фамилию, напишите: Фамилия [новая фамилия]")
    
    # Команда бонус
    elif text == "бонус":
        if can_do_action(user_id, "bonus", 12):
            bonus = random.randint(50, 100)
            add_cigarettes(user_id, bonus)
            update_last_bonus(user_id)
            update_daily_progress(user_id, "daily_bonus", 1)
            
            await message.answer(
                f"🎁 Вы получили бонус: {format_number(bonus)} сигарет!\n"
                f"Следующий бонус будет доступен через 12 часов.",
                keyboard=get_back_keyboard("profile")
            )
        else:
            cooldown = get_cooldown_time(user_id, "bonus", 12)
            await message.answer(f"⏳ Бонус ещё не доступен! Подождите {cooldown}", keyboard=get_main_keyboard())
    
    # Команда малява
    elif text == "малява":
        if can_do_action(user_id, "malyava", 1):
            malyava = random.randint(50, 75)
            add_cigarettes(user_id, malyava)
            update_last_malyava(user_id)
            update_daily_progress(user_id, "daily_malyava", 5)
            
            await message.answer(
                f"📨 Вы раскидали маляву по камерам и получили {format_number(malyava)} сигарет!\n"
                f"Следующая малява будет доступна через 1 час.",
                keyboard=get_back_keyboard("profile")
            )
        else:
            cooldown = get_cooldown_time(user_id, "malyava", 1)
            await message.answer(f"⏳ Малява ещё не доступна! Подождите {cooldown}", keyboard=get_main_keyboard())
    
    # Команда профиль
    elif text == "профиль":
        user_data = get_user_data(user_id)
        if user_data:
            current_first_name = user_data[2] if user_data[2] else user_data[0]
            current_last_name = user_data[3] if user_data[3] else user_data[1]
            article = user_data[4]
            prison_id = user_data[5]
            cigarettes = user_data[6]
            dollars = user_data[7]
            suit = user_data[8]
            authority = user_data[9]
            total_donations = user_data[10]
            reg_date = datetime.fromisoformat(user_data[11].replace(' ', 'T')).strftime("%d.%m.%Y")
            
            profile_text = (
                f"📑 Личное дело заключенного #{prison_id}\n"
                f"📒 Имя: {current_first_name}\n"
                f"📒 фамилия: {current_last_name}\n"
                f"⚖ Статья: {article}\n"
                f"📒 Под стражей с: {reg_date}\n"
                f"📜 Статус: Пожизненно\n\n"
                f"👱‍♂️ Масть: {suit}\n"
                f"👑 Авторитет: {authority} из 5\n"
                f"🚬 Сигареты: {format_number(cigarettes)}\n"
                f"💲 Баксы: {format_number(dollars)}\n"
                f"📦 Пожертвовано: {format_number(total_donations)}"
            )
            await message.answer(profile_text, keyboard=get_main_keyboard())

if __name__ == "__main__":
    print("Бот 'Областное Исправительное Учреждение' запущен...")
    print("Ожидание сообщений...")
    bot.run_forever()
