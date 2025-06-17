from django.contrib import admin
from django.utils.html import format_html
from .models import (
    NFCCard, 
    CreditTransaction, 
    VendorProfile, 
    Product, 
    RecyclingDeposit, 
    Order, 
    TransactionLog,
    CreditScore,
    CardApplication,
    HolidayDiscountCampaign
)

@admin.register(NFCCard)
class NFCCardAdmin(admin.ModelAdmin):
    list_display = ('card_number', 'user', 'card_type', 'balance', 'credit_limit', 'is_active', 'card_status')
    list_filter = ('card_type', 'is_active', 'annual_fee_paid')
    search_fields = ('card_number', 'user__email', 'user__firstName', 'user__lastName')
    readonly_fields = ('card_number', 'issued_at')
    fieldsets = (
        ('Card Information', {
            'fields': ('user', 'card_number', 'card_type', 'is_active', 'issued_at', 'expire_date')
        }),
        ('Balance & Credit', {
            'fields': ('balance', 'credit_limit')
        }),
        ('Postpaid Options', {
            'fields': ('annual_fee_paid', 'last_annual_fee_date'),
            'classes': ('collapse',),
            'description': 'Only applicable for Postpaid cards'
        })
    )
    
    def card_status(self, obj):
        if not obj.is_active:
            return format_html('<span style="color: red;">Inactive</span>')
        if obj.is_expired():
            return format_html('<span style="color: orange;">Expired</span>')
        if obj.card_type == 'POSTPAID' and obj.is_annual_fee_due():
            return format_html('<span style="color: #FFA500;">Fee Due</span>')
        return format_html('<span style="color: green;">Active</span>')
    
    card_status.short_description = 'Status'

@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    list_display = ('card', 'amount', 'type', 'timestamp')
    list_filter = ('type', 'timestamp')
    search_fields = ('card__card_number', 'description')
    date_hierarchy = 'timestamp'

@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'user', 'location', 'vendor_type')
    list_filter = ('vendor_type',)
    search_fields = ('business_name', 'location')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'vendor', 'price', 'stock', 'is_active')
    list_filter = ('is_active', 'vendor')
    search_fields = ('name', 'vendor__business_name')

@admin.register(RecyclingDeposit)
class RecyclingDepositAdmin(admin.ModelAdmin):
    list_display = ('user', 'material_type', 'weight_grams', 'credits_earned', 'created_at')
    list_filter = ('material_type', 'created_at')
    search_fields = ('user__email',)
    date_hierarchy = 'created_at'
    readonly_fields = ('credits_earned',)  # Auto-calculated field

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'buyer', 'product', 'quantity', 'total_price', 'paid_with_credits', 'created_at')
    list_filter = ('paid_with_credits', 'created_at')
    search_fields = ('buyer__email', 'product__name')
    date_hierarchy = 'created_at'

@admin.register(TransactionLog)
class TransactionLogAdmin(admin.ModelAdmin):
    list_display = ('actor', 'action', 'amount', 'result', 'timestamp')
    list_filter = ('action', 'result', 'timestamp')
    search_fields = ('actor__email',)
    date_hierarchy = 'timestamp'


@admin.register(CreditScore)
class CreditScoreAdmin(admin.ModelAdmin):
    list_display = ('user', 'score', 'score_category', 'last_updated')
    list_filter = ('last_updated',)
    search_fields = ('user__email', 'user__firstName', 'user__lastName')
    readonly_fields = ('last_updated',)
    
    def score_category(self, obj):
        category = obj.get_score_category()
        color = {
            'Excellent': 'green',
            'Good': '#4CAF50',
            'Fair': '#FFC107',
            'Poor': '#FF9800',
            'Very Poor': 'red'
        }.get(category, 'black')
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, category)
    
    score_category.short_description = 'Category'


@admin.register(CardApplication)
class CardApplicationAdmin(admin.ModelAdmin):
    list_display = ('user', 'card_type', 'application_date', 'status', 'initial_deposit', 'payment_confirmed')
    list_filter = ('status', 'card_type', 'application_date', 'payment_confirmed')
    search_fields = ('user__email', 'user__firstName', 'user__lastName')
    readonly_fields = ('application_date',)
    actions = ['approve_selected', 'reject_selected']
    
    def approve_selected(self, request, queryset):
        for application in queryset.filter(status='PENDING', payment_confirmed=True):
            # Default credit limit for postpaid is 25,000 TSh
            credit_limit = 25000 if application.card_type == 'POSTPAID' else 0
            application.approve(request.user, credit_limit)
        self.message_user(request, f"{queryset.count()} application(s) approved successfully.")
    
    approve_selected.short_description = "Approve selected applications"
    
    def reject_selected(self, request, queryset):
        for application in queryset.filter(status='PENDING'):
            application.reject(request.user, "Rejected by administrator.")
        self.message_user(request, f"{queryset.count()} application(s) rejected.")
    
    reject_selected.short_description = "Reject selected applications"


@admin.register(HolidayDiscountCampaign)
class HolidayDiscountCampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'discount_percentage', 'start_date', 'end_date', 'is_active', 'campaign_status')
    list_filter = ('is_active', 'start_date', 'end_date')
    search_fields = ('name', 'description')
    
    def campaign_status(self, obj):
        if not obj.is_active:
            return format_html('<span style="color: gray;">Inactive</span>')
        
        if obj.is_campaign_active():
            return format_html('<span style="color: green;">Running</span>')
        
        from datetime import date
        today = date.today()
        
        if today < obj.start_date:
            return format_html('<span style="color: blue;">Upcoming</span>')
        else:
            return format_html('<span style="color: red;">Ended</span>')
    
    campaign_status.short_description = 'Status'
