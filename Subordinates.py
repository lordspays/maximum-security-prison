import sqlite3
import math
from datetime import datetime, timedelta
from vkbottle import Keyboard, KeyboardButtonColor, Callback

# Константы
BASE_PRICE = 10  # Базовая цена найма
INCOME_PER_HOUR = 10  # Базовый доход в сигаретах в час
INCOME_REDUCTION = 2  # Уменьшение дохода если в подчинении

# Функции для работы с подчинёнными
def init_subordinates_table():
    """Инициализация таблицы подчинённых"""
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    # Создаем таблицу для подчинённых
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subordinates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boss_id INTEGER NOT NULL,
            slave_id INTEGER NOT NULL UNIQUE,
            price REAL NOT NULL,
            income INTEGER DEFAULT 10,
            purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (boss_id) REFERENCES users (user_id),
            FOREIGN KEY (slave_id) REFERENCES users (user_id)
        )
    ''')
    
    # Создаем таблицу для погонял
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nicknames (
            user_id INTEGER PRIMARY KEY,
            nickname TEXT UNIQUE,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Таблица подчинённых инициализирована")

def get_nickname(user_id):
    """Получение погоняла пользователя"""
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT nickname FROM nicknames WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    conn.close()
    return result[0] if result else None

def set_nickname(user_id, nickname):
    """Установка погоняла"""
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    # Проверяем уникальность
    cursor.execute("SELECT user_id FROM nicknames WHERE nickname = ?", (nickname,))
    if cursor.fetchone():
        conn.close()
        return False, "❌ Это погоняло уже занято!"
    
    cursor.execute('''
        INSERT OR REPLACE INTO nicknames (user_id, nickname) 
        VALUES (?, ?)
    ''', (user_id, nickname))
    
    conn.commit()
    conn.close()
    return True, f"✅ Погоняло успешно установлено: {nickname}"

def get_slave_info(user_id):
    """Получение информации о подчинённом"""
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT s.boss_id, s.price, s.income, u.first_name, u.last_name
        FROM subordinates s
        JOIN users u ON s.boss_id = u.user_id
        WHERE s.slave_id = ?
    ''', (user_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'boss_id': result[0],
            'price': result[1],
            'income': result[2],
            'boss_name': f"{result[3]} {result[4]}".strip()
        }
    return None

def get_boss_info(user_id):
    """Получение информации о боссе и его подчинённых"""
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    # Получаем всех подчинённых
    cursor.execute('''
        SELECT s.slave_id, s.price, s.income, u.first_name, u.last_name, n.nickname
        FROM subordinates s
        JOIN users u ON s.slave_id = u.user_id
        LEFT JOIN nicknames n ON s.slave_id = n.user_id
        WHERE s.boss_id = ?
        ORDER BY s.purchase_date DESC
    ''', (user_id,))
    
    slaves = cursor.fetchall()
    count = len(slaves)
    
    conn.close()
    
    return {
        'count': count,
        'slaves': [{
            'id': s[0],
            'price': s[1],
            'income': s[2],
            'name': f"{s[3]} {s[4]}".strip(),
            'nickname': s[5] if s[5] else f"{s[3]} {s[4]}".strip()
        } for s in slaves]
    }

def hire_slave(boss_id, slave_id):
    """Наём подчинённого"""
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    # Проверяем, не в подчинении ли уже
    cursor.execute("SELECT * FROM subordinates WHERE slave_id = ?", (slave_id,))
    if cursor.fetchone():
        conn.close()
        return False, "❌ Этот игрок уже в подчинении!"
    
    # Проверяем баланс босса
    cursor.execute("SELECT dollars FROM users WHERE user_id = ?", (boss_id,))
    boss_balance = cursor.fetchone()[0]
    
    # Проверяем, не пытается ли нанять сам себя
    if boss_id == slave_id:
        conn.close()
        return False, "❌ Нельзя нанять самого себя!"
    
    # Получаем текущую цену подчинённого
    cursor.execute("""
        SELECT price FROM subordinates WHERE slave_id = ?
    """, (slave_id,))
    existing = cursor.fetchone()
    
    if existing:
        price = existing[0]
    else:
        price = BASE_PRICE
    
    if boss_balance < price:
        conn.close()
        return False, f"❌ Нехватает баксов! Нужно: {price} 💲"
    
    # Если уже был в подчинении, обновляем запись
    if existing:
        cursor.execute("""
            UPDATE subordinates 
            SET boss_id = ?, price = ?, income = ?, purchase_date = CURRENT_TIMESTAMP
            WHERE slave_id = ?
        """, (boss_id, price, INCOME_PER_HOUR, slave_id))
    else:
        # Иначе создаём новую запись
        cursor.execute("""
            INSERT INTO subordinates (boss_id, slave_id, price, income)
            VALUES (?, ?, ?, ?)
        """, (boss_id, slave_id, price, INCOME_PER_HOUR))
    
    # Списываем деньги
    cursor.execute("UPDATE users SET dollars = dollars - ? WHERE user_id = ?", (price, boss_id))
    
    conn.commit()
    conn.close()
    
    return True, f"🌹 Вы успешно наняли нового подчинённого за {price} 💲"

def release_slave(boss_id, slave_id):
    """Освобождение подчинённого"""
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    # Проверяем, что это действительно подчинённый этого босса
    cursor.execute("""
        SELECT * FROM subordinates 
        WHERE boss_id = ? AND slave_id = ?
    """, (boss_id, slave_id))
    
    if not cursor.fetchone():
        conn.close()
        return False, "❌ Этот игрок не в вашем подчинении!"
    
    # Удаляем запись
    cursor.execute("DELETE FROM subordinates WHERE boss_id = ? AND slave_id = ?", (boss_id, slave_id))
    
    conn.commit()
    conn.close()
    
    return True, "✅ Подчинённый отпущен на свободу"

def upgrade_slave(boss_id, slave_id):
    """Повышение подчинённого"""
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    # Проверяем, что это подчинённый этого босса
    cursor.execute("""
        SELECT price, income FROM subordinates 
        WHERE boss_id = ? AND slave_id = ?
    """, (boss_id, slave_id))
    
    result = cursor.fetchone()
    if not result:
        conn.close()
        return False, "❌ Этот игрок не в вашем подчинении!"
    
    current_price = result[0]
    current_income = result[1]
    
    # Стоимость повышения = половина текущей цены
    upgrade_cost = math.ceil(current_price / 2)
    
    # Проверяем баланс босса
    cursor.execute("SELECT dollars FROM users WHERE user_id = ?", (boss_id,))
    boss_balance = cursor.fetchone()[0]
    
    if boss_balance < upgrade_cost:
        conn.close()
        return False, f"❌ Нехватает баксов для повышения! Нужно: {upgrade_cost} 💲"
    
    # Повышаем цену и доход
    new_price = current_price * 1.1
    new_income = current_income + 1
    
    cursor.execute("""
        UPDATE subordinates 
        SET price = ?, income = ?
        WHERE boss_id = ? AND slave_id = ?
    """, (new_price, new_income, boss_id, slave_id))
    
    # Списываем деньги
    cursor.execute("UPDATE users SET dollars = dollars - ? WHERE user_id = ?", (upgrade_cost, boss_id))
    
    conn.commit()
    conn.close()
    
    return True, f"✅ Подчинённый повышен!\nНовая цена: {math.ceil(new_price)} 💲\nНовый доход: {new_income} 🚬/час"

def buyout_slave(slave_id):
    """Выкуп из подчинения"""
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    # Получаем информацию о подчинённом
    cursor.execute("""
        SELECT boss_id, price FROM subordinates 
        WHERE slave_id = ?
    """, (slave_id,))
    
    result = cursor.fetchone()
    if not result:
        conn.close()
        return False, "❌ Вы не в подчинении!"
    
    boss_id = result[0]
    current_price = result[1]
    
    # Цена выкупа = текущая цена * 1.25
    buyout_price = math.ceil(current_price * 1.25)
    
    # Проверяем баланс
    cursor.execute("SELECT dollars FROM users WHERE user_id = ?", (slave_id,))
    slave_balance = cursor.fetchone()[0]
    
    if slave_balance < buyout_price:
        conn.close()
        return False, f"❌ Нехватает баксов для выкупа! Нужно: {buyout_price} 💲"
    
    # Списываем деньги
    cursor.execute("UPDATE users SET dollars = dollars - ? WHERE user_id = ?", (buyout_price, slave_id))
    
    # Переводим деньги боссу
    cursor.execute("UPDATE users SET dollars = dollars + ? WHERE user_id = ?", (buyout_price, boss_id))
    
    # Удаляем из подчинения
    cursor.execute("DELETE FROM subordinates WHERE slave_id = ?", (slave_id,))
    
    conn.commit()
    conn.close()
    
    return True, f"✅ Вы успешно выкупились за {buyout_price} 💲"

def get_income_reduction(user_id):
    """Проверка, уменьшен ли доход (в подчинении)"""
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM subordinates WHERE slave_id = ?", (user_id,))
    result = cursor.fetchone()
    
    conn.close()
    return result is not None

def calculate_hourly_income(user_id):
    """Расчёт почасового дохода"""
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    # Доход от подчинённых
    cursor.execute("SELECT SUM(income) FROM subordinates WHERE boss_id = ?", (user_id,))
    result = cursor.fetchone()
    income_from_slaves = result[0] if result[0] else 0
    
    total_income = income_from_slaves
    
    # Проверяем, не в подчинении ли сам
    if get_income_reduction(user_id):
        total_income = total_income // INCOME_REDUCTION
    
    conn.close()
    return total_income

def get_slaves_page(boss_id, page=1, per_page=10):
    """Получение страницы со списком подчинённых"""
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    offset = (page - 1) * per_page
    
    cursor.execute("""
        SELECT s.slave_id, s.price, s.income, u.first_name, u.last_name, n.nickname
        FROM subordinates s
        JOIN users u ON s.slave_id = u.user_id
        LEFT JOIN nicknames n ON s.slave_id = n.user_id
        WHERE s.boss_id = ?
        ORDER BY s.purchase_date DESC
        LIMIT ? OFFSET ?
    """, (boss_id, per_page, offset))
    
    slaves = cursor.fetchall()
    
    # Получаем общее количество
    cursor.execute("SELECT COUNT(*) FROM subordinates WHERE boss_id = ?", (boss_id,))
    total = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'slaves': [{
            'id': s[0],
            'price': math.ceil(s[1]),
            'income': s[2],
            'name': f"{s[3]} {s[4]}".strip(),
            'nickname': s[5] if s[5] else f"{s[3]} {s[4]}".strip()
        } for s in slaves],
        'total': total,
        'page': page,
        'pages': (total + per_page - 1) // per_page
    }

def create_slaves_keyboard(boss_id, page=1):
    """Создание клавиатуры для списка подчинённых"""
    data = get_slaves_page(boss_id, page)
    
    if data['total'] == 0:
        return None
    
    keyboard = Keyboard(inline=True)
    
    # Добавляем кнопки с подчинёнными
    for slave in data['slaves']:
        keyboard.add(
            Callback(f"{slave['nickname']} | {slave['price']}💲 | {slave['income']}🚬", 
                    payload={"command": "slave_info", "id": slave['id']}),
            color=KeyboardButtonColor.SECONDARY
        )
        keyboard.row()
    
    # Добавляем навигацию
    nav_row = []
    if page > 1:
        nav_row.append(Callback("⬅️", payload={"command": "slaves_page", "page": page-1}))
    
    nav_row.append(Callback(f"📄 {page}/{data['pages']}", payload={"command": "slaves_current"}))
    
    if page < data['pages']:
        nav_row.append(Callback("➡️", payload={"command": "slaves_page", "page": page+1}))
    
    for btn in nav_row:
        keyboard.add(btn, color=KeyboardButtonColor.PRIMARY)
    
    return keyboard

# Инициализация таблицы при импорте
init_subordinates_table()
