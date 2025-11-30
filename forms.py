from decimal import Decimal

from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import User

from .models import (
    Profile,
    Event,
    Merch,
    OrganizerDiscount,
    Comment,
    Partner,
    LoyaltyProgram,
    Seat,
    Ticket,
    BuyerDiscount,
    MailingTopic,
    MailingMessage,
    Subscription,
    ChatMessage,
)


class CustomUserCreationForm(UserCreationForm):
    USER_TYPE_CHOICES = [
        ('buyer', 'Покупатель'),
        ('organizer', 'Организатор'),
    ]

    username = forms.CharField(label='Имя пользователя', max_length=150)
    email = forms.EmailField(label='Электронная почта', required=True)
    password1 = forms.CharField(label='Пароль', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Подтверждение пароля', widget=forms.PasswordInput)
    user_type = forms.ChoiceField(choices=USER_TYPE_CHOICES, label='Тип пользователя', required=True)
    event_type = forms.ChoiceField(choices=Profile.EVENT_TYPE_CHOICES, required=False, label='Тип мероприятий')
    city = forms.CharField(label='Город', required=False)
    address = forms.CharField(label='Адрес', max_length=255, required=False)
    discount_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        min_value=0,
        max_value=100,
        label='Скидка (%)',
        initial=Decimal('0.00')
    )

    class Meta:
        model = User
        fields = (
            'username',
            'email',
            'password1',
            'password2',
            'user_type',
            'event_type',
            'city',
            'address',
            'discount_rate',
        )

    def clean(self):
        cleaned_data = super().clean()
        user_type = cleaned_data.get('user_type')
        event_type = cleaned_data.get('event_type')
        discount_rate = cleaned_data.get('discount_rate')

        if user_type == 'organizer':
            if not event_type:
                self.add_error('event_type', 'Организатор должен выбрать тип (sport/culture).')
            if discount_rate is None:
                self.add_error('discount_rate', 'Организатор должен указать скидку (хотя бы 0).')
        else:
            if discount_rate and discount_rate != 0:
                self.add_error('discount_rate', 'Только организатор может иметь скидку.')
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            profile = user.profile
            profile.user_type = self.cleaned_data.get('user_type')
            profile.city = self.cleaned_data.get('city') or ''
            profile.address = self.cleaned_data.get('address') or ''
            if profile.user_type == 'organizer':
                profile.event_type = self.cleaned_data.get('event_type')
                profile.discount_rate = self.cleaned_data.get('discount_rate') or Decimal('0.00')
            else:
                profile.event_type = None
                profile.discount_rate = None
            profile.save()
        return user


class EventForm(forms.ModelForm):
    organizer_discount = forms.ModelChoiceField(
        queryset=OrganizerDiscount.objects.none(),
        required=False,
        label='Скидка от организатора'
    )

    class Meta:
        model = Event
        fields = [
            'name',
            'description',
            'date',
            'location',
            'ticket_price',
            'ticket_quantity',
            'event_type',
            'status',
            'image',
            'partner',
            'discount',
            'payment_info',
            'organizer_discount',
        ]
        labels = {
            'name': 'Название мероприятия',
            'description': 'Описание',
            'date': 'Дата и время',
            'location': 'Место проведения',
            'ticket_price': 'Цена билета (руб.)',
            'ticket_quantity': 'Количество билетов',
            'event_type': 'Тип мероприятия',
            'status': 'Статус',
            'image': 'Изображение мероприятия',
            'partner': 'Партнёр',
            'discount': 'Скидка (%)',
            'payment_info': 'Информация об оплате',
            'organizer_discount': 'Выберите скидку от организатора',
        }
        widgets = {
            'date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        organizer = kwargs.pop('organizer', None)
        super().__init__(*args, **kwargs)
        if organizer:
            self.fields['organizer_discount'].queryset = OrganizerDiscount.objects.filter(from_organizer=organizer)


class MerchForm(forms.ModelForm):
    class Meta:
        model = Merch
        fields = ['name', 'description', 'price_in_points', 'image']
        labels = {
            'name': 'Название товара',
            'description': 'Описание',
            'price_in_points': 'Цена в баллах',
            'image': 'Изображение товара',
        }


class PartnerForm(forms.ModelForm):
    class Meta:
        model = Partner
        fields = ['name', 'website', 'discount_rate', 'organizer']
        labels = {
            'name': 'Название партнёра',
            'website': 'Сайт (URL)',
            'discount_rate': 'Скидка от партнёра (%)',
            'organizer': 'Организатор (владелец)'
        }


class OrganizerDiscountForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        organizer = kwargs.pop('organizer', None)
        super().__init__(*args, **kwargs)
        if organizer:
            if organizer.event_type == 'sport':
                self.fields['to_organizer'].queryset = Profile.objects.filter(
                    user_type='organizer', event_type='culture'
                ).exclude(id=organizer.id)
            elif organizer.event_type == 'culture':
                self.fields['to_organizer'].queryset = Profile.objects.filter(
                    user_type='organizer', event_type='sport'
                ).exclude(id=organizer.id)

    class Meta:
        model = OrganizerDiscount
        fields = ['to_organizer', 'discount_rate']
        labels = {
            'to_organizer': 'Другой организатор',
            'discount_rate': 'Скидка (%)',
        }


class CommentForm(forms.ModelForm):
    rating = forms.ChoiceField(
        choices=[(i, str(i)) for i in range(1, 6)],
        label='Оценка (1-5)',
        widget=forms.RadioSelect
    )

    class Meta:
        model = Comment
        fields = ['text', 'rating']
        labels = {
            'text': 'Комментарий',
            'rating': 'Оценка',
        }


class UserEditForm(UserChangeForm):
    password = None

    class Meta:
        model = User
        fields = ['username', 'email']


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['city', 'address', 'event_type']

    def __init__(self, *args, **kwargs):
        is_organizer = kwargs.pop('is_organizer', False)
        super().__init__(*args, **kwargs)
        if not is_organizer:
            self.fields.pop('event_type', None)


class TicketPurchaseForm(forms.Form):
    seat = forms.ModelChoiceField(
        queryset=Seat.objects.none(),
        widget=forms.RadioSelect,
        required=True,
        label='Выберите место'
    )

    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)
        super().__init__(*args, **kwargs)
        if event:
            self.fields['seat'].queryset = Seat.objects.filter(event=event, is_available=True)


class ApplyDiscountForm(forms.Form):
    discount_id = forms.ModelChoiceField(
        queryset=BuyerDiscount.objects.none(),
        label='Выберите скидку',
        widget=forms.RadioSelect,
        required=True
    )

    def __init__(self, *args, **kwargs):
        buyer = kwargs.pop('buyer', None)
        event_type = kwargs.pop('event_type', None)
        super().__init__(*args, **kwargs)
        if buyer and event_type:
            if event_type == 'culture':
                self.fields['discount_id'].queryset = BuyerDiscount.objects.filter(
                    buyer=buyer, is_applied=False, from_organizer__event_type='sport'
                )
            elif event_type == 'sport':
                self.fields['discount_id'].queryset = BuyerDiscount.objects.filter(
                    buyer=buyer, is_applied=False, from_organizer__event_type='culture'
                )


class MailingTopicForm(forms.ModelForm):
    class Meta:
        model = MailingTopic
        fields = ['name', 'description']
        labels = {
            'name': 'Название темы',
            'description': 'Описание темы (необязательно)',
        }


class MailingMessageForm(forms.ModelForm):
    class Meta:
        model  = MailingMessage
        fields = ['topic', 'description', 'text']
        labels = {
            'topic':       'Выберите тему рассылки',
            'description': 'Краткое описание (анонс)',
            'text':        'Текст сообщения',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'text':        forms.Textarea(attrs={'rows': 5}),
        }

class FeedbackForm(forms.Form):
    subject = forms.CharField(label='Тема', max_length=200)
    message = forms.CharField(label='Сообщение', widget=forms.Textarea)


class ChatMessageForm(forms.ModelForm):
    class Meta:
        model = ChatMessage
        fields = ['content', 'parent']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Введите ваше сообщение...'
            }),
            'parent': forms.HiddenInput(),
        }
        labels = {
            'content': '',
        }
