from django.urls import path
from . import views
from . import tourism_views

app_name = 'marketplace'

urlpatterns = [
    # Main marketplace pages
    path('', views.marketplace, name='marketplace'),
    
    # Tourism integration
    path('tourism/', tourism_views.marketplace_tourism_experiences, name='tourism_experiences'),
    path('tourism/<int:pk>/', tourism_views.marketplace_experience_detail, name='tourism_experience_detail'),
    path('tourism/add-to-cart/<int:pk>/', tourism_views.add_experience_to_cart, name='add_experience_to_cart'),
    path('tourism/remove-from-cart/<str:booking_id>/', tourism_views.remove_experience_from_cart, name='remove_experience_from_cart'),
    
    # Cart operations
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),
    path('cart/debug/', views.debug_cart, name='debug_cart'),
    path('cart/deep-clean/', views.deep_clean_cart, name='deep_clean_cart'),
    path('cart/monitor-creation/', views.monitor_cart_creation, name='monitor_cart_creation'),
    
    # Checkout process
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/place-order/', views.place_order, name='place_order'),
    path('order-success/<int:order_id>/', views.order_success, name='order_success'),
    path('order-success/', views.order_success_redirect, name='order_success_redirect'),
    
    # Order history
    path('orders/', views.order_history, name='order_history'),
    
    # Group delivery
    path('group/create/', views.create_group_view, name='create_group'),
    path('group/<str:code>/', views.group_detail_view, name='group_detail'),
    path('group/<str:code>/join/', views.join_group_view, name='join_group'),
    path('group/<str:code>/add-member/', views.add_member_to_group_view, name='add_member_to_group'),
    path('group/<str:code>/close/', views.close_group_view, name='close_group'),
    path('group/<str:group_code>/order/<int:order_id>/add-products/', views.add_products_to_member_order_view, name='add_products_to_member_order'),
    path('group/<str:group_code>/order/<int:order_id>/remove/', views.remove_group_order_view, name='remove_group_order'),
    path('groups/', views.my_groups_view, name='my_groups'),
    
    # Business product management
    path('business/products/', views.business_product_list, name='business_product_list'),
    path('business/products/add/', views.business_product_add, name='business_product_add'),
    
    # Categories
    path('categories/add/', views.category_add, name='category_add'),
    
    # Related products management
    path('manage-related-products/', views.manage_related_products, name='manage_related_products'),
    
    # API Endpoints
    path('api/products/<int:product_id>/', views.product_detail_api, name='product_detail_api'),
    path('api/cart-summary/', views.api_cart_summary, name='api_cart_summary'),
    path('api/refresh-cart-summary/', views.refresh_cart_summary, name='refresh_cart_summary'),
    path('refresh-order-summary/', views.refresh_order_summary, name='refresh_order_summary'),
    path('cart/count/', views.cart_count, name='cart_count'),
]