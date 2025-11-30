import logging
import os
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import PasswordChangeForm
from django.core.mail import send_mail
from django.db import transaction, OperationalError
from django.db.models import Count, Q, F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView

# Импорт форм
from .forms import (
    CustomUserCreationForm,
    EventForm,
    MerchForm,
    OrganizerDiscountForm,
    CommentForm,
    UserEditForm,
    ProfileEditForm,
    TicketPurchaseForm,
    ApplyDiscountForm,
    FeedbackForm,
    MailingTopicForm,
    MailingMessageForm,
    ChatMessageForm,
)

# Импорт моделей
from .models import (
    Profile,
    Event,
    Ticket,
    Merch,
    Seat,
    OrganizerDiscount,
    Comment,
    BuyerDiscount,
    MerchPurchase,
    Partner,
    MailingTopic,
    MailingMessage,
    Subscription,
    EmailLog,
    ChatMessage,
    ChatReaction,
    LoyaltyProgram,
)

logger = logging.getLogger(__name__)

# ============================================================================ 
# Вспомогательные функции
# ============================================================================

def safe_send_mail(subject: str, message_text: str, recipients: list, from_email: str = None) -> bool:
    """
    Обёртка над send_mail:
    - не валит приложение при ошибке SMTP;
    - логирует исключение.
    Возвращает True при успехе, False при ошибке.
    """
    if not recipients:
        return False

    if from_email is None:
        from_email = settings.DEFAULT_FROM_EMAIL

    try:
        send_mail(
            subject,
            message_text,
            from_email,
            recipients,
            fail_silently=False,  # ошибки ловим здесь, а не глушим
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ошибка отправки письма [%s -> %s]: %s", subject, recipients, exc)
        return False


# ============================================================================ 
# Вспомогательные функции программы лояльности
# ============================================================================

def award_loyalty_points_for_ticket(ticket: Ticket) -> int:
    """
    Начисляет пользователю баллы по активной программе лояльности
    за конкретный билет. Возвращает количество начисленных баллов.
    """
    program = LoyaltyProgram.get_active()
    if not program:
        return 0

    effective_price = ticket.get_effective_price()
    if not effective_price or effective_price <= Decimal('0.00'):
        return 0

    raw_points = effective_price * program.points_per_ruble
    points_to_add = int(raw_points.quantize(Decimal('1.'), rounding=ROUND_HALF_UP))

    profile = ticket.user.profile
    profile.points = F('points') + points_to_add
    profile.save(update_fields=['points'])
    profile.refresh_from_db(fields=['points'])

    return points_to_add


def issue_buyer_discounts_for_ticket(ticket: Ticket) -> int:
    """
    На основе настроенных OrganizerDiscount для организатора мероприятия
    выдаёт/обновляет персональные скидки (BuyerDiscount) покупателю.
    Возвращает количество созданных/обновлённых скидок.
    """
    organizer = ticket.event.organizer
    buyer_profile = ticket.user.profile

    organizer_discounts = OrganizerDiscount.objects.filter(from_organizer=organizer)
    created_or_updated = 0

    for od in organizer_discounts:
        # если у BuyerDiscount есть поле target_organizer:
        # bd, created = BuyerDiscount.objects.get_or_create(
        #     buyer=buyer_profile,
        #     from_organizer=od.from_organizer,
        #     target_organizer=od.target_organizer,
        #     defaults={'discount_rate': od.discount_rate}
        # )

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

    return created_or_updated


# ============================================================================ 
# Основные функции сайта
# ============================================================================

def home(request):
    query = request.GET.get('q', '').strip()
    event_type = request.GET.get('event_type', 'all').strip()
    city = request.GET.get('city', '').strip()
    date_str = request.GET.get('date', '').strip()

    events = Event.objects.all()
    if query:
        events = events.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if event_type != 'all':
        events = events.filter(event_type=event_type)
    if city:
        events = events.filter(location__icontains=city)
    if date_str:
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            events = events.filter(date__date=date_obj)
        except ValueError:
            pass
    events = events.order_by('date')
    context = {
        'events': events,
        'query': query,
        'event_type': event_type,
        'city': city,
        'date': date_str,
    }
    return render(request, 'main/home.html', context)


def platform_info(request):
    return render(request, 'main/platform_info.html')


def logout_view(request):
    if request.method == 'POST':
        logout(request)
        messages.info(request, "Вы успешно вышли из системы.")
        return redirect('home')
    return redirect('home')


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Добро пожаловать, {user.username}!")
            return redirect('home')
        else:
            messages.error(request, "Ошибка регистрации. Проверьте введённые данные.")
    else:
        form = CustomUserCreationForm()
    return render(request, 'main/register.html', {'form': form})


def feedback(request):
    """
    Обратная связь с платформой. Письмо отправляется на EMAIL_HOST_USER.
    Ошибка SMTP не валит сайт.
    """
    if request.method == 'POST':
        form = FeedbackForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data.get('subject')
            message_text = form.cleaned_data.get('message')
            sender_email = getattr(request.user, 'email', '') or 'аноним'
            full_message = f"От: {sender_email}\n\n{message_text}"

            sent_ok = safe_send_mail(subject, full_message, [settings.EMAIL_HOST_USER])
            if sent_ok:
                # Логируем только успешную отправку
                if request.user.is_authenticated:
                    EmailLog.objects.create(user=request.user, message_text=full_message)
                messages.success(request, "Ваше сообщение отправлено!")
            else:
                messages.warning(
                    request,
                    "Не удалось отправить письмо. Попробуйте позже или свяжитесь с поддержкой другим способом."
                )
            return redirect('profile')
        else:
            messages.error(request, "Ошибка при отправке сообщения.")
    else:
        form = FeedbackForm()
    return render(request, 'main/feedback.html', {'form': form})


@login_required
def profile(request, pk=None):
    if pk:
        user_obj = get_object_or_404(get_user_model(), pk=pk)
        profile_obj = user_obj.profile
    else:
        profile_obj = request.user.profile

    # Получаем список id тем, на которые подписан пользователь
    try:
        subscribed_topic_ids = list(request.user.subscriptions.values_list('topic_id', flat=True))
    except Exception:  # noqa: BLE001
        subscribed_topic_ids = []

    # Получаем билеты пользователя
    tickets = Ticket.objects.filter(user=profile_obj.user).select_related('event')
    cultural_tickets = tickets.filter(event__event_type='culture')
    sports_tickets = tickets.filter(event__event_type='sport')

    # Пытаемся получить темы рассылок, если таблица существует
    try:
        mailing_topics = list(MailingTopic.objects.all())
    except Exception:  # noqa: BLE001
        mailing_topics = []

    # Базовый контекст
    context = {
        'profile': profile_obj,
        'cultural_tickets': cultural_tickets,
        'sports_tickets': sports_tickets,
        'mailing_topics': mailing_topics,
        'subscribed_topic_ids': subscribed_topic_ids,
    }

    # --- Блок для организатора ---
    if profile_obj.user_type == 'organizer':
        events = Event.objects.filter(organizer=profile_obj)
        organizer_comments = Comment.objects.filter(event__organizer=profile_obj)
        context.update({
            'events': events,
            'organizer_comments': organizer_comments,
        })

    # --- Блок для покупателя ---
    elif profile_obj.user_type == 'buyer':
        # Тут важно: подтягиваем связанные профили организаторов,
        # чтобы в шаблоне можно было легко вывести
        # "от кого" и "на кого" скидка.
        #
        # Если в твоей модели BuyerDiscount поле называется не target_organizer,
        # а, например, to_organizer / for_organizer — просто поправь название в select_related.
        buyer_discounts = BuyerDiscount.objects.filter(buyer=profile_obj) \
            .select_related(
                'from_organizer__user',    # организатор, который выдал скидку
                # 'target_organizer__user',   # <- раскомментируй/переименуй под своё поле, если оно есть
            ) \
            .order_by('-created_at')

        purchases = MerchPurchase.objects.filter(user=profile_obj.user).select_related('merch')

        confirmed_tickets = tickets.filter(is_confirmed=True).select_related('event__partner')
        partner_discounts = {
            ticket.event.partner
            for ticket in confirmed_tickets
            if ticket.event.partner and ticket.event.partner.discount_rate > 0
        }

        context.update({
            'buyer_discounts': buyer_discounts,
            'purchases': purchases,
            'partner_discounts': list(partner_discounts),
        })

    return render(request, 'main/profile.html', context)



@login_required
def apply_discount_to_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id, user=request.user)
    if ticket.is_confirmed:
        messages.error(request, "Нельзя применять скидку к уже оплаченному билету.")
        return redirect('profile')
    event_type = ticket.event.event_type
    if request.method == 'POST':
        form = ApplyDiscountForm(request.POST, buyer=request.user.profile, event_type=event_type)
        if form.is_valid():
            discount = form.cleaned_data.get('discount_id')
            ticket.applied_discount = discount
            ticket.discounted_price = ticket.price * (Decimal('1.00') - discount.discount_rate / Decimal('100'))
            ticket.save()
            discount.is_applied = True
            discount.save()
            messages.success(request, f"Скидка {discount.discount_rate}% успешно применена к билету.")
            return redirect('profile')
        else:
            messages.error(request, "Ошибка при применении скидки.")
    else:
        form = ApplyDiscountForm(buyer=request.user.profile, event_type=event_type)
    return render(request, 'main/apply_discount.html', {'ticket': ticket, 'form': form})


@login_required
def edit_profile(request):
    user = request.user
    profile_obj = user.profile
    is_organizer = (profile_obj.user_type == 'organizer')
    if request.method == 'POST':
        if 'update_profile' in request.POST:
            user_form = UserEditForm(request.POST, instance=user)
            profile_form = ProfileEditForm(request.POST, instance=profile_obj, is_organizer=is_organizer)
            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                messages.success(request, "Профиль успешно обновлён.")
                return redirect('profile')
            else:
                messages.error(request, "Исправьте ошибки в форме.")
                password_form = PasswordChangeForm(user=user)
        elif 'change_password' in request.POST:
            password_form = PasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                messages.success(request, "Пароль успешно изменён.")
                return redirect('profile')
            else:
                messages.error(request, "Ошибка при изменении пароля.")
                user_form = UserEditForm(instance=user)
                profile_form = ProfileEditForm(instance=profile_obj, is_organizer=is_organizer)
        else:
            user_form = UserEditForm(instance=user)
            profile_form = ProfileEditForm(instance=profile_obj, is_organizer=is_organizer)
            password_form = PasswordChangeForm(user=user)
    else:
        user_form = UserEditForm(instance=user)
        profile_form = ProfileEditForm(instance=profile_obj, is_organizer=is_organizer)
        password_form = PasswordChangeForm(user=user)
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
    }
    return render(request, 'main/edit_profile.html', context)


def organizer_detail(request, pk):
    organizer = get_object_or_404(Profile, pk=pk, user_type='organizer')
    events = Event.objects.filter(organizer=organizer)
    organizer_comments = Comment.objects.filter(event__organizer=organizer)
    return render(request, 'main/organizer_detail.html', {'organizer': organizer, 'events': events, 'organizer_comments': organizer_comments})


@login_required
def create_event(request):
    profile_obj = request.user.profile
    if profile_obj.user_type != 'organizer':
        messages.error(request, "Только организаторы могут создавать мероприятия.")
        return redirect('home')
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, organizer=profile_obj)
        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = profile_obj
            organizer_discount = form.cleaned_data.get('organizer_discount')
            if organizer_discount:
                event.discount = organizer_discount.discount_rate
            event.save()
            # создаём 10 рядов по 20 мест
            for row in range(1, 11):
                for number in range(1, 21):
                    Seat.objects.create(event=event, row=row, number=str(number))
            messages.success(request, f'Мероприятие "{event.name}" создано успешно.')
            return redirect('event_detail', pk=event.pk)
        else:
            messages.error(request, "Ошибка при создании мероприятия. Проверьте введённые данные.")
    else:
        form = EventForm(organizer=profile_obj)
    return render(request, 'main/create_event.html', {'form': form})


def event_list(request):
    query = request.GET.get('q', '').strip()
    event_type = request.GET.get('event_type', 'all').strip()
    city = request.GET.get('city', '').strip()
    date_str = request.GET.get('date', '').strip()
    events = Event.objects.all()
    if query:
        events = events.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if event_type != 'all':
        events = events.filter(event_type=event_type)
    if city:
        events = events.filter(location__icontains=city)
    if date_str:
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            events = events.filter(date__date=date_obj)
        except ValueError:
            pass
    events = events.order_by('date')
    context = {
        'events': events,
        'query': query,
        'event_type': event_type,
        'city': city,
        'date': date_str,
    }
    return render(request, 'main/event_list.html', context)


def event_detail(request, pk):
    event = get_object_or_404(Event, pk=pk)
    user_has_confirmed_ticket = False
    if request.user.is_authenticated:
        user_has_confirmed_ticket = Ticket.objects.filter(event=event, user=request.user, is_confirmed=True).exists()
    return render(request, 'main/event_detail.html', {'event': event, 'user_has_confirmed_ticket': user_has_confirmed_ticket})


def ticket_success(request):
    return render(request, 'main/ticket_success.html')


@login_required
def edit_event(request, pk):
    event = get_object_or_404(Event, pk=pk, organizer=request.user.profile)
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event, organizer=request.user.profile)
        if form.is_valid():
            form.save()
            messages.success(request, f'Мероприятие "{event.name}" обновлено!')
            return redirect('event_detail', pk=event.pk)
        else:
            messages.error(request, "Ошибка при обновлении мероприятия.")
    else:
        form = EventForm(instance=event, organizer=request.user.profile)
    return render(request, 'main/edit_event.html', {'form': form, 'event': event})


@login_required
def delete_event(request, pk):
    event = get_object_or_404(Event, pk=pk, organizer=request.user.profile)
    if request.method == 'POST':
        event.delete()
        messages.success(request, "Мероприятие удалено.")
        return redirect('event_list')
    return render(request, 'main/delete_event.html', {'event': event})

# ============================================================================ 
# MERCH (товары)
# ============================================================================

class MerchListView(ListView):
    model = Merch
    template_name = 'main/merch_list.html'
    context_object_name = 'merch_items'


class MerchDetailView(DetailView):
    model = Merch
    template_name = 'main/merch_detail.html'
    context_object_name = 'merch'


@login_required
def purchase_merch(request, pk):
    merch = get_object_or_404(Merch, pk=pk)
    profile_obj = request.user.profile
    if request.method == 'POST':
        if profile_obj.points >= merch.price_in_points:
            profile_obj.points -= merch.price_in_points
            profile_obj.save()
            MerchPurchase.objects.create(user=request.user, merch=merch)
            messages.success(request, f'Вы успешно приобрели "{merch.name}"!')
            return redirect('merch_detail', pk=pk)
        else:
            messages.error(request, "У вас недостаточно баллов для покупки.")
            return redirect('merch_detail', pk=pk)
    return render(request, 'main/purchase_merch.html', {'merch': merch})

# ============================================================================ 
# Страницы со статическим контентом
# ============================================================================

def privacy_policy(request):
    return render(request, 'main/privacy_policy.html')


def terms_of_service(request):
    return render(request, 'main/terms_of_service.html')

# ============================================================================ 
# Выбор места на мероприятии
# ============================================================================

@login_required
def select_seat(request, event_id):
    """
    Выбор места + создание билета.
    Важно: создание билета и блокировка места выполняются в транзакции.
    Отправка письма вынесена за пределы транзакции, чтобы ошибка SMTP
    не откатывала покупку.
    """
    event = get_object_or_404(Event, pk=event_id)
    seats = Seat.objects.filter(event=event).order_by('row', 'number')
    seats_matrix = [seats.filter(row=row).order_by('number') for row in range(1, 11)]

    if request.method == 'POST':
        seat_id = request.POST.get('seat_id')
        if not seat_id:
            messages.error(request, "Пожалуйста, выберите место.")
            return redirect('select_seat', event_id=event.id)

        original_price = event.ticket_price

        try:
            with transaction.atomic():
                # внутри транзакции ещё раз проверяем доступность места
                try:
                    seat = Seat.objects.select_for_update().get(
                        id=seat_id,
                        event=event,
                        is_available=True,
                    )
                except Seat.DoesNotExist:
                    messages.error(request, "Место недоступно или уже занято.")
                    return redirect('select_seat', event_id=event.id)

                ticket = Ticket.objects.create(
                    event=event,
                    user=request.user,
                    seat=seat,
                    is_confirmed=False,
                    price=original_price,
                    discounted_price=original_price,
                )

                seat.is_available = False
                seat.save()

        except OperationalError as exc:
            # типичная ошибка sqlite: "database is locked"
            logger.warning("Ошибка БД при бронировании места: %s", exc)
            messages.error(
                request,
                "База данных временно недоступна. Попробуйте ещё раз через несколько секунд."
            )
            return redirect('select_seat', event_id=event.id)

        # === ВНЕ транзакции формируем и отправляем письмо ===
        order_subject = f"Заказ билета на {event.name}"
        order_message = (
            f"Здравствуйте, {request.user.username}!\n\n"
            f"Вы успешно заказали билет на мероприятие '{event.name}'.\n"
            f"Ряд: {seat.row}, Место: {seat.number}.\n"
            f"Цена: {ticket.price} руб.\n\n"
            "Спасибо за покупку!"
        )

        sent_ok = safe_send_mail(order_subject, order_message, [request.user.email])

        if sent_ok:
            EmailLog.objects.create(user=request.user, message_text=order_message)
            messages.success(
                request,
                "Билет создан, письмо с деталями отправлено на вашу почту. "
                "Ожидается подтверждение оплаты."
            )
        else:
            messages.warning(
                request,
                "Билет создан, но письмо с деталями не удалось отправить. "
                "Проверьте профиль для просмотра информации о заказе."
            )

        return redirect('ticket_success')

    return render(request, 'main/select_seat.html', {
        'event': event,
        'seats_matrix': seats_matrix,
    })

# ============================================================================ 
# Управление скидками для организаторов
# ============================================================================

@login_required
def manage_discounts(request):
    profile_obj = request.user.profile
    if profile_obj.user_type != 'organizer':
        messages.error(request, "Доступ запрещён.")
        return redirect('home')
    if request.method == 'POST':
        form = OrganizerDiscountForm(request.POST, organizer=profile_obj)
        if form.is_valid():
            discount = form.save(commit=False)
            discount.from_organizer = profile_obj
            discount.save()
            messages.success(request, "Скидка успешно установлена.")
            return redirect('manage_discounts')
    else:
        form = OrganizerDiscountForm(organizer=profile_obj)
    discounts = OrganizerDiscount.objects.filter(from_organizer=profile_obj)
    return render(request, 'main/manage_discounts.html', {'form': form, 'discounts': discounts})


def organizer_list(request):
    query = request.GET.get('q', '').strip()
    city = request.GET.get('city', '').strip()
    event_type = request.GET.get('event_type', '').strip()
    organizers = Profile.objects.filter(user_type='organizer')
    if query:
        organizers = organizers.filter(user__username__icontains=query)
    if city:
        organizers = organizers.filter(city__icontains=city)
    if event_type:
        organizers = organizers.filter(event_type=event_type)
    context = {
        'organizers': organizers,
        'query': query,
        'city': city,
        'event_type': event_type,
    }
    return render(request, 'main/organizer_list.html', context)


@login_required
def add_comment(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    if not Ticket.objects.filter(event=event, user=request.user, is_confirmed=True).exists():
        messages.error(request, "У вас нет оплаченного билета на это мероприятие.")
        return redirect('event_detail', pk=event.pk)
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.user = request.user
            comment.event = event
            comment.save()
            messages.success(request, "Отзыв успешно добавлен!")
            return redirect('event_detail', pk=event.pk)
        else:
            messages.error(request, "Ошибка при добавлении отзыва.")
    else:
        form = CommentForm()
    return render(request, 'main/add_comment.html', {'form': form, 'event': event})

# ============================================================================ 
# Функции для организаторов по работе с билетами
# ============================================================================

def user_is_organizer(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.user_type == 'organizer'


@login_required
@user_passes_test(user_is_organizer)
def organizer_buyers_list(request):
    organizer_profile = request.user.profile
    events = Event.objects.filter(organizer=organizer_profile)
    tickets = Ticket.objects.filter(event__in=events).select_related('user', 'seat', 'event')
    return render(request, 'main/organizer_buyers_list.html', {'tickets': tickets})


@login_required
@user_passes_test(user_is_organizer)
def confirm_ticket_purchase(request, ticket_id):
    """
    Организатор подтверждает покупку билета:
    - помечаем билет как оплаченный;
    - начисляем баллы по активной программе лояльности;
    - выдаём/обновляем персональные скидки по настроенным OrganizerDiscount.
    """
    organizer_profile = request.user.profile
    ticket = get_object_or_404(Ticket, id=ticket_id, event__organizer=organizer_profile)
    if request.method == 'POST':
        if not ticket.is_confirmed:
            ticket.is_confirmed = True
            ticket.save()

            added_points = award_loyalty_points_for_ticket(ticket)
            created_discounts = issue_buyer_discounts_for_ticket(ticket)

            msg_parts = ["Оплата билета подтверждена."]
            if added_points > 0:
                msg_parts.append(f"Начислено {added_points} баллов.")
            if created_discounts > 0:
                msg_parts.append(f"Выдано/обновлено скидок: {created_discounts}.")
            messages.success(request, " ".join(msg_parts))
        else:
            messages.info(request, "Этот билет уже подтверждён.")
        return redirect('organizer_buyers_list')
    return render(request, 'main/confirm_ticket_purchase.html', {'ticket': ticket})

# ============================================================================ 
# PDF-отчёты
# ============================================================================

@login_required
def pdf_user_orders(request, user_id):
    User = get_user_model()
    user = get_object_or_404(User, pk=user_id)
    tickets = Ticket.objects.filter(user=user).select_related('event')
    total_amount = sum(ticket.get_effective_price() for ticket in tickets)

    response = HttpResponse(content_type='application/pdf')
    filename = f"user_{user_id}_orders.pdf"
    response['Content-Disposition'] = f'attachment; filename=\"{filename}\"'

    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_path = os.path.join(settings.BASE_DIR, 'main', 'fonts', 'DejaVuSans.ttf')
    pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))

    c = canvas.Canvas(response)
    c.setTitle(f"Выписка для пользователя {user.username}")
    c.setFont('DejaVuSans', 12)

    def draw_header():
        c.drawString(50, 800, f"Выписка для пользователя: {user.username}")
        c.drawString(50, 780, f"Email: {user.email}")

    draw_header()
    current_y = 740
    if tickets.exists():
        c.drawString(50, current_y, "Список заказов:")
        current_y -= 20
        for ticket in tickets:
            if current_y < 50:
                c.showPage()
                c.setFont('DejaVuSans', 12)
                draw_header()
                current_y = 740
            event_name = ticket.event.name if ticket.event else "Без названия"
            purchase_date_str = ticket.purchase_date.strftime("%d.%m.%Y %H:%M")
            effective_price = ticket.get_effective_price()
            price_str = f"{effective_price:.2f} руб."
            line_text = f"- {event_name} | {purchase_date_str} | {price_str}"
            c.drawString(60, current_y, line_text)
            current_y -= 20
        if current_y < 50:
            c.showPage()
            c.setFont('DejaVuSans', 12)
            draw_header()
            current_y = 740
        current_y -= 10
        c.drawString(50, current_y, f"Общая сумма: {total_amount:.2f} руб.")
    else:
        c.drawString(50, current_y, "Нет заказов.")
    c.showPage()
    c.save()
    return response


@login_required
def pdf_pricelist_sport(request):
    events = Event.objects.filter(event_type='sport')

    response = HttpResponse(content_type='application/pdf')
    filename = "pricelist_sport.pdf"
    response['Content-Disposition'] = f'attachment; filename=\"{filename}\"'

    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_path = os.path.join(settings.BASE_DIR, 'main', 'fonts', 'DejaVuSans.ttf')
    pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))

    c = canvas.Canvas(response)
    c.setTitle("Прайс-лист спортивных мероприятий")
    c.setFont('DejaVuSans', 12)

    c.drawString(50, 800, "Прайс-лист спортивных мероприятий")
    current_y = 760
    if events.exists():
        c.drawString(50, current_y, "Название")
        c.drawString(300, current_y, "Цена билета")
        c.drawString(420, current_y, "Организатор")
        current_y -= 20
        c.line(50, current_y + 10, 550, current_y + 10)

        for event in events:
            event_name = event.name
            price = f"{event.ticket_price:.2f} руб."
            organizer = event.organizer.user.username
            c.drawString(50, current_y, event_name)
            c.drawString(300, current_y, price)
            c.drawString(420, current_y, organizer)
            current_y -= 20
            if current_y < 50:
                c.showPage()
                c.setFont('DejaVuSans', 12)
                current_y = 800
    else:
        c.drawString(50, current_y, "Нет спортивных мероприятий.")

    c.showPage()
    c.save()
    return response


@login_required
def pdf_pricelist_culture(request):
    events = Event.objects.filter(event_type='culture')

    response = HttpResponse(content_type='application/pdf')
    filename = "pricelist_culture.pdf"
    response['Content-Disposition'] = f'attachment; filename=\"{filename}\"'

    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_path = os.path.join(settings.BASE_DIR, 'main', 'fonts', 'DejaVuSans.ttf')
    pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))

    c = canvas.Canvas(response)
    c.setTitle("Прайс-лист культурных мероприятий")
    c.setFont('DejaVuSans', 12)

    c.drawString(50, 800, "Прайс-лист культурных мероприятий")
    current_y = 760
    if events.exists():
        c.drawString(50, current_y, "Название")
        c.drawString(300, current_y, "Цена билета")
        c.drawString(420, current_y, "Организатор")
        current_y -= 20
        c.line(50, current_y + 10, 550, current_y + 10)

        for event in events:
            event_name = event.name
            price = f"{event.ticket_price:.2f} руб."
            organizer = event.organizer.user.username
            c.drawString(50, current_y, event_name)
            c.drawString(300, current_y, price)
            c.drawString(420, current_y, organizer)
            current_y -= 20
            if current_y < 50:
                c.showPage()
                c.setFont('DejaVuSans', 12)
                current_y = 800
    else:
        c.drawString(50, current_y, "Нет культурных мероприятий.")

    c.showPage()
    c.save()
    return response


@login_required
def pdf_revenue_report(request):
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2026, 12, 31)

    tickets = Ticket.objects.filter(is_confirmed=True, purchase_date__gte=start_date, purchase_date__lte=end_date)

    revenue_by_month = defaultdict(Decimal)
    overall_total = Decimal('0.00')
    for ticket in tickets:
        month_str = ticket.purchase_date.strftime("%Y-%m")
        effective_price = ticket.get_effective_price()
        revenue_by_month[month_str] += effective_price
        overall_total += effective_price

    response = HttpResponse(content_type='application/pdf')
    filename = "revenue_report_2024-2026.pdf"
    response['Content-Disposition'] = f'attachment; filename=\"{filename}\"'

    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font_path = os.path.join(settings.BASE_DIR, 'main', 'fonts', 'DejaVuSans.ttf')
    pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))

    c = canvas.Canvas(response)
    c.setTitle("Отчет о выручке за период 2024-2026")
    c.setFont('DejaVuSans', 12)
    c.drawString(50, 800, "Отчет о выручке за период 2024-2026")
    c.drawString(50, 780, "Период: 01.01.2024 - 31.12.2026")
    current_y = 740
    if revenue_by_month:
        for month, total in sorted(revenue_by_month.items()):
            line = f"{month}: {total:.2f} руб."
            c.drawString(50, current_y, line)
            current_y -= 20
            if current_y < 50:
                c.showPage()
                c.setFont('DejaVuSans', 12)
                current_y = 800
        current_y -= 10
        c.drawString(50, current_y, f"Общая выручка: {overall_total:.2f} руб.")
    else:
        c.drawString(50, current_y, "Нет данных за указанный период.")
    c.showPage()
    c.save()
    return response

# ============================================================================ 
# Google Charts (Контрольная точка №5)
# ============================================================================

@login_required
def charts(request):
    # Подтверждённые билеты по типам
    sport_tickets = Ticket.objects.filter(event__event_type='sport', is_confirmed=True)
    culture_tickets = Ticket.objects.filter(event__event_type='culture', is_confirmed=True)

    # Гистограммы: дата покупки — фактическая цена
    sport_histogram_data = [["Дата", "Цена"]]
    for ticket in sport_tickets:
        sport_histogram_data.append([
            ticket.purchase_date.strftime("%Y-%m-%d"),
            float(ticket.get_effective_price())
        ])

    culture_histogram_data = [["Дата", "Цена"]]
    for ticket in culture_tickets:
        culture_histogram_data.append([
            ticket.purchase_date.strftime("%Y-%m-%d"),
            float(ticket.get_effective_price())
        ])

    # Круговая диаграмма: затраты пользователя по типам мероприятий
    orders = Ticket.objects.filter(user=request.user, is_confirmed=True).select_related('event')
    spending = defaultdict(Decimal)
    for order in orders:
        spending[order.event.event_type] += order.get_effective_price()
    pie_data = [["Категория", "Сумма"]]
    for cat, amount in spending.items():
        pie_data.append([cat, float(amount)])

    # Линейный график: выручка по дням (по фактической цене)
    tickets = Ticket.objects.filter(is_confirmed=True)
    revenue = defaultdict(Decimal)
    for ticket in tickets:
        day = ticket.purchase_date.strftime("%Y-%m-%d")
        revenue[day] += ticket.get_effective_price()
    line_data = [["День", "Выручка"]]
    for day, total in sorted(revenue.items()):
        line_data.append([day, float(total)])

    context = {
        'sport_histogram_data': sport_histogram_data,
        'culture_histogram_data': culture_histogram_data,
        'pie_data': pie_data,
        'line_data': line_data,
    }
    return render(request, 'main/charts.html', context)

# ============================================================================ 
# Групповой чат
# ============================================================================

def chat(request):
    sort_by = request.GET.get('sort', 'new')
    messages_qs = ChatMessage.objects.all()
    if sort_by == 'popular':
        messages_qs = messages_qs.annotate(
            like_count=Count('reactions', filter=Q(reactions__reaction_type='like')),
            reply_count=Count('replies')
        ).annotate(
            popularity=F('like_count') + F('reply_count')
        ).order_by('-popularity', '-created_at')
    else:
        messages_qs = messages_qs.order_by('-created_at')
    context = {
        'messages': messages_qs,
        'sort_by': sort_by,
    }
    return render(request, 'chat/chat.html', context)


@login_required
def chat_api(request):
    if request.method == 'GET':
        messages_qs = ChatMessage.objects.all().order_by('created_at')
        data = [
            {
                'id': m.id,
                'user': m.user.username,
                'content': m.content,
                'timestamp': m.created_at.isoformat()
            }
            for m in messages_qs
        ]
        return JsonResponse({'messages': data})
    elif request.method == 'POST':
        content = request.POST.get('content')
        if not content:
            return JsonResponse({'status': 'error', 'error': 'Content cannot be empty'}, status=400)
        message_obj = ChatMessage.objects.create(user=request.user, content=content)
        return JsonResponse({
            'status': 'success',
            'message': {
                'id': message_obj.id,
                'user': message_obj.user.username,
                'content': message_obj.content,
                'timestamp': message_obj.created_at.isoformat()
            }
        })
    else:
        return JsonResponse({'status': 'error', 'error': 'Invalid HTTP method'}, status=405)


@login_required
def chat_reply(request, parent_id):
    parent_msg = get_object_or_404(ChatMessage, id=parent_id)
    if request.method == 'POST':
        form = ChatMessageForm(request.POST)
        if form.is_valid():
            reply = form.save(commit=False)
            reply.user = request.user
            reply.parent = parent_msg
            reply.save()
            messages.success(request, "Ответ отправлен!")
            return redirect('chat')
        else:
            messages.error(request, "Ошибка отправки ответа.")
    else:
        form = ChatMessageForm(initial={'parent': parent_id})
    return render(request, 'chat/chat_reply.html', {'form': form, 'parent': parent_msg})


@login_required
def delete_chat_message(request, message_id):
    message_obj = get_object_or_404(ChatMessage, id=message_id)
    if request.user == message_obj.user or request.user.is_staff:
        message_obj.delete()
        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error', 'error': 'Нет прав на удаление'}, status=403)


@login_required
def chat_reaction(request, message_id, reaction_type):
    message_obj = get_object_or_404(ChatMessage, id=message_id)
    if reaction_type not in ['like', 'dislike']:
        return JsonResponse({'status': 'error', 'error': 'Неверный тип реакции.'}, status=400)
    reaction, created = ChatReaction.objects.get_or_create(
        user=request.user,
        message=message_obj,
        defaults={'reaction_type': reaction_type}
    )
    if not created:
        if reaction.reaction_type != reaction_type:
            reaction.reaction_type = reaction_type
            reaction.save()
            return JsonResponse({'status': 'success'})
        else:
            return JsonResponse({'status': 'info', 'error': 'Вы уже поставили эту реакцию.'})
    return JsonResponse({'status': 'success'})

# ============================================================================ 
# Рассылки (подписки + админка)
# ============================================================================

def user_is_admin(user):
    return user.is_authenticated and (
        user.is_superuser or (hasattr(user, 'profile') and user.profile.user_type == 'admin')
    )


@login_required
def subscribe_topic(request, topic_id):
    topic = get_object_or_404(MailingTopic, pk=topic_id)
    Subscription.objects.get_or_create(user=request.user, topic=topic)
    messages.success(request, f"Вы подписались на тему: {topic.name}")
    return redirect('profile')


@login_required
def unsubscribe_topic(request, topic_id):
    topic = get_object_or_404(MailingTopic, pk=topic_id)
    Subscription.objects.filter(user=request.user, topic=topic).delete()
    messages.success(request, f"Вы отписались от темы: {topic.name}")
    return redirect('profile')


@login_required
def admin_mailing_dashboard(request):
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    topics = MailingTopic.objects.all()
    stats = [{'topic': topic, 'sent_count': topic.messages.count()} for topic in topics]
    return render(request, 'admin_custom/mailing_dashboard.html', {'stats': stats})


@login_required
def admin_create_mailing_topic(request):
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
    return render(request, 'admin_custom/mailing_topic_form.html', {'form': form, 'title': 'Создать тему рассылки'})


@login_required
def admin_create_mailing_message(request):
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    if request.method == 'POST':
        form = MailingMessageForm(request.POST)
        if form.is_valid():
            mailing_message = form.save()

            # здесь можно включить реальную отправку писем подписчикам, если нужно
            # (оставляю без реализации, чтобы не ломать твой код из-за неизвестных полей модели)
            # subscriptions = mailing_message.topic.subscriptions.select_related('user')
            # recipient_list = [sub.user.email for sub in subscriptions if sub.user.email]

            messages.success(request, "Сообщение создано! (Рассылка может быть реализована отдельно.)")
            return redirect('admin_mailing_stats')
    else:
        form = MailingMessageForm()
    return render(request, 'admin_custom/mailing_message_form.html', {'form': form, 'title': 'Создать сообщение рассылки'})


@login_required
def admin_mailing_stats(request):
    if not user_is_admin(request.user):
        messages.error(request, "Нет доступа.")
        return redirect('home')
    topics = MailingTopic.objects.all()
    stats = [{'topic': topic, 'sent_count': topic.messages.count()} for topic in topics]
    return render(request, 'admin_custom/mailing_stats.html', {'stats': stats})


@login_required
def view_mailing_messages(request):
    # Получаем темы, на которые подписан пользователь
    subscribed_topics = MailingTopic.objects.filter(subscriptions__user=request.user)
    # Получаем все сообщения из этих тем (сортируем по дате отправки, от новых к старым)
    messages_qs = MailingMessage.objects.filter(topic__in=subscribed_topics).order_by('-sent_at')
    context = {
        'mailing_messages': messages_qs,
    }
    return render(request, 'main/mailing_messages.html', context)
