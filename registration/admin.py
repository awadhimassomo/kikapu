from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, BusinessProfile, CustomerProfile, LoyaltyCard, CardTransaction, OTPCredit, DeliveryAgent, AdminUser, AgentProfile, AgentRecommendation, BenefitedPhoneNumber, CreditEvent

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
        updated = queryset.update(is_active=True)
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
                    agent.save()
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

admin.site.register(User, UserAdmin)
admin.site.register(BusinessProfile)
admin.site.register(CustomerProfile)

@admin.register(LoyaltyCard)
class LoyaltyCardAdmin(admin.ModelAdmin):
    list_display = ('card_number', 'get_customer_name', 'tier', 'status', 'issue_date', 'expiry_date')
    list_filter = ('tier', 'status', 'issue_date')
    search_fields = ('card_number', 'nfc_tag_id', 'customer__user__phoneNumber')
    date_hierarchy = 'issue_date'
    
    def get_customer_name(self, obj):
        user = obj.customer.user
        return f"{user.firstName} {user.lastName} ({user.phoneNumber})"
    
    get_customer_name.short_description = 'Customer'

@admin.register(CardTransaction)
class CardTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_customer_name', 'transaction_type', 'points', 'transaction_date')
    list_filter = ('transaction_type', 'transaction_date')
    search_fields = ('loyalty_card__card_number', 'loyalty_card__customer__user__phoneNumber')
    date_hierarchy = 'transaction_date'
    
    def get_customer_name(self, obj):
        user = obj.loyalty_card.customer.user
        return f"{user.firstName} {user.lastName} ({user.phoneNumber})"
    
    get_customer_name.short_description = 'Customer'

@admin.register(OTPCredit)
class OTPCreditAdmin(admin.ModelAdmin):
    list_display = ('otp', 'user', 'business', 'otp_timestamp', 'otp_expiry')
    list_filter = ('otp_timestamp',)
    search_fields = ('otp', 'user__phoneNumber', 'business__business_name')

@admin.register(BenefitedPhoneNumber)
class BenefitedPhoneNumberAdmin(admin.ModelAdmin):
    list_display = ('phoneNumber', 'benefited_timestamp')
    search_fields = ('phoneNumber',)

@admin.register(DeliveryAgent)
class DeliveryAgentAdmin(admin.ModelAdmin):
    list_display = ('agent_id', 'get_agent_name', 'phoneNumber', 'assigned_area', 'is_active', 'is_verified', 'total_recommendations', 'successful_recommendations')
    list_filter = ('is_active', 'is_verified', 'join_date')
    search_fields = ('agent_id', 'user__firstName', 'user__lastName', 'phoneNumber')
    
    def get_agent_name(self, obj):
        return f"{obj.user.firstName} {obj.user.lastName}"
    
    get_agent_name.short_description = 'Agent Name'

@admin.register(AdminUser)
class AdminUserAdmin(admin.ModelAdmin):
    list_display = ('admin_id', 'get_admin_name', 'department', 'access_level', 'is_active')
    list_filter = ('department', 'access_level', 'is_active')
    search_fields = ('admin_id', 'user__firstName', 'user__lastName', 'user__email')
    
    def get_admin_name(self, obj):
        return f"{obj.user.firstName} {obj.user.lastName}"
    
    get_admin_name.short_description = 'Admin Name'

@admin.register(AgentProfile)
class AgentProfileAdmin(admin.ModelAdmin):
    list_display = ('agent_id', 'get_agent_name', 'region', 'total_submissions', 'approved_submissions', 'submission_quality_score', 'is_active')
    list_filter = ('is_active', 'region', 'date_joined')
    search_fields = ('agent_id', 'user__firstName', 'user__lastName', 'user__phoneNumber')
    readonly_fields = ('total_submissions', 'approved_submissions', 'rejected_submissions', 'submission_quality_score')
    
    def get_agent_name(self, obj):
        return f"{obj.user.firstName} {obj.user.lastName} ({obj.user.phoneNumber})"
    
    get_agent_name.short_description = 'Agent Name'
    
@admin.register(AgentRecommendation)
class AgentRecommendationAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_agent_name', 'get_customer_name', 'recommendation_date', 'status')
    list_filter = ('status', 'recommendation_date', 'processed_date')
    search_fields = ('agent__agent_id', 'customer__firstName', 'customer__lastName', 'customer__phoneNumber')
    date_hierarchy = 'recommendation_date'
    
    def get_agent_name(self, obj):
        return f"{obj.agent.user.firstName} {obj.agent.user.lastName} ({obj.agent.agent_id})"
    
    def get_customer_name(self, obj):
        return f"{obj.customer.firstName} {obj.customer.lastName} ({obj.customer.phoneNumber})"
    
    get_agent_name.short_description = 'Agent'
    get_customer_name.short_description = 'Customer'

@admin.register(CreditEvent)
class CreditEventAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_customer_name', 'event_type', 'points_change', 'timestamp')
    list_filter = ('event_type', 'timestamp')
    search_fields = ('customer__firstName', 'customer__lastName', 'customer__phoneNumber')
    date_hierarchy = 'timestamp'
    
    def get_customer_name(self, obj):
        return f"{obj.customer.firstName} {obj.customer.lastName} ({obj.customer.phoneNumber})"
    
    get_customer_name.short_description = 'Customer'
