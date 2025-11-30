# main/admin.py

from django.contrib import admin
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
    LoyaltyProgram,  # Убедитесь, что модель добавлена здесь
)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_type', 'city', 'points')
    list_filter = ('user_type', 'event_type')
    search_fields = ('user__username', 'user__email', 'city')

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'organizer', 'date', 'location', 'status', 'event_type')
    list_filter = ('status', 'event_type', 'organizer')
    search_fields = ('name', 'description', 'location', 'organizer__user__username')

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('event', 'user', 'seat', 'purchase_date', 'is_confirmed')
    list_filter = ('is_confirmed', 'event')
    search_fields = ('user__username', 'event__name')

@admin.register(Merch)
class MerchAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_in_points')
    search_fields = ('name',)

@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ('event', 'row', 'number', 'is_available')
    list_filter = ('event', 'is_available')
    search_fields = ('event__name', 'row', 'number')

@admin.register(OrganizerDiscount)
class OrganizerDiscountAdmin(admin.ModelAdmin):
    list_display = ('from_organizer', 'to_organizer', 'discount_rate')
    list_filter = ('from_organizer', 'to_organizer')
    search_fields = ('from_organizer__user__username', 'to_organizer__user__username')

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('event', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'event')
    search_fields = ('user__username', 'event__name', 'text')

@admin.register(BuyerDiscount)
class BuyerDiscountAdmin(admin.ModelAdmin):
    list_display = ('buyer', 'from_organizer', 'discount_rate', 'created_at')
    list_filter = ('discount_rate', 'from_organizer')
    search_fields = ('buyer__user__username', 'from_organizer__user__username')

@admin.register(MerchPurchase)
class MerchPurchaseAdmin(admin.ModelAdmin):
    list_display = ('user', 'merch', 'purchase_date')
    list_filter = ('purchase_date', 'merch')
    search_fields = ('user__username', 'merch__name')

@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ('name', 'organizer', 'discount_rate')
    list_filter = ('organizer',)
    search_fields = ('name', 'organizer__user__username')

@admin.register(LoyaltyProgram)
class LoyaltyProgramAdmin(admin.ModelAdmin):
    list_display = ('name', 'points_per_ruble', 'active')
    list_filter = ('active',)
    search_fields = ('name',)
