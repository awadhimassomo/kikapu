from django.urls import path
from . import views

app_name = 'tradepoint'

urlpatterns = [
    path('', views.index, name='index'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('listing/<int:listing_id>/', views.listing_detail, name='listing_detail'),
    path('create/', views.create_listing, name='create_listing'),
    path('update/<int:listing_id>/', views.update_listing, name='update_listing'),
    path('delete/<int:listing_id>/', views.delete_listing, name='delete_listing'),
    path('delete-image/<int:image_id>/', views.delete_image, name='delete_image'),
    path('show-interest/<int:listing_id>/', views.show_interest, name='show_interest'),
    path('mark-as-contacted/<int:interest_id>/', views.mark_as_contacted, name='mark_as_contacted'),
    path('report/<int:listing_id>/', views.report_listing, name='report_listing'),
]
