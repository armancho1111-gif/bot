from aiogram.types import LabeledPrice
from config import PAID_PRICE

def get_payment(invoice_title="Доступ к боту", invoice_description="Безлимитный доступ"):
    prices = [LabeledPrice(label=invoice_title, amount=int(PAID_PRICE*100))]  # в центах
    return prices, invoice_description