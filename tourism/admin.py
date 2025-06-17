from django.contrib import admin
from .models import FarmExperience, Booking

@admin.register(FarmExperience)
class FarmExperienceAdmin(admin.ModelAdmin):
    list_display = ('title', 'experience_type', 'available', 'location')
    list_filter = ('experience_type', 'available')
    search_fields = ('title', 'location')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_number', 'experience', 'user', 'start_date', 'end_date', 'party_size', 'status', 'total_price')
    list_filter = ('status', 'experience__experience_type')
    search_fields = ('booking_number', 'user__email', 'user__firstName', 'user__lastName')
    readonly_fields = ('booking_number', 'created_at')
