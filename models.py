# main/models.py
import uuid
from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


def generate_default_mailing_topic_name():
    now_str = timezone.now().strftime("%d.%m.%Y %H:%M")
    unique_part = uuid.uuid4().hex[:6]
    return f"Рассылка {now_str} {unique_part}"


def generate_unique_subject():
    """
    Генерация уникального темы письма по умолчанию.
    """
    return generate_default_mailing_topic_name()


class Profile(models.Model):
    USER_TYPE_CHOICES = [
        ('buyer', 'Покупатель'),
        ('organizer', 'Организатор'),
        ('admin', 'Администратор'),
    ]
    EVENT_TYPE_CHOICES = [
        ('sport', 'Спортивное'),
        ('culture', 'Культурное'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)
    event_type = models.CharField(max_length=10, choices=EVENT_TYPE_CHOICES, null=True, blank=True)
    city = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=255, blank=True, verbose_name="Адрес")
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    points = models.IntegerField(default=0)

    def __str__(self):
        return self.user.username


class LoyaltyProgram(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    points_per_ruble = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('1.00'),
        verbose_name='Баллы за рубль'
    )
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Программа лояльности"
        verbose_name_plural = "Программы лояльности"

    def __str__(self):
        return self.name

    @classmethod
    def get_active(cls):
        """
        Возвращает активную программу лояльности.
        Если активных несколько — берём последнюю по id.
        """
        return cls.objects.filter(active=True).order_by('-id').first()


class Partner(models.Model):
    name = models.CharField(max_length=100)
    website = models.URLField(blank=True, null=True)
    discount_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Скидка от партнёра (%)'
    )
    organizer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='partners')

    def __str__(self):
        return self.name


class Event(models.Model):
    EVENT_TYPE_CHOICES = [
        ('sport', 'Спортивное'),
        ('culture', 'Культурное'),
    ]
    STATUS_CHOICES = [
        ('upcoming', 'Предстоящее'),
        ('completed', 'Завершённое'),
    ]
    name = models.CharField(max_length=200)
    description = models.TextField()
    date = models.DateTimeField()
    location = models.CharField(max_length=200)
    ticket_price = models.DecimalField(max_digits=10, decimal_places=2)
    ticket_quantity = models.PositiveIntegerField()
    event_type = models.CharField(max_length=10, choices=EVENT_TYPE_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='upcoming')
    image = models.ImageField(upload_to='events/', blank=True, null=True)
    organizer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='events')
    partner = models.ForeignKey(Partner, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    payment_info = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


class Seat(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    row = models.PositiveIntegerField()
    number = models.CharField(max_length=5)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"Ряд {self.row}, Место {self.number} для {self.event.name}"


class Ticket(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    seat = models.ForeignKey(Seat, on_delete=models.SET_NULL, null=True, blank=True)
    purchase_date = models.DateTimeField(auto_now_add=True)
    is_confirmed = models.BooleanField(default=False)
    # исходная цена
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    # применённая персональная скидка (если есть)
    applied_discount = models.ForeignKey(
        'BuyerDiscount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets_applied'
    )
    # цена после всех скидок
    discounted_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"Билет на {self.event.name} от {self.user.username}"

    def get_effective_price(self) -> Decimal:
        """
        Фактическая стоимость билета с учётом скидки.
        Если скидка не применялась или не задана — возвращаем price.
        """
        if self.discounted_price and self.discounted_price > Decimal('0.00'):
            return self.discounted_price
        return self.price


class BuyerDiscount(models.Model):
    buyer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='buyer_discounts')
    from_organizer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='buyer_discounts_given')
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2)
    is_applied = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Персональная скидка покупателя"
        verbose_name_plural = "Персональные скидки покупателей"

    def __str__(self):
        return f"{self.discount_rate}% от {self.from_organizer.user.username} для {self.buyer.user.username}"


class OrganizerDiscount(models.Model):
    from_organizer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='organizer_discounts_given')
    to_organizer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='organizer_discounts_received')
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        verbose_name = "Скидка между организаторами"
        verbose_name_plural = "Скидки между организаторами"

    def __str__(self):
        return f"{self.discount_rate}% от {self.from_organizer.user.username} для {self.to_organizer.user.username}"


class Merch(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price_in_points = models.PositiveIntegerField()
    image = models.ImageField(upload_to='merch/', blank=True, null=True)

    def __str__(self):
        return self.name


class MerchPurchase(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='merch_purchases')
    merch = models.ForeignKey(Merch, on_delete=models.CASCADE)
    purchase_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} приобрёл {self.merch.name} {self.purchase_date}"


class Comment(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField()
    rating = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Комментарий от {self.user.username} к {self.event.name}"


class MailingTopic(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class MailingMessage(models.Model):
    subject = models.CharField(
        max_length=200,
        default=generate_unique_subject
    )
    topic = models.ForeignKey(
        MailingTopic,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Краткое описание (анонс)"
    )
    text = models.TextField(verbose_name="Текст сообщения")
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Сообщение по теме '{self.topic.name}' от {self.sent_at}"


class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    topic = models.ForeignKey(MailingTopic, on_delete=models.CASCADE, related_name='subscriptions')
    subscribed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'topic')

    def __str__(self):
        return f"{self.user.username} подписан на {self.topic.name}"


class EmailLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_logs')
    message_text = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Email sent to {self.user.username} at {self.sent_at}"


class ChatMessage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages', verbose_name="Пользователь")
    content = models.TextField(verbose_name="Содержимое сообщения")
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies', verbose_name="Ответ на сообщение")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата отправки")

    class Meta:
        ordering = ['created_at']
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"

    def __str__(self):
        return f"{self.user.username}: {self.content[:30]}"

    def get_like_count(self):
        return self.reactions.filter(reaction_type='like').count()

    def get_dislike_count(self):
        return self.reactions.filter(reaction_type='dislike').count()

    @property
    def like_reactors(self):
        return [reaction.user.username for reaction in self.reactions.filter(reaction_type='like')]

    @property
    def dislike_reactors(self):
        return [reaction.user.username for reaction in self.reactions.filter(reaction_type='dislike')]


class ChatReaction(models.Model):
    REACTION_CHOICES = [
        ('like', 'Лайк'),
        ('dislike', 'Дизлайк'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_reactions', verbose_name="Пользователь")
    message = models.ForeignKey(ChatMessage, on_delete=models.CASCADE, related_name='reactions', verbose_name="Сообщение")
    reaction_type = models.CharField(max_length=7, choices=REACTION_CHOICES, verbose_name="Тип реакции")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата реакции")

    class Meta:
        unique_together = ('user', 'message')
        verbose_name = "Реакция"
        verbose_name_plural = "Реакции"

    def __str__(self):
        return f"{self.user.username} -> {self.message.id} ({self.reaction_type})"


class Order(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    profit = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"Order #{self.pk} — {self.created_at:%Y-%m-%d}"
