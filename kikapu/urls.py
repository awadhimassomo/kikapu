"""kikapu URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from operations.admin import admin_site
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Configure Swagger documentation view
schema_view = get_schema_view(
    openapi.Info(
        title="Kikapu API",
        default_version='v1',
        description="API documentation for Kikapu marketplace",
        terms_of_service="https://kikapu.co.tz/terms/",
        contact=openapi.Contact(email="contact@kikapu.co.tz"),
        license=openapi.License(name="Proprietary"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),  # Changed from IsAuthenticated to AllowAny
)

# Import error handlers
handler404 = 'website.views.custom_404'
handler500 = 'website.views.custom_500'
handler403 = 'website.views.custom_403'

# Import api_root view
from api_utils import api_root
from credits.views import register_blank_card, authorize_payment
from registration.views import login_redirect
# Import operations views properly
from operations import views as operations_views
from Tradepoint import views as Tradepoint_views

urlpatterns = [
    # Custom admin site that redirects to operations dashboard
    path('admin/', admin_site.urls),
    
    # Real Django admin access (bypasses redirection)
    path('admin/real/', admin_site.real_admin, name='real_admin'),
    
    # API Documentation
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    # Add direct path to Swagger UI
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='swagger-ui'),
    
    # API Root
    path('api/', api_root, name='api-root'),    # Direct API routes for mobile apps
    path('api/agent/login/', operations_views.agent_api_login, name='agent_api_login'),
    path('api/agent/register/', include('registration.urls_apiauth')),  # New route for agent registration
    path('api/auth/', include('registration.urls_apiauth')),  # Fixed auth route to correctly include apiauth paths
    path('api/card/register/', register_blank_card, name='card_register'),  # Using register_blank_card function
    path('api/card/scan/', include('operations.urls_card_scan')),  # Card scanning endpoint
    path('api/payment/authorize/', authorize_payment, name='payment_authorize'),  # Card payment authorization endpoint
    
    # Redirect card assignment API calls to the correct endpoint
    path('api/cards/assign/', lambda request: redirect('credits:assign_card'), name='redirect_card_assign'),
    
    # Redirect for old login URL
    path('registration/login/', login_redirect, name='login_redirect'),
    
    # Apps URLs
    path('', include('website.urls')),
    path('auth/', include('registration.urls')),
    path('apiauth/', include('registration.urls_apiauth')),  # Add the new apiauth URL pattern
    path('marketplace/', include('marketplace.urls')),
    path('operations/', include('operations.urls')),
    path('credits/', include('credits.urls')),
    path('tourism/', include('tourism.urls')),
    path('tradepoint/', include('Tradepoint.urls')),
    
    # Call to Action pages
    path('action/', include('call_to_action.urls')),
    
    # Market research app
    path('api/market_research/', include('market_research.urls'))
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
