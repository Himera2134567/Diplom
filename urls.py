from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from main import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', include('django.contrib.auth.urls')),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/<int:pk>/', views.profile, name='profile'),
    path('feedback/', views.feedback, name='feedback'),
    path('create_event/', views.create_event, name='create_event'),
    path('events/', views.event_list, name='event_list'),
    path('events/<int:pk>/', views.event_detail, name='event_detail'),
    path('events/<int:pk>/edit/', views.edit_event, name='edit_event'),
    path('events/<int:pk>/delete/', views.delete_event, name='delete_event'),
    path('events/<int:event_id>/select_seat/', views.select_seat, name='select_seat'),
    path('ticket_success/', views.ticket_success, name='ticket_success'),
    path('ticket/apply_discount/<int:ticket_id>/', views.apply_discount_to_ticket, name='apply_discount_to_ticket'),
    path('merch/', views.MerchListView.as_view(), name='merch_list'),
    path('merch/<int:pk>/', views.MerchDetailView.as_view(), name='merch_detail'),
    path('merch/<int:pk>/purchase/', views.purchase_merch, name='purchase_merch'),
    path('organizers/', views.organizer_list, name='organizer_list'),
    path('organizer/<int:pk>/', views.organizer_detail, name='organizer_detail'),
    path('organizer/buyers/', views.organizer_buyers_list, name='organizer_buyers_list'),
    path('organizer/confirm_purchase/<int:ticket_id>/', views.confirm_ticket_purchase, name='confirm_ticket_purchase'),
    path('events/<int:event_id>/comment/add/', views.add_comment, name='add_comment'),
    path('privacy_policy/', views.privacy_policy, name='privacy_policy'),
    path('terms_of_service/', views.terms_of_service, name='terms_of_service'),
    path('platform/', views.platform_info, name='platform_info'),
    # PDF-отчеты
    path('pdf/user_orders/<int:user_id>/', views.pdf_user_orders, name='pdf_user_orders'),
    path('pdf/pricelist/sport/', views.pdf_pricelist_sport, name='pdf_pricelist_sport'),
    path('pdf/pricelist/culture/', views.pdf_pricelist_culture, name='pdf_pricelist_culture'),
    path('pdf/revenue_report/', views.pdf_revenue_report, name='pdf_revenue_report'),
    # Отчеты Google Charts
    path('charts/', views.charts, name='charts'),
    # Групповой чат
    path('chat/', views.chat, name='chat'),
    path('chat/api/', views.chat_api, name='chat_api'),
    path('chat/reply/<int:parent_id>/', views.chat_reply, name='chat_reply'),
    path('chat/message/<int:message_id>/delete/', views.delete_chat_message, name='delete_chat_message'),
    path('chat/reaction/<int:message_id>/<str:reaction_type>/', views.chat_reaction, name='chat_reaction'),
    # Подписки
    path('subscribe/<int:topic_id>/', views.subscribe_topic, name='subscribe_topic'),
    path('unsubscribe/<int:topic_id>/', views.unsubscribe_topic, name='unsubscribe_topic'),
    # В конце списка urlpatterns
    path('mailing/messages/', views.view_mailing_messages, name='view_mailing_messages'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
  + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
