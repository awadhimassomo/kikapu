from django.urls import path
from . import views

app_name = 'operations'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Related Products URLs
    path('related-products/', views.manage_related_products, name='related_products'),
    path('related-products/add/', views.add_related_product, name='add_related_product'),
    path('related-products/edit/<int:relationship_id>/', views.edit_related_product, name='edit_related_product'),
    path('related-products/delete/<int:relationship_id>/', views.delete_related_product, name='delete_related_product'),
    
    # Agent Management URLs
    path('agents/', views.manage_agents, name='manage_agents'),
    path('agents/add/', views.add_agent, name='add_agent'),
    path('agents/edit/<int:agent_id>/', views.edit_agent, name='edit_agent'),
    path('agents/details/<int:agent_id>/', views.agent_details, name='agent_details'),
    path('agents/toggle-status/<int:agent_id>/', views.toggle_agent_status, name='toggle_agent_status'),
    
    # NFC Card Management URLs
    path('nfc-cards/', views.manage_nfc_cards, name='manage_nfc_cards'),
    path('nfc-cards/force-sync-balances/', views.force_sync_all_balances, name='force_sync_all_balances'),
    
    # API Endpoints
    path('api/customers/', views.get_customers, name='get_customers'),
    path('api/customers/search/', views.search_customer, name='search_customer'),
    path('api/cards/<str:card_id>/', views.get_card_details, name='get_card_details'),
    
    # Debug catch-all route - this should be last
    path('api/<path:path>', views.debug_api_request, name='debug_api_request'),
]