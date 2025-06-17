from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.decorators import api_view, schema
from rest_framework import permissions
from . import views
from . import views_sync  # Import the sync views
from . import views_debug  # Import the debug views
from . import views_debug_permissions  # Import the permissions debug views
from . import api_views  # Import the API views

# Configure router with explicit descriptions
router = DefaultRouter()
router.register(r'sources', views.SourceViewSet, basename='source')
router.register(r'markets', views.MarketViewSet, basename='market')
router.register(r'commodities', views.CommodityViewSet, basename='commodity')

app_name = 'market_research'

urlpatterns = [
    # API endpoints - removing nested 'api/' prefix to avoid double nesting
    path('', include(router.urls)),
    
    # Source registration endpoints
    path('register-source/', views.SourceCreateAPIView.as_view(), name='register_source'),
    path('register-market/', views.MarketCreateAPIView.as_view(), name='register_market'),
    
    # Mobile app API endpoints
    path('price/submit/', views.submit_market_price, name='submit_market_price'),
    path('mobile/markets/', views.mobile_market_list, name='mobile_market_list'),
    path('mobile/commodities/', views.mobile_commodity_list, name='mobile_commodity_list'),
    path('mobile/recent-prices/', views.mobile_recent_prices, name='mobile_recent_prices'),
    
    # Data retrieval API endpoints
    path('comparison_data/', views.get_comparison_data, name='get_comparison_data'),
    path('regional_profit_data/', views.get_regional_profit_data, name='get_regional_profit_data'),
    path('seasonal_data/', views.get_seasonal_data, name='get_seasonal_data'),
    
    # Dashboard views
    path('dashboard/', views.market_research_dashboard, name='market_research_dashboard'),
    path('map/', views.market_map_view, name='market_map_view'),  # New map view URL
    path('add_commodity/', views.add_commodity, name='add_commodity'),
    path('api/add-commodity/', api_views.add_commodity_api, name='add_commodity_api'),  # AJAX API endpoint
    path('api/delete-commodity/<int:commodity_id>/', api_views.delete_commodity_api, name='delete_commodity_api'),  # AJAX API endpoint for deletion
    path('delete_commodity/<int:commodity_id>/', views.delete_commodity, name='delete_commodity'),
    path('submit_price_data/', views.submit_price_data, name='submit_price_data'),
    
    # Sync endpoints for offline data collection
    path('sync/', views_sync.sync_data, name='sync_data'),
    path('sync/resolve/', views_sync.resolve_conflict, name='resolve_conflict'),
    path('sync/pending/', views_sync.get_pending_syncs, name='get_pending_syncs'),
    
    # Debug endpoints
    path('debug/auth-test/', views_debug.auth_test_endpoint, name='auth_test_endpoint'),
    path('debug/check-permissions/', views_debug_permissions.check_agent_permissions, name='check_agent_permissions'),
    path('debug/permissions/', views_debug_permissions.permission_debug_view, name='permission_debug_view'),
]