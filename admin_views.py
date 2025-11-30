import uuid
from decimal import Decimal, ROUND_HALF_UP

import math
import numpy as np

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Count, Sum, F
from django.db.models.functions import TruncMonth, TruncDate, TruncWeek

from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.utils.safestring import mark_safe
import json

from .models import (
    Profile, Event, Ticket, Merch, Partner,
    MailingTopic, MailingMessage, Subscription,
    LoyaltyProgram, OrganizerDiscount, BuyerDiscount,
)

from .forms import (
    EventForm, MerchForm, PartnerForm,
    MailingTopicForm, MailingMessageForm
)


def user_is_admin(user):
    """Проверка: пользователь — администратор (или суперпользователь)."""
    return user.is_authenticated and (
        user.is_superuser or (hasattr(user, 'profile') and user.profile.user_type == 'admin')
    )


@user_passes_test(user_is_admin)
def admin_home(request):
    """Главная страница кастомной админ-панели."""
    users = User.objects.all()
    return render(request, 'admin_custom/admin_home.html', {'users': users})


@login_required
def user_list(request):
    """Список пользователей."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    users = User.objects.select_related('profile').order_by('username')
    return render(request, 'admin_custom/user_list.html', {'users': users})


@user_passes_test(user_is_admin)
@transaction.atomic
def user_edit(request, pk):
    """Редактирование пользователя."""
    user_obj = get_object_or_404(User, pk=pk)
    profile = user_obj.profile

    if request.method == 'POST':
        # Основные поля юзера
        user_obj.username = request.POST.get('username', user_obj.username)
        user_obj.email = request.POST.get('email', user_obj.email)
        new_password = request.POST.get('password')
        if new_password:
            user_obj.set_password(new_password)
        user_obj.save()

        # Профиль
        profile.city = request.POST.get('city', profile.city)
        profile.address = request.POST.get('address', profile.address)
        profile.user_type = request.POST.get('user_type', profile.user_type)
        if profile.user_type == 'organizer':
            profile.event_type = request.POST.get('event_type', profile.event_type)
        else:
            profile.event_type = None
        profile.save()

        messages.success(request, f"Пользователь {user_obj.username} обновлён!")
        return redirect('custom_admin_user_list')

    return render(request, 'admin_custom/user_edit.html', {
        'user_obj': user_obj,
        'profile': profile,
    })


@login_required
def user_delete(request, pk):
    """Удаление пользователя."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    user_obj = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        user_obj.delete()
        messages.success(request, "Пользователь удалён.")
        return redirect('custom_admin_user_list')
    return render(request, 'admin_custom/user_confirm_delete.html', {'user_obj': user_obj})


@login_required
def event_list(request):
    """Список мероприятий."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    events = Event.objects.order_by('-date')
    return render(request, 'admin_custom/event_list.html', {'events': events})


@login_required
def event_create(request):
    """Создать мероприятие."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Событие создано!")
            return redirect('custom_admin_event_list')
    else:
        form = EventForm()
    return render(request, 'admin_custom/event_form.html', {
        'title': "Создать мероприятие",
        'form': form
    })


@login_required
def event_edit(request, pk):
    """Редактировать мероприятие."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    event_obj = get_object_or_404(Event, pk=pk)
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Событие обновлено!")
            return redirect('custom_admin_event_list')
    else:
        form = EventForm(instance=event_obj)
    return render(request, 'admin_custom/event_form.html', {
        'title': "Редактировать мероприятие",
        'form': form
    })


@login_required
def event_delete(request, pk):
    """Удалить мероприятие."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    event_obj = get_object_or_404(Event, pk=pk)
    if request.method == 'POST':
        event_obj.delete()
        messages.success(request, "Событие удалено.")
        return redirect('custom_admin_event_list')
    return render(request, 'admin_custom/event_confirm_delete.html', {'event': event_obj})


@login_required
def merch_list(request):
    """Список товаров."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    merch_list = Merch.objects.all().order_by('name')
    return render(request, 'admin_custom/merch_list.html', {'merch_list': merch_list})


@login_required
def merch_create(request):
    """Создать товар."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    if request.method == 'POST':
        form = MerchForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Товар создан!")
            return redirect('custom_admin_merch_list')
    else:
        form = MerchForm()
    return render(request, 'admin_custom/merch_form.html', {
        'title': "Создать товар",
        'form': form
    })


@login_required
def merch_detail(request, pk):
    """Детали товара."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    merch = get_object_or_404(Merch, pk=pk)
    return render(request, 'admin_custom/merch_detail.html', {'merch': merch})


@login_required
def merch_edit(request, pk):
    """Редактировать товар."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    merch_obj = get_object_or_404(Merch, pk=pk)
    if request.method == 'POST':
        form = MerchForm(request.POST, request.FILES, instance=merch_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Товар обновлён.")
            return redirect('custom_admin_merch_list')
    else:
        form = MerchForm(instance=merch_obj)
    return render(request, 'admin_custom/merch_form.html', {
        'title': "Редактировать товар",
        'form': form
    })


@login_required
def merch_delete(request, pk):
    """Удалить товар."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    merch_obj = get_object_or_404(Merch, pk=pk)
    if request.method == 'POST':
        merch_obj.delete()
        messages.success(request, "Товар удалён.")
        return redirect('custom_admin_merch_list')
    return render(request, 'admin_custom/merch_confirm_delete.html', {'merch': merch_obj})


@login_required
def ticket_list(request):
    """Список билетов."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    tickets = Ticket.objects.select_related('event', 'user').order_by('-purchase_date')
    return render(request, 'admin_custom/ticket_list.html', {'tickets': tickets})
def _admin_award_loyalty_and_discounts(ticket: Ticket):
    """
    Вспомогательная функция для админ-подтверждения билета:
    - начисляет баллы по активной программе лояльности;
    - выдаёт/обновляет персональные скидки (BuyerDiscount) по OrganizerDiscount.
    Возвращает (added_points, created_discounts).
    """
    program = LoyaltyProgram.get_active()
    added_points = 0

    if program:
        effective_price = ticket.get_effective_price()
        if effective_price and effective_price > Decimal('0.00'):
            raw_points = effective_price * program.points_per_ruble
            added_points = int(raw_points.quantize(Decimal('1.'), rounding=ROUND_HALF_UP))
            profile = ticket.user.profile
            profile.points = F('points') + added_points
            profile.save(update_fields=['points'])
            profile.refresh_from_db(fields=['points'])

    organizer = ticket.event.organizer
    buyer_profile = ticket.user.profile
    organizer_discounts = OrganizerDiscount.objects.filter(from_organizer=organizer)
    created_or_updated = 0

    for od in organizer_discounts:
        bd, created = BuyerDiscount.objects.get_or_create(
            buyer=buyer_profile,
            from_organizer=organizer,
            defaults={'discount_rate': od.discount_rate}
        )
        if created:
            created_or_updated += 1
        else:
            if bd.discount_rate < od.discount_rate:
                bd.discount_rate = od.discount_rate
                bd.save(update_fields=['discount_rate'])
                created_or_updated += 1

    return added_points, created_or_updated

@login_required
def ticket_confirm(request, pk):
    """
    Подтверждение билета через кастомную админ-панель:
    - помечаем билет оплаченным;
    - начисляем баллы по программе лояльности;
    - выдаём/обновляем персональные скидки.
    """
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')

    ticket = get_object_or_404(Ticket, pk=pk)
    if not ticket.is_confirmed:
        ticket.is_confirmed = True
        ticket.save()

        added_points, created_discounts = _admin_award_loyalty_and_discounts(ticket)

        msg_parts = [f"Билет {ticket.id} подтверждён."]
        if added_points > 0:
            msg_parts.append(f"Начислено {added_points} баллов.")
        if created_discounts > 0:
            msg_parts.append(f"Выдано/обновлено скидок: {created_discounts}.")
        messages.success(request, " ".join(msg_parts))
    else:
        messages.info(request, "Билет уже подтверждён.")
    return redirect('custom_admin_ticket_list')



@login_required
def partner_list(request):
    """Список партнёров."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    partners = Partner.objects.all().order_by('id')
    return render(request, 'admin_custom/partner_list.html', {'partners': partners})


@login_required
def partner_create(request):
    """Создать партнёра."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    if request.method == 'POST':
        form = PartnerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Партнёр создан!")
            return redirect('custom_admin_partner_list')
    else:
        form = PartnerForm()
    return render(request, 'admin_custom/partner_form.html', {
        'title': "Создать партнёра",
        'form': form
    })


@login_required
def partner_detail(request, pk):
    """Детали партнёра."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    partner = get_object_or_404(Partner, pk=pk)
    return render(request, 'admin_custom/partner_detail.html', {'partner': partner})


@login_required
def partner_edit(request, pk):
    """Редактировать партнёра."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    partner = get_object_or_404(Partner, pk=pk)
    if request.method == 'POST':
        form = PartnerForm(request.POST, instance=partner)
        if form.is_valid():
            form.save()
            messages.success(request, "Партнёр обновлён.")
            return redirect('custom_admin_partner_list')
    else:
        form = PartnerForm(instance=partner)
    return render(request, 'admin_custom/partner_form.html', {
        'title': "Редактировать партнёра",
        'form': form
    })


@login_required
def partner_delete(request, pk):
    """Удалить партнёра."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    partner = get_object_or_404(Partner, pk=pk)
    if request.method == 'POST':
        partner.delete()
        messages.success(request, "Партнёр удалён.")
        return redirect('custom_admin_partner_list')
    return render(request, 'admin_custom/partner_confirm_delete.html', {'partner': partner})


@login_required
def admin_mailing_dashboard(request):
    """Дашборд рассылок."""
    topics = MailingTopic.objects.all()
    stats = []
    for topic in topics:
        stats.append({
            'topic': topic,
            'sent_count': topic.messages.count()
        })
    return render(request, 'admin_custom/mailing_dashboard.html', {'stats': stats})


@login_required
def admin_create_mailing_topic(request):
    """Создать тему рассылки."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    if request.method == 'POST':
        form = MailingTopicForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Тема рассылки создана!")
            return redirect('admin_mailing_stats')
    else:
        form = MailingTopicForm()
    return render(request, 'admin_custom/mailing_topic_form.html', {
        'title': 'Создать тему рассылки',
        'form': form
    })


@login_required
def admin_create_mailing_message(request):
    """Создать и отправить сообщение рассылки."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    if request.method == 'POST':
        form = MailingMessageForm(request.POST)
        if form.is_valid():
            msg = form.save()
            recipient_list = [sub.user.email for sub in msg.topic.subscriptions.all()]
            if recipient_list:
                send_mail(
                    f"Новое сообщение по теме {msg.topic.name}",
                    msg.text,
                    settings.DEFAULT_FROM_EMAIL,
                    recipient_list,
                    fail_silently=True,
                )
            messages.success(request, "Сообщение отправлено подписчикам!")
            return redirect('admin_mailing_stats')
    else:
        form = MailingMessageForm()
    return render(request, 'admin_custom/mailing_message_form.html', {
        'title': 'Создать сообщение рассылки',
        'form': form
    })


@login_required
def admin_mailing_stats(request):
    """Статистика по рассылкам."""
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    topics = MailingTopic.objects.all()
    stats = []
    for topic in topics:
        stats.append({
            'topic': topic,
            'sent_count': topic.messages.count()
        })
    return render(request, 'admin_custom/mailing_stats.html', {'stats': stats})


@login_required
def subscribe_topic(request, topic_id):
    """Подписаться на тему."""
    topic = get_object_or_404(MailingTopic, pk=topic_id)
    Subscription.objects.get_or_create(user=request.user, topic=topic)
    messages.success(request, f"Вы подписались на тему: {topic.name}")
    return redirect('profile')


@login_required
def unsubscribe_topic(request, topic_id):
    """Отписаться от темы."""
    topic = get_object_or_404(MailingTopic, pk=topic_id)
    Subscription.objects.filter(user=request.user, topic=topic).delete()
    messages.success(request, f"Вы отписались от теме: {topic.name}")
    return redirect('profile')













@login_required
@user_passes_test(user_is_admin)
def statistics(request):
    """
    Полный расчёт статистики для ЛР-6 … ЛР-10.
    Изменения:
      • Для ЛР-8 вместо одной таблицы/graf’ика формируем
        - smoothing_calc_json      (расчёт MA3, MA7, WMA5)
        - smoothing_forecast_json  (то же + прогноз на следующий месяц)
    """

    import copy                         # нужно только здесь
    period    = request.GET.get('period', 'day')
    base_date = timezone.now().replace(day=1)

    # ---------------------------------------------------- ЛР-6
    area_data = [['Месяц', 'Плановая прибыль', 'Реальная прибыль']]
    for i in range(12):
        ym   = (base_date - relativedelta(months=11-i)).strftime('%Y-%m')
        plan = 10000 + i * 1200
        fact = plan - 1000 + (i % 3) * 500
        area_data.append([ym, plan, fact])

    bubble_data = [['ID', 'Цена', 'Клиенты', 'Прибыль', 'Товар']]
    for idx, (name, price, clients) in enumerate([('Футболка', 500, 120),
                                                  ('Кепка',    1500, 80)], 1):
        bubble_data.append([idx, price, clients, price * clients, name])

    calendar_data = [['Дата', 'Заказы']]
    for i in range(30):
        d = (timezone.now() - relativedelta(days=29 - i)).date().isoformat()
        calendar_data.append([d, 2 + (i % 5)])

    org_data = [
        ['Менеджер', 'Ассортимент'],
        ['Ассортимент', 'Футболка'],
        ['Ассортимент', 'Кепка'],
    ]

    geochart_data = [['Страна', 'Клиенты'],
                     ['Russia', 20],
                     ['Kazakhstan', 10],
                     ['United States', 10]]

    sankey_data = [['Клиент', 'Товар', 'Количество'],
                   ['Иван',   'Футболка', 2],
                   ['Мария',  'Кепка',    1]]

    timeline_data = [['Товар', 'Начало', 'Конец']]
    for name, off_s, off_e in [('Футболка', 60, 1), ('Кепка', 50, 5)]:
        timeline_data.append([
            name,
            (timezone.now() - relativedelta(days=off_s)).date().isoformat(),
            (timezone.now() - relativedelta(days=off_e)).date().isoformat()
        ])

    # ---------------------------------------------------- ЛР-7
    # ─────────────────────────────────────────────────────────────── ЛР-7 ──────
    # 1) сами последовательности
    month_profits = [ 80_000,  95_000, 100_000, 110_000, 120_000,
                    130_000, 125_000, 135_000, 140_000, 150_000]

    orders_seq   = [120, 130, 140, 150, 160, 170, 165, 175, 180, 190]          # 👈
    revenue_seq  = [o * 1_000 for o in orders_seq]                              # 👈

    # 2) таблица «Прибыль по месяцам»
    profit_data  = [['Месяц', 'Заказы', 'Выручка', 'Прибыль']]
    for i, p in enumerate(month_profits):
        ym = (base_date - relativedelta(months=len(month_profits)-1-i)).strftime('%Y-%m')
        profit_data.append([ym, orders_seq[i], revenue_seq[i], p])              # 👈 заполняем числами

    # 3) таблица показателей динамики (используем только прибыль, поэтому здесь всё ок)
    indicators_data = [['Месяц', 'yₜ', 'Δцепн.', 'Δбаз.', 'Tцепн %',
                        'Tбаз %', 'Iцепн %', 'Iбаз %']]
    base_p, prev = month_profits[0], None
    for i, y in enumerate(month_profits):
        ym = (base_date - relativedelta(months=len(month_profits)-1-i)).strftime('%Y-%m')
        d_chain = None if prev is None else y - prev
        d_base  = y - base_p
        t_chain = None if prev is None else round(y / prev * 100, 2)
        t_base  = round(y / base_p * 100, 2)
        indicators_data.append([
            ym, y, d_chain, d_base, t_chain, t_base,
            None if t_chain is None else round(t_chain - 100, 2),
            round(t_base - 100, 2)
        ])
        prev = y


    dyn_orders  = [['Период', 'Заказы']]
    dyn_revenue = [['Период', 'Выручка']]
    dyn_users   = [['Период', 'Новые клиенты']]
    if period == 'week':
        for i in range(7):
            lbl = (timezone.now() - relativedelta(weeks=6 - i)).strftime('%Y-%W')
            dyn_orders.append([lbl, 5 + i])
            dyn_revenue.append([lbl, 120000 + i * 50000])
            dyn_users.append([lbl, 1 + (i % 3)])
    else:
        d = [5, 8, 2, 7, 10, 6, 9]
        r = [120000, 190000, 80000, 160000, 210000, 140000, 180000]
        u = [3, 5, 1, 4, 6, 2, 5]
        for i in range(7):
            lbl = (timezone.now() - relativedelta(days=6 - i)).date().isoformat()
            dyn_orders.append([lbl, d[i]])
            dyn_revenue.append([lbl, r[i]])
            dyn_users.append([lbl, u[i]])

    # ---------------------------------------------------- ЛР-8  (MA3 / MA7 / WMA5 + прогноз)
    months = [row[0] for row in profit_data[1:]]
    fact   = [row[3] for row in profit_data[1:]]

    def simple_ma(series, l):
        p = l // 2
        res = [None] * len(series)
        for i in range(p, len(series) - p):
            window = series[i - p:i + p + 1]
            if None in window: continue
            res[i] = sum(window) / l
        return res

    def weighted_ma5(series):
        w = [-3/35, 12/35, 17/35, 12/35, -3/35]
        res = [None] * len(series)
        for i in range(2, len(series) - 2):
            window = series[i - 2:i + 3]
            if None in window: continue
            res[i] = sum(wk * vk for wk, vk in zip(w, window))
        return res

    def restore_edges(series, p):
        n = len(series)
        start_vals = [v for v in series if v is not None][:p + 1]
        if len(start_vals) >= 2:
            inc = sum(start_vals[i] - start_vals[i - 1] for i in range(1, len(start_vals))) / (len(start_vals) - 1)
            first = start_vals[0]
            for i in range(p):
                if series[i] is None:
                    series[i] = first - inc * (p - i)
        end_vals = [v for v in series[::-1] if v is not None][:p + 1]
        if len(end_vals) >= 2:
            inc = sum(end_vals[i] - end_vals[i - 1] for i in range(1, len(end_vals))) / (len(end_vals) - 1)
            last = end_vals[0]
            for i in range(n - p, n):
                if series[i] is None:
                    series[i] = last + inc * (i - (n - p) + 1)

    def forecast_next(series):
        vals = [v for v in series if v is not None]
        if len(vals) < 2: return None
        inc = sum(vals[i] - vals[i - 1] for i in range(1, len(vals))) / (len(vals) - 1)
        return vals[-1] + inc

    ma3  = simple_ma(fact, 3)
    ma7  = simple_ma(fact, 7)
    wma5 = weighted_ma5(fact)

    ma3_orig, ma7_orig, wma5_orig = map(copy.copy, (ma3, ma7, wma5))
    restore_edges(ma3, 1); restore_edges(ma7, 3); restore_edges(wma5, 2)

    next_month = (base_date + relativedelta(months=1)).strftime('%Y-%m')
    f3, f7, fw5 = forecast_next(ma3), forecast_next(ma7), forecast_next(wma5)

    smoothing_calc = []
    for i, m in enumerate(months):
        smoothing_calc.append([
            m, fact[i],
            ma3[i]  is not None and round(ma3[i], 2),
            ma7[i]  is not None and round(ma7[i], 2),
            wma5[i] is not None and round(wma5[i], 2),
            ma3_orig[i] is None and ma3[i] is not None,   # bool-флаги (для подсветки)
            ma7_orig[i] is None and ma7[i] is not None,
            wma5_orig[i] is None and wma5[i] is not None
        ])

    smoothing_forecast = smoothing_calc + [[
        next_month, None,
        f3  is not None and round(f3, 2),
        f7  is not None and round(f7, 2),
        fw5 is not None and round(fw5, 2),
        False, False, False
    ]]

    # ---------------------------------------------------- ЛР-9  (критерии + модели тренда)
    # ❶ Берём сглаженные ряды, посчитанные в ЛР-8
    ma3_series  = [row[2] if row[2] is not False else None for row in smoothing_calc]
    wma5_series = [row[4] if row[4] is not False else None for row in smoothing_calc]
    ma7_series  = [row[3] if row[3] is not False else None for row in smoothing_calc]

    series = [
        ('MA3' , ma3_series ),
        ('WMA5', wma5_series),
        ('MA7' , ma7_series ),
    ]

    # ─────────────────────── 1. критерии серий (кратко) ──────────────────────
    def runs_test_median(y):
        flt = [v for v in y if v is not None]
        n   = len(flt)
        if n == 0: return 0,0,0,0
        med   = np.median(flt)
        signs = [1 if v > med else 0 for v in flt]
        runs  = 1 + sum(signs[i] != signs[i-1] for i in range(1, n))
        n1,n2 = sum(signs), n - sum(signs)
        ER  = 2*n1*n2/n + 1
        Var = (2*n1*n2*(2*n1*n2 - n)) / (n**2 * (n-1)) if n > 1 else 0
        Z   = (runs - ER) / math.sqrt(Var) if Var > 0 else 0
        return runs,ER,Var,Z


    def runs_test_direction(y):
        flt = [v for v in y if v is not None]
        if len(flt) < 2: return 0,0,0,0
        diff = [1 if flt[i] > flt[i-1] else 0 for i in range(1, len(flt))]
        m    = len(diff)
        runs = 1 + sum(diff[i] != diff[i-1] for i in range(1, m))
        n1,n2 = sum(diff), m - sum(diff)
        ER  = 2*n1*n2/(n1+n2) + 1
        Var = (2*n1*n2*(2*n1*n2 - n1 - n2)) / (((n1+n2)**2)*(n1+n2-1)) if (n1+n2) > 1 else 0
        Z   = (runs - ER) / math.sqrt(Var) if Var > 0 else 0
        return runs,ER,Var,Z


    # ───── 1a. критерии (подробно) — для «картинок» 9.1-9.3 ──────
    def runs_test_median_detail(y):
        flt = [v for v in y if v is not None]
        n   = len(flt)
        if n == 0:
            return {}

        med    = float(np.median(flt))
        signs  = ['+' if v > med else '-' for v in flt]

        # собираем серии одинаковых знаков
        series, cur, ln = [], None, 0
        for s in signs:
            if s != cur:
                if cur is not None:
                    series.append({'sign': cur, 'len': ln})
                cur, ln = s, 1
            else:
                ln += 1
        series.append({'sign': cur, 'len': ln})

        v     = len(series)
        tmax  = max(r['len'] for r in series)
        lower = 0.5 * (n + 1 - 1.96 * math.sqrt(n - 1))
        upper = 1.43 * math.log(n + 1)

        # формируем сравнения для вывода
        cmp_v   = f"{v} {'>' if v > lower else '<'} {round(lower,2)}"
        cmp_tmx = f"{tmax} {'<' if tmax < upper else '>'} {round(upper,2)}"

        return {
            'criterion': 'median',
            'n':         n,
            'median':    round(med, 2),
            'signs':     ' '.join(signs),
            'series':    series,
            'v':         v,
            'tmax':      tmax,
            'lowerV':    round(lower, 2),
            'upperT':    round(upper, 2),
            'cmp_v':     cmp_v,
            'cmp_tmx':   cmp_tmx,
            'accept':    (v > lower and tmax < upper)
        }


    def runs_test_updown_detail(y):
        flt = [v for v in y if v is not None]
        if len(flt) < 2:
            return {}

        diff   = np.diff(flt)
        signs  = ['+' if d > 0 else '-' for d in diff]

        # собираем серии одинаковых знаков
        series, cur, ln = [], None, 0
        for s in signs:
            if s != cur:
                if cur is not None:
                    series.append({'sign': cur, 'len': ln})
                cur, ln = s, 1
            else:
                ln += 1
        series.append({'sign': cur, 'len': ln})

        k     = len(signs)
        v     = len(series)
        tmax  = max(r['len'] for r in series)
        lower = (2*k - 1)/3 - 1.96 * math.sqrt((16*k - 29)/90)
        t0    = 5 if k <= 26 else 6 if k <= 153 else 7

        # сравнения для вывода
        cmp_v   = f"{v} {'>' if v > lower else '<'} {round(lower,2)}"
        cmp_tmx = f"{tmax} {'<' if tmax < t0 else '>'} {t0}"

        return {
            'criterion': 'updown',
            'n':         k + 1,
            'signs':     ' '.join(signs),
            'series':    series,
            'v':         v,
            'tmax':      tmax,
            'lowerV':    round(lower, 2),
            'upperT':    t0,
            'cmp_v':     cmp_v,
            'cmp_tmx':   cmp_tmx,
            'accept':    (v > lower and tmax < t0)
        }


    # ────────────────────────── 2a. таблицы 3.5 / 3.6 ──────────────────
    def make_trend_calc_table(y):
        """
        Таблица 3.5 / 3.6.
        Пропускаем элементы, где y is None, чтобы не рушить расчёт.
        """
        # оставляем только валидные точки
        clean = [(idx + 1, v)
                for idx, v in enumerate(y)
                if v is not None]

        n = len(clean)
        if n == 0:
            return []                       # пустая таблица – вернём «ничего»

        # t берём симметрично: −(n−1)/2 … +(n−1)/2  ⇒ Σt = 0
        t_vals = np.arange(-(n - 1) / 2, (n + 1) / 2)

        rows = []
        sums = {k: 0 for k in
                ('y', 't', 'yt', 't2', 'yt2', 't4', 'lny', 'lny_t')}

        for (idx, yt), ti in zip(clean, t_vals):
            ti2 = ti ** 2
            lny = math.log(yt)

            rows.append([
                idx,                   # №
                round(yt, 2),          # yₜ
                ti,                    # t
                round(yt * ti, 3),     # yₜ·t
                ti2,                   # t²
                round(yt * ti2, 3),    # yₜ·t²
                ti2 ** 2,              # t⁴
                round(lny, 3),         # ln(yₜ)
                round(lny * ti, 3)     # ln(yₜ)·t
            ])

            # накапливаем суммы
            sums['y']     += yt
            sums['t']     += ti
            sums['yt']    += yt * ti
            sums['t2']    += ti2
            sums['yt2']   += yt * ti2
            sums['t4']    += ti2 ** 2
            sums['lny']   += lny
            sums['lny_t'] += lny * ti

        # строка Σ
        rows.append([
            'Σ',
            *[round(sums[k], 3) for k in
            ('y', 't', 'yt', 't2', 'yt2', 't4', 'lny', 'lny_t')]
        ])

        return rows



    # ─────────────────────── 3. модели тренда ────────────────────────
    def fit_linear(y):
        arr=np.asarray(y,float);   t=np.arange(1,len(arr)+1)
        a1,a0=np.linalg.lstsq(np.vstack([t,np.ones_like(t)]).T,arr,rcond=None)[0]
        return a0,a1,(a0+a1*t).tolist()

    def fit_parabolic(y):
        arr=np.asarray(y,float);   t=np.arange(1,len(arr)+1)
        a2,a1,a0=np.linalg.lstsq(np.vstack([t**2,t,np.ones_like(t)]).T,arr,rcond=None)[0]
        return a0,a1,a2,(a0+a1*t+a2*t**2).tolist()

    def fit_exponential(y):
        arr=np.asarray(y,float);   t=np.arange(1,len(arr)+1)
        ln_b,ln_a=np.linalg.lstsq(np.vstack([t,np.ones_like(t)]).T,np.log(arr),rcond=None)[0]
        a,b=math.exp(ln_a),math.exp(ln_b)
        return a,b,(a*(b**t)).tolist()


    # ─────────────────────── 4. цикл по трём рядам ──────────────────────────
    series_test, runs_detail, trend_calc = [], [], []
    trend_params, trend_data = [], []

    for name,y in series:
        # краткие критерии
        Rm,Em,Varm,Zm = runs_test_median(y)
        Rd,Ed,Vard,Zd = runs_test_direction(y)
        series_test.append({
            'name':name,
            'R_med':Rm,'E_med':round(Em,2),'Var_med':round(Varm,2),'Z_med':round(Zm,2),
            'R_dir':Rd,'E_dir':round(Ed,2),'Var_dir':round(Vard,2),'Z_dir':round(Zd,2),
        })

        # подробные критерии
        md=runs_test_median_detail(y); md['name']=name
        ud=runs_test_updown_detail(y); ud['name']=name
        runs_detail.extend([md,ud])

        # таблица 3.5/3.6
        trend_calc.append({'name':name,'rows':make_trend_calc_table(y)})

        # параметры моделей
        a0_l,a1_l,y_l          = fit_linear(y)
        a0_p,a1_p,a2_p,y_p     = fit_parabolic(y)
        a_e ,b_e ,y_e          = fit_exponential(y)
        trend_params.append({
            'name':name,
            'a0_lin':a0_l,'a1_lin':a1_l,
            'a0_par':a0_p,'a1_par':a1_p,'a2_par':a2_p,
            'a_exp':a_e ,'b_exp':b_e,
        })
        trend_data.append({
            'name':name,
            'values':[[i+1,y[i],y_l[i],y_p[i],y_e[i]]
                    for i in range(len(y))]
        })




    # ---------------------------------------------------- ЛР-10  (адекватность/точность)
    # после trend_data и т.п.
    # 1) Рассчитываем остатки для каждой модели
    residuals = {}
    for rec in trend_data:
        name = rec['name']
        vals = rec['values']
        actual = np.array([v[1] for v in vals], float)
        pred_lin = np.array([v[2] for v in vals], float)
        pred_par = np.array([v[3] for v in vals], float)
        pred_exp = np.array([v[4] for v in vals], float)
        residuals[name] = {
            'Линейная':      actual - pred_lin,
            'Параболическая': actual - pred_par,
            'Показательная':  actual - pred_exp,
        }

    # 2) Критерий восходящих/нисходящих серий
    def updown_test(e):
        # e — numpy-массив остатков (без NaN)
        signs = ['+' if e[i] > e[i-1] else '-' for i in range(1, len(e))]
        series = []
        cur, ln = None, 0
        for s in signs:
            if s != cur:
                if cur is not None:
                    series.append({'type': cur, 'len': ln})
                cur, ln = s, 1
            else:
                ln += 1
        series.append({'type': cur, 'len': ln})
        k = len(signs)
        v = len(series)
        tmax = max(s['len'] for s in series)
        lower = (2*k - 1)/3 - 1.96 * math.sqrt((16*k - 29)/90)
        upper = 5 if k <= 26 else 6 if k <= 153 else 7
        return {'series': series, 'v': v, 'tmax': tmax, 'lower': lower, 'upper': upper}

    runs_tests = {
        name: { m: updown_test(e[~np.isnan(e)]) 
                for m, e in mods.items() }
        for name, mods in residuals.items()
    }

    # 3) Асимметрия и эксцесс
    def asym_excess(e):
        e = e[~np.isnan(e)]
        n = len(e)
        mu2 = np.mean(e**2)
        A = np.mean(e**3) / mu2**1.5
        E = np.mean(e**4) / mu2**2 - 3
        critA = 1.5 * math.sqrt(6*(n-2)/((n+1)*(n+3)))
        critE = 1.5 * math.sqrt(24*n*(n-2)*(n-3)/((n+1)**2*(n+3)*(n+5)))
        ok = abs(A) < critA and abs(E + 6/(n+1)) < critE
        return {'A': A, 'E': E, 'critA': critA, 'critE': critE, 'ok': ok}

    normal_tests = {
        name: { m: asym_excess(e) for m, e in mods.items() }
        for name, mods in residuals.items()
    }

    def durbin_watson(e):
    # убираем NaN
        e_clean = e[~np.isnan(e)]
        # накопим таблицу и суммы
        table = []
        sum_et_sq = 0.0
        sum_diff_sq = 0.0

        for i, et in enumerate(e_clean):
            et_sq = et**2
            diff_sq = None if i == 0 else (et - e_clean[i-1])**2

            table.append({
                'num':     i+1,
                'et':      et,
                'et_sq':   et_sq,
                'diff_sq': diff_sq,
            })
            sum_et_sq += et_sq
            if diff_sq is not None:
                sum_diff_sq += diff_sq

        # рассчитываем статистику d
        d = sum_diff_sq / sum_et_sq
        d_l, d_u = 1.08, 1.36
        if   d < d_l:
            concl = 'отвергается (положит. автокорреляция)'
        elif d > d_u:
            concl = 'не отвергается'
        else:
            concl = 'неопределённый результат'

        return {
            'd': d,
            'd_l': d_l,
            'd_u': d_u,
            'concl': concl,
            'table': table,
            'sum_et_sq': sum_et_sq,
            'sum_diff_sq': sum_diff_sq,
        }


    dw_tests = {
    name: {
        model: durbin_watson(resid) 
        for model, resid in mods.items()
    }
    for name, mods in residuals.items()
    }
    
    # 5) Метрики точности (MAPE, SSE, MSE, S)
    def metrics(e, actual):
        mask = ~np.isnan(e)
        n = mask.sum()
        se = np.sum(e[mask]**2)
        ae = np.mean(np.abs(e[mask] / actual[mask])) * 100
        return {'MAPE': ae, 'SSE': se, 'MSE': se/n, 'S': math.sqrt(se/n)}

    metrics_tests = {}
    for rec in trend_data:
        name = rec['name']
        actual = np.array([v[1] for v in rec['values']], float)
        metrics_tests[name] = {
            m: metrics(e, actual)
            for m, e in residuals[name].items()
        }

    # 6) Выбор лучших моделей по минимальному MAPE
    best_models = {
        name: min(mt.items(), key=lambda x: x[1]['MAPE'])[0]
        for name, mt in metrics_tests.items()
    }

    # ---------------------------------------------------- контекст для шаблона
    ctx = {
        'period': period,
        # ЛР-6
        'area_json':        mark_safe(json.dumps(area_data)),
        'bubble_json':      mark_safe(json.dumps(bubble_data)),
        'calendar_json':    mark_safe(json.dumps(calendar_data)),
        'org_json':         mark_safe(json.dumps(org_data)),
        'geo_json':         mark_safe(json.dumps(geochart_data)),
        'sankey_json':      mark_safe(json.dumps(sankey_data)),
        'timeline_json':    mark_safe(json.dumps(timeline_data)),
        # ЛР-7
        'profit_json':      mark_safe(json.dumps(profit_data)),
        'indicators_json':  mark_safe(json.dumps(indicators_data)),
        'dyn_orders_json':  mark_safe(json.dumps(dyn_orders)),
        'dyn_revenue_json': mark_safe(json.dumps(dyn_revenue)),
        'dyn_users_json':   mark_safe(json.dumps(dyn_users)),
        # ЛР-8
        'smoothing_calc_json':     mark_safe(json.dumps(smoothing_calc)),
        'smoothing_forecast_json': mark_safe(json.dumps(smoothing_forecast)),
        # ЛР-9
        'series_test_json':  mark_safe(json.dumps(series_test)),
        'trend_params_json': mark_safe(json.dumps(trend_params)),
        'trend_data_json':   mark_safe(json.dumps(trend_data)),
        'trend_calc_json' : mark_safe(json.dumps(trend_calc)),
        'runs_detail_json': mark_safe(json.dumps(runs_detail)),

        # ЛР-10
        'runs_tests': runs_tests,
        'normal_tests': normal_tests,
        'dw_tests': dw_tests,
        'metrics_tests': metrics_tests,
        'best_models': best_models,


    }
    return render(request, 'admin_custom/statistics.html', ctx)
