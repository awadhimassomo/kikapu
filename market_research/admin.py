from django.contrib import admin
from django.utils.html import format_html
from .models import Commodity, Market, MarketPriceResearch, UnsyncedData, SyncLog

@admin.register(Commodity)
class CommodityAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'default_unit')
    list_filter = ('category',)
    search_fields = ('name', 'description')

@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'region', 'is_active')
    list_filter = ('region', 'is_active')
    search_fields = ('name', 'location')

@admin.register(MarketPriceResearch)
class MarketPriceResearchAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'source_name', 'price', 'unit', 'date_observed', 'get_agent_details')
    list_filter = ('source_type', 'unit', 'region', 'agent__user_type')
    search_fields = ('product_name', 'source_name', 'agent__username', 'agent__email', 'agent__phoneNumber')
    date_hierarchy = 'date_observed'
    raw_id_fields = ('agent',)
    
    def get_queryset(self, request):
        """Override to prefetch agent data"""
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('agent', 'agent__agent_profile')
        return queryset
    
    def get_agent_details(self, obj):
        if obj.agent:
            try:
                agent_profile = obj.agent.agent_profile
                return format_html(
                    '<strong>{}</strong> ({})<br/>ID: {}<br/>Region: {}',
                    obj.agent.get_full_name(),
                    obj.agent.phoneNumber,
                    agent_profile.agent_id,
                    agent_profile.region or 'N/A'
                )
            except:
                return f"{obj.agent.get_full_name()} ({obj.agent.phoneNumber})"
        return "No agent assigned"
    
    get_agent_details.short_description = 'Agent'
    get_agent_details.admin_order_field = 'agent__username'

# Admin interfaces for sync models
@admin.register(UnsyncedData)
class UnsyncedDataAdmin(admin.ModelAdmin):
    list_display = ('id', 'data_type', 'sync_status', 'timestamp', 'retry_count', 'get_agent_details')
    list_filter = ('data_type', 'sync_status', 'retry_count', 'agent__user_type')
    search_fields = ('id', 'device_id', 'error_message', 'agent__username', 'agent__email', 'agent__phoneNumber')
    date_hierarchy = 'timestamp'
    readonly_fields = ('id', 'timestamp', 'retry_count', 'get_agent_details')
    raw_id_fields = ('agent',)
    
    def get_queryset(self, request):
        """Override to prefetch agent data"""
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('agent', 'agent__agent_profile')
        return queryset
    
    def get_agent_details(self, obj):
        if obj.agent:
            try:
                agent_profile = obj.agent.agent_profile
                return format_html(
                    '<strong>{}</strong> ({})<br/>ID: {}<br/>Region: {}',
                    obj.agent.get_full_name(),
                    obj.agent.phoneNumber,
                    agent_profile.agent_id,
                    agent_profile.region or 'N/A'
                )
            except:
                return f"{obj.agent.get_full_name()} ({obj.agent.phoneNumber})"
        return "No agent assigned"
    
    get_agent_details.short_description = 'Agent'
    get_agent_details.admin_order_field = 'agent__username'
    get_agent_details.allow_tags = True
    
    def has_add_permission(self, request):
        # Prevent manual creation of sync records
        return False
    
    actions = ['mark_as_pending']
    
    def mark_as_pending(self, request, queryset):
        """Admin action to reset failed syncs to pending status"""
        updated = queryset.update(
            sync_status='PENDING',
            retry_count=0,
            error_message=None
        )
        self.message_user(request, f"{updated} records reset to pending status.")
    
    mark_as_pending.short_description = "Reset failed syncs to pending status"

@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_data_type', 'status', 'sync_time', 'get_agent')
    list_filter = ('status', 'sync_time', 'data__agent__user_type')
    search_fields = ('id', 'data__id', 'data__agent__username', 'data__agent__phoneNumber')
    date_hierarchy = 'sync_time'
    readonly_fields = ('id', 'sync_time')
    
    def get_data_type(self, obj):
        return obj.data.data_type
    
    get_data_type.short_description = 'Data Type'
    get_data_type.admin_order_field = 'data__data_type'
    
    def get_agent(self, obj):
        if obj.data.agent:
            try:
                agent_profile = obj.data.agent.agent_profile
                return format_html(
                    '<strong>{}</strong><br/>ID: {}',
                    obj.data.agent.get_full_name(),
                    agent_profile.agent_id
                )
            except:
                return f"{obj.data.agent.get_full_name()}"
        return "No agent"
    
    get_agent.short_description = 'Agent'
    get_agent.admin_order_field = 'data__agent__username'
    get_agent.allow_tags = True
    
    def has_add_permission(self, request):
        # Prevent manual creation of log records
        return False
