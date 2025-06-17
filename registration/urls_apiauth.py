from django.urls import path
from .views_redirect import redirect_agent_register
from .views import ResendOTPView, VerifyOTPView, DeliveryAgentViewSet
from operations.views import agent_api_login

urlpatterns = [
    # Root path redirector
    path('', redirect_agent_register, name='apiauth_root'),
    
    # Agent endpoints - accessible from both '/api/auth/agent/' and '/apiauth/agent/'
    path('agent/register/', DeliveryAgentViewSet.as_view({'post': 'create'}), name='apiauth_agent_register'),
    path('agent/login/', agent_api_login, name='apiauth_agent_login'),
    path('agent/verify-otp/', DeliveryAgentViewSet.as_view({'post': 'verify_otp'}), name='apiauth_agent_verify_otp'),
    path('agent/resend-otp/', DeliveryAgentViewSet.as_view({'post': 'resend_otp'}), name='apiauth_agent_resend_otp'),
    
    # OTP endpoints
    path('resend-otp/', ResendOTPView.as_view(), name='apiauth_resend_otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='apiauth_verify_otp'),
]