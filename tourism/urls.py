from django.urls import path
from . import views

app_name = 'tourism'

urlpatterns = [
    path('', views.farm_experiences, name='experience_list'),
    path('<int:pk>/', views.experience_detail, name='experience_detail'),
    
    # New unified booking routes
    path('book/<int:pk>/', views.book_experience, name='book_experience'),
    path('booking-confirmation/<int:booking_id>/', views.booking_confirmation, name='booking_confirmation'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    
    # Legacy routes for compatibility
    path('book-farmhouse/', views.book_farmhouse, name='book_farmhouse'),
    path('book-farmhouse/<int:pk>/', views.book_farmhouse, name='book_farmhouse_with_id'),
    path('book-restaurant/', views.book_restaurant, name='book_restaurant'),
    path('book-restaurant/<int:pk>/', views.book_restaurant, name='book_restaurant_with_id'),
]