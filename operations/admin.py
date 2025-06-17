
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from registration.models import User, BusinessProfile, CustomerProfile, DeliveryAgent, AdminUser, AgentProfile, LoyaltyCard, CardTransaction, OTPCredit, AgentRecommendation, BenefitedPhoneNumber, CreditEvent
from marketplace.models import Product, Category, Order, OrderItem, RelatedProduct
from market_research.models import Commodity, Market, MarketPriceResearch, UnsyncedData, SyncLog
from credits.models import NFCCard, CreditTransaction, VendorProfile, Product as CreditsProduct, RecyclingDeposit, Order as CreditsOrder, TransactionLog, CreditScore, CardApplication, HolidayDiscountCampaign
from .admin_sites import OperationsDashboardAdminSite
from .models import CTAFormSubmission
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Custom admin site instance
admin_site = OperationsDashboardAdminSite(name='operations_admin')

# Create the same inlines as in the original admin
class BusinessProfileInline(admin.StackedInline):
    model = BusinessProfile
    can_delete = False
    verbose_name_plural = 'Business Profile'

class CustomerProfileInline(admin.StackedInline):
    model = CustomerProfile
    can_delete = False
    verbose_name_plural = 'Customer Profile'

class AgentProfileInline(admin.StackedInline):
    model = AgentProfile
    can_delete = False
    verbose_name_plural = 'Agent Profile'

class UserAdmin(BaseUserAdmin):
    list_display = ('firstName', 'lastName', 'user_type', 'phoneNumber', 'is_active', 'is_verified', 'is_staff')
    list_filter = ('user_type', 'is_active', 'is_staff', 'is_superuser')
    actions = ['activate_users', 'deactivate_users', 'verify_users', 'unverify_users']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('firstName', 'lastName', 'phoneNumber', 'profile_image')}),
        ('Permissions', {
            'fields': ('user_type', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'phoneNumber', 'user_type', 'password1', 'password2'),
        }),
    )
    search_fields = ('email', 'firstName', 'lastName', 'phoneNumber')
    ordering = ('phoneNumber',)
    inlines = []
    
    def get_inlines(self, request, obj=None):
        if obj and obj.user_type == 'BUSINESS':
            return [BusinessProfileInline]
        elif obj and obj.user_type == 'CUSTOMER':
            return [CustomerProfileInline]
        elif obj and obj.user_type == 'AGENT':
            return [AgentProfileInline]
        return []
    def is_verified(self, obj):
        """Check if the user is verified based on their user type"""
        if obj.user_type == 'BUSINESS':
            try:
                return obj.business_profile.is_verified
            except BusinessProfile.DoesNotExist:
                return False
        elif obj.user_type == 'AGENT':
            try:
                return hasattr(obj, 'delivery_agent') and obj.delivery_agent.is_verified
            except DeliveryAgent.DoesNotExist:
                return False
        # For CUSTOMER and ADMIN user types, they don't have a verification field
        # so we'll just check if they're active
        return obj.is_active
    
    # Make the is_verified field boolean for nice icons in admin
    is_verified.boolean = True
    is_verified.short_description = "Verified"
    
    def activate_users(self, request, queryset):
        """Activate selected users"""
        updated = 0
        for user in queryset:
            user.is_active = True
            user.save()
            updated += 1
            
            # If this is an agent, also set their agent account to active
            if user.user_type == 'AGENT':
                try:
                    agent = DeliveryAgent.objects.get(user=user)
                    agent.is_active = True
                    agent.save()
                except DeliveryAgent.DoesNotExist:
                    pass
                    
        self.message_user(request, f"{updated} users have been activated.")
    activate_users.short_description = "Activate selected users"
    
    def deactivate_users(self, request, queryset):
        """Deactivate selected users"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} users have been deactivated.")
    deactivate_users.short_description = "Deactivate selected users"
    
    def verify_users(self, request, queryset):
        """Mark selected users as verified based on user type"""
        count = 0
        for user in queryset:
            if user.user_type == 'BUSINESS':
                try:
                    profile = BusinessProfile.objects.get(user=user)
                    profile.is_verified = True
                    profile.save()
                    count += 1            
                except BusinessProfile.DoesNotExist:
                    pass
            elif user.user_type == 'AGENT':
                try:
                    agent = DeliveryAgent.objects.get(user=user)
                    agent.is_verified = True
                    agent.is_active = True  # Also set is_active to True
                    agent.save()
                    
                    # Make sure the user is active too
                    if not user.is_active:
                        user.is_active = True
                        user.save()
                    count += 1
                except DeliveryAgent.DoesNotExist:
                    pass
            # For CUSTOMER and ADMIN, just activate them
            else:
                user.is_active = True
                user.save()
                count += 1
        
        self.message_user(request, f"{count} users have been verified.")
    verify_users.short_description = "Verify selected users"
    
    def unverify_users(self, request, queryset):
        """Mark selected users as unverified based on user type"""
        count = 0
        for user in queryset:
            if user.user_type == 'BUSINESS':
                try:
                    profile = BusinessProfile.objects.get(user=user)
                    profile.is_verified = False
                    profile.save()
                    count += 1
                except BusinessProfile.DoesNotExist:
                    pass
            elif user.user_type == 'AGENT':
                try:
                    agent = DeliveryAgent.objects.get(user=user)
                    agent.is_verified = False
                    agent.save()
                    count += 1
                except DeliveryAgent.DoesNotExist:
                    pass
        
        self.message_user(request, f"{count} users have been unverified.")
    unverify_users.short_description = "Unverify selected users"

# Register the models with our custom admin site
admin_site.register(User, UserAdmin)
admin_site.register(BusinessProfile)
admin_site.register(CustomerProfile)
admin_site.register(DeliveryAgent)
admin_site.register(AdminUser)
admin_site.register(LoyaltyCard)
admin_site.register(CardTransaction)
admin_site.register(OTPCredit)
admin_site.register(AgentRecommendation)
admin_site.register(BenefitedPhoneNumber)
admin_site.register(CreditEvent)

@admin.register(CTAFormSubmission, site=admin_site)
class CTAFormSubmissionAdmin(admin.ModelAdmin):
    list_display = ('form_type', 'name', 'email', 'organization', 'submitted_at', 'is_processed')
    list_filter = ('form_type', 'is_processed', 'submitted_at')
    search_fields = ('name', 'email', 'organization', 'company', 'message')
    list_select_related = ('processed_by',)
    readonly_fields = ('submitted_at',)
    date_hierarchy = 'submitted_at'
    actions = ['mark_as_processed']
    
    fieldsets = (
        ('Submission Details', {
            'fields': ('form_type', 'submitted_at', 'is_processed', 'processed_at', 'processed_by', 'notes')
        }),
        ('Contact Information', {
            'fields': ('name', 'email', 'organization', 'company')
        }),
        ('Message', {
            'fields': ('message',),
            'classes': ('collapse',)
        }),
    )
    
    def mark_as_processed(self, request, queryset):
        updated = queryset.update(
            is_processed=True,
            processed_at=timezone.now(),
            processed_by=request.user
        )
        self.message_user(request, f"Marked {updated} submissions as processed.")
    mark_as_processed.short_description = "Mark selected submissions as processed"

# Register marketplace models
admin_site.register(Product)
admin_site.register(Category)
admin_site.register(Order)
admin_site.register(OrderItem)
admin_site.register(RelatedProduct)

# Register market research models
admin_site.register(Commodity)
admin_site.register(Market)
admin_site.register(MarketPriceResearch)
admin_site.register(UnsyncedData)
admin_site.register(SyncLog)

# Register credits models
admin_site.register(NFCCard)
admin_site.register(CreditTransaction)
admin_site.register(VendorProfile)
admin_site.register(CreditsProduct, name="Credits Product")
admin_site.register(RecyclingDeposit)
admin_site.register(CreditsOrder, name="Credits Order")
admin_site.register(TransactionLog)
admin_site.register(CreditScore)
admin_site.register(CardApplication)
admin_site.register(HolidayDiscountCampaign)

logger.info("Initialized custom admin site with redirects to operations dashboard")
