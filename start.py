import random
import sqlite3
from datetime import datetime
from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text, Callback

# Импортируем утилиты
from utils import format_number

# Конфигурация бота (токен будет передан из bot.py)
bot = None

# Список статей для приговора
ARTICLES = [
    "105 ч. 2 УК РФ — убийство с отягчающими обстоятельствами",
    "205 ч. 3 УК РФ — террористический акт",
    "206 ч. 4 УК РФ — захват заложника",
    "210 ч. 4 УК РФ — организация преступного сообщества (преступной организации) или участие в нём (ней)",
    "228.1 ч. 5 УК РФ — незаконный оборот наркотических средств",
    "281 ч. 3 УК РФ — диверсия",
    "357 УК РФ — геноцид"
]

# Функция для склонения имени в родительный падеж
def get_genitive_name(name):
    if name.endswith('а'):
        return name[:-1] + 'ы'
    elif name.endswith('я'):
        return name[:-1] + 'и'
    elif name.endswith('й'):
        return name[:-1] + 'я'
    elif name.endswith('ь'):
        return name[:-1] + 'я'
    elif name.endswith('о'):
        return name
    else:
        return name + 'а'

# Проверка регистрации пользователя
def is_user_registered(user_id):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    
    conn.close()
    return result is not None

# Получение следующего доступного prison_id
def get_next_prison_id():
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT MAX(prison_id) FROM users")
    max_id = cursor.fetchone()[0]
    
    conn.close()
    
    if max_id is None:
        return 1
    else:
        return max_id + 1

# Регистрация нового пользователя
def register_user(user_id, vk_first_name, vk_last_name, article, prison_id):
    conn = sqlite3.connect('prison_bot.db')
    cursor = conn.cursor()
    
    cursor.execute(
        """INSERT INTO users (
            user_id, vk_name, vk_last_name, first_name, last_name, 
            article, prison_id, cigarettes, dollars, suit, authority,
            daily_malyava, daily_donations, daily_bonus, daily_chifir, daily_read
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, vk_first_name, vk_last_name, vk_first_name, vk_last_name, 
         article, prison_id, 0, 0, 'Петух', 0, 0, 0, 0, 0, 0)
    )
    
    conn.commit()
    conn.close()

# Создание основной клавиатуры (импортируем из bot.py чтобы избежать циклического импорта)
def get_main_keyboard():
    from bot import get_main_keyboard as main_kb
    return main_kb()

# Создание клавиатуры для незарегистрированных пользователей
def get_start_keyboard():
    keyboard = Keyboard(inline=False)
    keyboard.add(Text("Начать"), color=KeyboardButtonColor.POSITIVE)
    keyboard.add(Text("Старт"), color=KeyboardButtonColor.SECONDARY)
    keyboard.row()
    keyboard.add(Text("start"), color=KeyboardButtonColor.PRIMARY)
    return keyboard

# Обработчик для незарегистрированных пользователей
async def handle_unregistered(message: Message):
    user_id = message.from_id
    
    # Получаем информацию о пользователе из VK
    users = await message.ctx_api.users.get(user_ids=[user_id])
    if users:
        vk_first_name = users[0].first_name
        vk_last_name = users[0].last_name
    else:
        vk_first_name = "Заключенный"
        vk_last_name = ""
    
    # Проверяем, является ли сообщение командой для начала
    if message.text.lower() in ["начать", "старт", "start"]:
        # Регистрируем нового пользователя
        random_article = random.choice(ARTICLES)
        prison_id = get_next_prison_id()
        register_user(user_id, vk_first_name, vk_last_name, random_article, prison_id)
        
        # Склоняем имя в родительный падеж
        genitive_name = get_genitive_name(vk_first_name)
        
        # Отправляем приветственное сообщение
        welcome_text = (f"Суд выносит приговор для {genitive_name}.\n"
                       f"Статья {random_article}.\n\n"
                       f"Приговорить {genitive_name} к пожизненному заключению под стражу "
                       f"в тюрьму строгого режима.👮‍♂️\n\n"
                       f"{vk_first_name}, с этого момента вы лишаетесь свободы до конца своих дней. 😭\n\n"
                       f"Вы можете узнать команды заключённых командой Помощь.")
        
        await message.answer(welcome_text, keyboard=get_main_keyboard())
        return True
    else:
        # Игнорируем все остальные сообщения от незарегистрированных пользователей
        return False

# Функция для инициализации обработчиков
def init_start_handlers(bot_instance):
    global bot
    bot = bot_instance
    
    @bot.on.message()
    async def start_handler(message: Message):
        user_id = message.from_id
        
        if not is_user_registered(user_id):
            await handle_unregistered(message)
