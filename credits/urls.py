from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Define app name for namespace resolution
app_name = 'credits'

# Create a router for the API endpoints
router = DefaultRouter()
router.register(r'nfc-cards', views.NFCCardViewSet, basename='nfc-card')
router.register(r'transactions', views.TransactionViewSet, basename='transaction')
router.register(r'postpaid-applications', views.PostpaidApplicationViewSet, basename='postpaid-application')
router.register(r'agent-recommendations', views.AgentRecommendationViewSet, basename='agent-recommendation')
router.register(r'credit-events', views.CreditEventViewSet, basename='credit-event')

# Define all URLs in a single urlpatterns list for better Swagger compatibility
urlpatterns = [
    # Core Credit System URLs
    path('dashboard/', views.dashboard, name='dashboard'),
    path('topup/', views.topup_card, name='topup'),
    path('recycle/', views.recycle_submit, name='recycle_submit'),
    path('vendors/', views.view_vendors, name='view_vendors'),
    path('vendors/<int:vendor_id>/', views.vendor_products, name='vendor_products'),
    path('buy/<int:product_id>/', views.buy_product, name='buy_product'),
    path('credits/history/', views.credit_history, name='credit_history'),
    path('orders/history/', views.order_history, name='order_history'),
    path('recycling/history/', views.recycling_history, name='recycling_history'),
    
    # Kikapu Card System URLs
    path('card/', views.kikapu_card_home, name='kikapu_card_home'),
    path('card/eligibility/', views.check_eligibility, name='check_eligibility'),
    path('card/apply/prepaid/', views.apply_prepaid_card, name='apply_prepaid_card'),
    path('card/apply/postpaid/', views.apply_postpaid_card, name='apply_postpaid_card'),
    path('card/manage/', views.manage_card, name='manage_card'),
    path('card/application/<int:app_id>/', views.view_application, name='view_application'),
    path('card/payment/<int:app_id>/', views.confirm_card_payment, name='confirm_card_payment'),

    # API URLs
    path('api/', include(router.urls)),
    
    # Professional Card Lifecycle Management API Endpoints
    path('api/nfc_card/register/', views.register_blank_card, name='register_nfc_card'),  # Legacy endpoint updated to use register_blank_card
    
    # New professional card lifecycle endpoints
    path('api/card/register/', views.register_blank_card, name='register_blank_card'),  # Step 1: Register blank card
    path('api/card/assign/', views.register_customer_with_card, name='assign_card'),    # Step 2: Assign card to customer
    path('api/card/activate/', views.activate_card, name='activate_card'),              # Step 3: Activate card by physical tap
    path('api/card/scan/', views.scan_card, name='scan_card'),                         # Endpoint for scanning cards during payment operations
    
    # Payment endpoints
    path('api/payment/authorize/', views.authorize_payment, name='authorize_payment'),    # Endpoint to verify card password/PIN
    path('api/payment/process/', views.process_payment, name='process_payment'),        # Endpoint to process payment and update balance
]