from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views_redirect import redirect_agent_register

# Define app name for namespace resolution
app_name = 'registration'

# Create a router for API endpoints
router = DefaultRouter()
router.register(r'delivery-agents', views.DeliveryAgentViewSet, basename='delivery-agent')

# Consolidating all URL patterns into a single list for better Swagger compatibility
urlpatterns = [
    # Web UI URLs
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_redirect_view, name='profile'),
    path('customer-register/', views.CustomerRegistrationView.as_view(), name='customer_register'),
    path('business-register/', views.BusinessRegistrationView.as_view(), name='business_register'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('resend-otp/', views.resend_otp_view, name='resend_otp'),
    path('customer-dashboard/', views.CustomerDashboardView.as_view(), name='customer_dashboard'),
    path('business-dashboard/', views.BusinessDashboardView.as_view(), name='business_dashboard'),
    
    # Loyalty Card URLs
    path('loyalty/cards/', views.LoyaltyCardListView.as_view(), name='loyalty_card_list'),
    path('loyalty/card/<int:pk>/', views.LoyaltyCardDetailView.as_view(), name='loyalty_card_detail'),
    path('loyalty/card/create/<int:customer_id>/', views.LoyaltyCardCreateView.as_view(), name='loyalty_card_create'),
    path('loyalty/card/update/<int:pk>/', views.LoyaltyCardUpdateView.as_view(), name='loyalty_card_update'),
    path('loyalty/transaction/add/<int:card_id>/', views.add_transaction, name='add_transaction'),
    path('loyalty/dashboard/', views.CustomerLoyaltyDashboardView.as_view(), name='loyalty_dashboard'),
    
    # Mobile API
    path('mobile/register/', views.MobileRegistrationAPIView.as_view(), name='mobile_register'),
    path('mobile/scan-nfc/', views.NFCTagScanAPIView.as_view(), name='scan_nfc'),
    
    # Testing Views (only visible in development)
    path('test-sms/', views.test_sms_delivery, name='test_sms'),
    
    # API URLs - now directly included in main urlpatterns
    path('api/', include(router.urls)),
    path('api/login/', views.LoginView.as_view(), name='api_login'),
    path('api/register/', views.register_customer, name='api_register'),
    path('api/profile/', views.user_profile, name='api_profile'),
    path('api/update-pin/', views.update_pin, name='api_update_pin'),
    
    # OTP Verification API endpoints
    path('api/verify-otp/', views.VerifyOTPView.as_view(), name='api_verify_otp'),
    path('api/resend-otp/', views.ResendOTPView.as_view(), name='api_resend_otp'),
    
    # Agent API endpoints
    path('api/agent/login/', views.agent_api_login, name='agent_api_login'),
    path('api/agent/register/', redirect_agent_register, name='api_agent_register'),
]
