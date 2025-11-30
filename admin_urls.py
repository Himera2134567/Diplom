from django.urls import path
from . import admin_views

urlpatterns = [
    path('', admin_views.admin_home, name='custom_admin_home'),
    # Пользователи
    path('users/', admin_views.user_list, name='custom_admin_user_list'),
    path('users/<int:pk>/edit/', admin_views.user_edit, name='custom_admin_user_edit'),
    path('users/<int:pk>/delete/', admin_views.user_delete, name='custom_admin_user_delete'),
    # Мероприятия
    path('events/', admin_views.event_list, name='custom_admin_event_list'),
    path('events/create/', admin_views.event_create, name='custom_admin_event_create'),
    path('events/<int:pk>/edit/', admin_views.event_edit, name='custom_admin_event_edit'),
    path('events/<int:pk>/delete/', admin_views.event_delete, name='custom_admin_event_delete'),
    # Товары (Merch)
    path('merch/', admin_views.merch_list, name='custom_admin_merch_list'),
    path('merch/create/', admin_views.merch_create, name='custom_admin_merch_create'),
    path('merch/<int:pk>/', admin_views.merch_detail, name='custom_admin_merch_detail'),
    path('merch/<int:pk>/edit/', admin_views.merch_edit, name='custom_admin_merch_edit'),
    path('merch/<int:pk>/delete/', admin_views.merch_delete, name='custom_admin_merch_delete'),
    # Билеты
    path('tickets/', admin_views.ticket_list, name='custom_admin_ticket_list'),
    path('tickets/<int:pk>/confirm/', admin_views.ticket_confirm, name='custom_admin_ticket_confirm'),
    # Партнёры
    path('partners/', admin_views.partner_list, name='custom_admin_partner_list'),
    path('partners/create/', admin_views.partner_create, name='custom_admin_partner_create'),
    path('partners/<int:pk>/', admin_views.partner_detail, name='custom_admin_partner_detail'),
    path('partners/<int:pk>/edit/', admin_views.partner_edit, name='custom_admin_partner_edit'),
    path('partners/<int:pk>/delete/', admin_views.partner_delete, name='custom_admin_partner_delete'),
    # Рассылки
    path('mailing/dashboard/', admin_views.admin_mailing_dashboard, name='admin_mailing_dashboard'),
    path('mailing/create_topic/', admin_views.admin_create_mailing_topic, name='admin_create_mailing_topic'),
    path('mailing/create_message/', admin_views.admin_create_mailing_message, name='admin_create_mailing_message'),
    path('mailing/stats/', admin_views.admin_mailing_stats, name='admin_mailing_stats'),
    # В конце списка urlpatterns
    path('statistics/', admin_views.statistics, name='admin_statistics'),


]
