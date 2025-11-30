import json
from typing import Any, Sequence, Union

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(name='safe_json')
def safe_json(value: Any) -> str:
    """
    Сериализует Python-объект в JSON и помечает его как безопасный для вставки в шаблон.
    Возвращает 'null' в случае ошибки.
    """
    try:
        dumped = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        dumped = 'null'
    return mark_safe(dumped)

@register.filter(name='map_dates')
def map_dates(
    calendar_data: Sequence[Sequence[Union[str, int]]]
) -> str:
    """
    Преобразует данные вида:
        [
            ['Дата', 'Заказы'],
            ['YYYY-MM-DD', count],
            ...
        ]
    в JavaScript-массив:
        [[new Date(Y, M-1, D), count], ...]
    """
    rows: list[str] = []
    for entry in calendar_data[1:]:
        try:
            date_str, cnt = entry
            y, m, d = (int(part) for part in date_str.split("-"))
            rows.append(f"[new Date({y}, {m-1}, {d}), {int(cnt)}]")
        except Exception:
            continue
    return mark_safe("[" + ",".join(rows) + "]")

@register.filter(name='map_timeline')
def map_timeline(
    timeline_data: Sequence[Sequence[str]]
) -> str:
    """
    Преобразует данные вида:
        [
            ['Товар', 'Начало', 'Конец'],
            ['name', 'YYYY-MM-DD', 'YYYY-MM-DD'],
            ...
        ]
    в JS-массив:
        [[ 'name', new Date(Y,M-1,D), new Date(Y2,M2-1,D2) ], ...]
    """
    rows: list[str] = []
    for entry in timeline_data[1:]:
        try:
            name, start, end = entry
            ys, ms, ds = (int(x) for x in start.split("-"))
            ye, me, de = (int(x) for x in end.split("-"))
            # Преобразуем месяцы в 0-based для JS
            ms -= 1
            me -= 1
            safe_name = name.replace("'", "\\'")
            rows.append(
                f"['{safe_name}', new Date({ys}, {ms}, {ds}), new Date({ye}, {me}, {de})]"
            )
        except Exception:
            continue
    return mark_safe("[" + ",".join(rows) + "]")
