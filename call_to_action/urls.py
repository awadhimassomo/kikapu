from django.urls import path
from . import views

app_name = 'call_to_action'

urlpatterns = [
    path('schedule-pitch/', views.schedule_pitch, name='schedule_pitch'),
    path('request-investor-pack/', views.request_investor_pack, name='request_investor_pack'),
    path('request-partnership/', views.request_partnership, name='request_partnership'),
    path('explore-development-partnerships/', views.explore_development, name='explore_development'),
]
