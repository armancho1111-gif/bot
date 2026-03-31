from aiogram.types import LabeledPrice
from config import PAID_PRICE, CURRENCY

def get_payment(invoice_title="Доступ к боту", invoice_description="Безлимитный доступ к решению задач"):
    """
    Создает платеж для оплаты доступа
    
    Returns:
        tuple: (prices, description)
    """
    # Цена в копейках/центах
    amount = int(PAID_PRICE * 100)
    
    prices = [
        LabeledPrice(
            label=invoice_title,
            amount=amount
        )
    ]
    
    description = (
        f"{invoice_description}\n\n"
        f"✅ Безлимитное количество задач\n"
        f"✅ Доступ ко всем режимам решения\n"
        f"✅ Сохранение истории\n"
        f"✅ Приоритетная поддержка\n\n"
        f"Стоимость: {PAID_PRICE} {CURRENCY}"
    )
    
    return prices, description

def get_subscription_payment():
    """
    Создает платеж для подписки (если нужно)
    """
    prices = [
        LabeledPrice(label="Месячная подписка", amount=199),  # 1.99 USD
        LabeledPrice(label="Годовая подписка", amount=1999),  # 19.99 USD
    ]
    
    description = "Выберите период подписки для безлимитного доступа"
    
    return prices, description