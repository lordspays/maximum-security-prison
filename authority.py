import sqlite3
from datetime import datetime, timedelta

# Список мастей (только текст, без эмодзи)
SUITS = ["Вор в законе", "Блатной", "Мужик", "Козел", "Петух"]

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
