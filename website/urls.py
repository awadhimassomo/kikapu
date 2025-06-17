from django.urls import path
from . import views

app_name = 'website'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/waitlist-signup/', views.waitlist_signup, name='waitlist_signup'),
    path('vendor/signup/', views.vendor_signup, name='vendor_signup'),
    path('our_mission/', views.our_mission, name='our_mission'),
    path('about_us/', views.about_us, name='about_us'),
    path('careers/', views.careers, name='careers'),
    path('press/', views.press, name='press'),
    path('privacy_policy/', views.privacy_policy, name='privacy_policy'),
    path('impact/', views.impact, name='impact'),
    path('become-supplier/', views.become_supplier, name='become_supplier'),
    path('about/', views.about, name='about'),
    path('how_it_works/', views.how_it_works, name='how_it_works'),
    path('blog/', views.blog, name='blog'),
    path('contact/', views.contact, name='contact'),
    path('local_marketplace/', views.local_marketplace, name='local_marketplace'),
    path('earn_credits/', views.earn_credits, name='earn_credits'),
    path('nutrition_guides/', views.nutrition_guides, name='nutrition_guides'),
    path('community_events/', views.community_events, name='community_events'),
    path('terms/', views.terms, name='terms'),
    path('faq/', views.faq, name='faq'),
    path('cookie-policy/', views.cookie_policy, name='cookies'),
    path('refund-policy/', views.refund_policy, name='refund'),
]