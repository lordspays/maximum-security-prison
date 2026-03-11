import re

def format_number(number):
    """
    Форматирует число с разделением тысяч точкой
    Пример: 1000 -> 1.000, 1000000 -> 1.000.000
    """
    if number is None:
        return "0"
    
    # Преобразуем в целое число если это возможно
    if isinstance(number, float) and number.is_integer():
        number = int(number)
    
    # Для чисел с плавающей точкой (баксы)
    if isinstance(number, float):
        # Отделяем целую и дробную часть
        integer_part = int(number)
        fractional_part = round(number - integer_part, 1)
        
        # Форматируем целую часть с разделителями
        formatted_integer = f"{integer_part:,}".replace(",", ".")
        
        # Если дробная часть не нулевая, добавляем её
        if fractional_part > 0:
            # Берём только первый знак после запятой
            fractional_str = str(fractional_part).split('.')[1][0]
            return f"{formatted_integer}.{fractional_str}"
        else:
            return formatted_integer
    else:
        # Для целых чисел
        return f"{number:,}".replace(",", ".")

def parse_number_with_suffix(text):
    """
    Парсит число с суффиксами к, кк, ккк
    Примеры: 1к -> 1000, 2.5кк -> 2_500_000, 3ккк -> 3_000_000_000
    
    Возвращает кортеж (число, успех)
    """
    if not text:
        return None, False
    
    # Убираем пробелы и приводим к нижнему регистру
    text = text.lower().replace(' ', '')
    
    # Паттерн для поиска числа с суффиксом
    pattern = r'^(\d+(?:[.,]\d+)?)(ккк|кк|к)?$'
    match = re.match(pattern, text)
    
    if not match:
        # Пробуем просто число
        try:
            if '.' in text or ',' in text:
                # Заменяем запятую на точку для парсинга
                num = float(text.replace(',', '.'))
                return num, True
            else:
                num = int(text)
                return num, True
        except ValueError:
            return None, False
    
    number_part, suffix = match.groups()
    
    # Заменяем запятую на точку для парсинга
    number_part = number_part.replace(',', '.')
    
    try:
        if '.' in number_part:
            value = float(number_part)
        else:
            value = int(number_part)
    except ValueError:
        return None, False
    
    # Применяем суффикс
    if suffix == 'к':
        result = value * 1000
    elif suffix == 'кк':
        result = value * 1_000_000
    elif suffix == 'ккк':
        result = value * 1_000_000_000
    else:
        result = value
    
    # Для целых чисел возвращаем int, для дробных - float
    if isinstance(result, float) and result.is_integer():
        return int(result), True
    return result, True

def parse_amount_with_suffix(text, allow_float=False):
    """
    Парсит количество с суффиксом для использования в командах
    Возвращает кортеж (количество, успех)
    """
    value, success = parse_number_with_suffix(text)
    
    if not success:
        return None, False
    
    # Проверяем, что число положительное
    if value <= 0:
        return None, False
    
    # Для целочисленных операций (сигареты) проверяем, что число целое
    if not allow_float and isinstance(value, float):
        # Если это число с плавающей точкой, но оно целое (1.0)
        if value.is_integer():
            return int(value), True
        return None, False
    
    if allow_float:
        return float(value), True
    else:
        return int(value), True

def format_transaction_message(transaction_type, amount, currency, recipient=None, balance=None):
    """
    Форматирует сообщение о транзакции
    """
    formatted_amount = format_number(amount)
    
    if transaction_type == "donation":
        return (
            f"✅ Пожертвование успешно!\n"
            f"Пожертвовано: {formatted_amount} 🚬 в общак\n\n"
            f"Блатные запомнят ваш поступок 🤝"
        )
    elif transaction_type == "sell":
        return (
            f"✅ Продажа успешна!\n"
            f"Продано: {formatted_amount} 🚬\n"
            f"Получено: {format_number(amount * 0.1)} 💲"
        )
    elif transaction_type == "transfer":
        return (
            f"✅ Перевод успешно выполнен!\n"
            f"Переведено: {formatted_amount} 💲\n"
            f"Получатель: {recipient}\n\n"
            f"💰 Ваш баланс: {format_number(balance)} 💲"
        )
    elif transaction_type == "balance":
        return f"🚬 Сигареты: {formatted_amount}"
    elif transaction_type == "dollars":
        return f"💲 Баксы: {formatted_amount}"
    elif transaction_type == "obshak":
        return f"🏘 Общак камеры\nВсего собрано: {formatted_amount} 🚬"
    
    return str(formatted_amount)

def format_profile_number(number):
    """
    Форматирует число для профиля (всегда с разделителями)
    """
    return format_number(number)

# Примеры использования:
if __name__ == "__main__":
    # Тестирование форматирования
    print(format_number(1000))           # 1.000
    print(format_number(1500000))        # 1.500.000
    print(format_number(1234567))        # 1.234.567
    print(format_number(10.5))            # 10.5
    print(format_number(1000.0))          # 1.000
    
    # Тестирование парсинга с суффиксами
    print(parse_number_with_suffix("1к"))     # (1000, True)
    print(parse_number_with_suffix("2.5кк"))  # (2500000.0, True)
    print(parse_number_with_suffix("3ккк"))   # (3000000000, True)
    print(parse_number_with_suffix("100"))    # (100, True)
    print(parse_number_with_suffix("1.5"))    # (1.5, True)
    
    # Тестирование парсинга количества
    print(parse_amount_with_suffix("5к"))      # (5000, True)
    print(parse_amount_with_suffix("1.5к", True))  # (1500.0, True)
    print(parse_amount_with_suffix("2.5", False))  # (None, False) - нельзя дробное для целых
