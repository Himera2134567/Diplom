from django import template
import json
from datetime import datetime

register = template.Library()

@register.filter
def safe(value):
    return json.dumps(value)

@register.filter
def map_dates(value):
    # Преобразует ['YYYY-MM-DD', n] → [new Date(Y, M, D), n]
    out = []
    for row in value[1:]:
        d = datetime.strptime(row[0], '%Y-%m-%d')
        out.append([f"new Date({d.year}, {d.month-1}, {d.day})", row[1]])
    return '[' + ','.join(f"[{item[0]}, {item[1]}]" for item in out) + ']'

@register.filter
def map_timeline(value):
    # Преобразует ['name','YYYY-MM-DD','YYYY-MM-DD'] → [ 'name', new Date(...), new Date(...) ]
    out = []
    for row in value[1:]:
        s = datetime.strptime(row[1], '%Y-%m-%d')
        e = datetime.strptime(row[2], '%Y-%m-%d')
        out.append(f"['{row[0]}', new Date({s.year},{s.month-1},{s.day}), new Date({e.year},{e.month-1},{e.day})]")
    return '[' + ','.join(out) + ']'
