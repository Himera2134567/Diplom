# main/templatetags/star_filters.py

from django import template

register = template.Library()

@register.filter
def stars(rating):
    """
    Возвращает HTML-код звезд для рейтинга (1-5).
    """
    full_star = '★'
    empty_star = '☆'
    # Ограничим рейтинг сверху 5, снизу 0 (на всякий случай).
    rating = max(0, min(rating, 5))
    return full_star * rating + empty_star * (5 - rating)