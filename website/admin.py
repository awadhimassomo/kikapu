from django.contrib import admin
from .models import WaitlistEntry

# Register your models here.

@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'created_at', 'is_contacted')
    list_filter = ('is_contacted', 'created_at')
    search_fields = ('name', 'email', 'phone')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_per_page = 20
    
    actions = ['mark_as_contacted']
    
    def mark_as_contacted(self, request, queryset):
        updated = queryset.update(is_contacted=True)
        self.message_user(request, f'{updated} entries marked as contacted.')
    mark_as_contacted.short_description = "Mark selected entries as contacted"
