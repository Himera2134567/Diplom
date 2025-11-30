# main/templatetags/custom_filters.py

from django import template

register = template.Library()

@register.filter
def dict_get(dictionary, key):
    if dictionary and key:
        return dictionary.get(key, '')
    return ''

@register.filter
def percentage(value):
    """
    Форматирует число как процентное значение.
    Пример: 0.25 -> '25%'
    """
    return '{:.0%}'.format(value)

@register.filter
def multiply(value, arg):
    """
    Умножает значение на аргумент.
    """
    return value * arg

@register.filter
def subtract(value, arg):
    """
    Вычитает аргумент из значения.
    """
    return value - arg



@register.filter
def get_choice_label(choices, key):
    """
    Возвращает метку (label) из списка choices по заданному ключу.
    Если ключ не найден, возвращает пустую строку.
    """
    for k, v in choices:
        if k == key:
            return v
    return ''