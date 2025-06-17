from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
from .models import WaitlistEntry

# Create your views here.

def index(request):
    context = {}
    if request.user.is_authenticated:
        # Create a compatibility layer for templates that might expect first_name
        user = request.user
        context['user'] = user
        # Add these attributes dynamically to avoid database field access
        if hasattr(user, 'firstName'):
            user.first_name = user.firstName
        if hasattr(user, 'lastName'):
            user.last_name = user.lastName
    
    return render(request, 'website/index.html', context)

def vendor_signup(request):
    return render(request, 'website/vendor_signup.html')

def our_mission(request):
    return render(request, 'website/our_mission.html')

def about_us(request):
    return render(request, 'website/about_us.html')

def about(request):
    return render(request, 'website/about.html')

def careers(request):
    return render(request, 'website/career.html')


@csrf_exempt
@require_POST
def waitlist_signup(request):
    """Handle waitlist form submissions via AJAX"""
    try:
        # Parse JSON data from request body
        data = json.loads(request.body)
        name = data.get('name', '')
        email = data.get('email', '')
        phone = data.get('phone', '')
        
        # Basic validation
        if not all([name, email, phone]):
            return JsonResponse({
                'success': False,
                'message': 'All fields are required.'
            }, status=400)
        
        # Check if email already exists
        if WaitlistEntry.objects.filter(email=email).exists():
            return JsonResponse({
                'success': False,
                'message': 'You are already on our waitlist!'
            }, status=400)
        
        # Create new waitlist entry
        entry = WaitlistEntry.objects.create(
            name=name,
            email=email,
            phone=phone
        )
        
        # Email notification is handled by the signal
        
        return JsonResponse({
            'success': True,
            'message': 'Thank you for joining our waitlist!'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid data format.'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }, status=500)

def press(request):
    return render(request, 'website/press.html')

def privacy_policy(request):
    return render(request, 'website/privacy_policy.html')

def impact(request):
    return render(request, 'website/impact.html')

def become_supplier(request):
    return render(request, 'website/become_supplier.html')

def how_it_works(request):
    return render(request, 'website/how_it_works.html')

def blog(request):
    return render(request, 'website/blog.html')

def contact(request):
    return render(request, 'website/contact.html')

def local_marketplace(request):
    return render(request, 'website/local_marketplace.html')

def earn_credits(request):
    return render(request, 'website/earn_credits.html')

def nutrition_guides(request):
    return render(request, 'website/nutrition_guides.html')

def community_events(request):
    return render(request, 'website/community_events.html')

def terms(request):
    return render(request, 'website/terms.html')

def faq(request):
    return render(request, 'website/faq.html')

def cookie_policy(request):
    return render(request, 'website/cookie_policy.html')

def refund_policy(request):
    return render(request, 'website/refund_policy.html')

# Custom Error Handlers
def custom_404(request, exception):
    """
    Custom 404 (Page Not Found) error handler
    """
    return render(request, 'errors/404.html', status=404)

def custom_500(request):
    """
    Custom 500 (Server Error) error handler
    """
    return render(request, 'errors/500.html', status=500)

def custom_403(request, exception):
    """
    Custom 403 (Permission Denied) error handler
    """
    return render(request, 'errors/403.html', status=403)
