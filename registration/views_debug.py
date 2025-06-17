from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import User, BusinessProfile
from django.shortcuts import render, redirect
from django.contrib import messages

@login_required
def check_user_type(request):
    """
    Debug view to check user permissions and business profile status
    """
    user = request.user
    
    try:
        # Check for business profile
        if user.user_type == 'BUSINESS':
            try:
                business_profile = BusinessProfile.objects.get(user=user)
                business_info = {
                    'exists': True,
                    'business_name': business_profile.business_name,
                    'business_type': business_profile.business_type,
                    'is_active': getattr(business_profile, 'is_active', True)  # Default to True if field doesn't exist
                }
            except BusinessProfile.DoesNotExist:
                business_info = {'exists': False}
        else:
            business_info = {'exists': False}
            
        data = {
            'success': True,
            'user_info': {
                'username': user.username,
                'user_type': user.user_type,
                'is_authenticated': user.is_authenticated,
                'phoneNumber': user.phoneNumber,
                'email': user.email,
                'is_active': user.is_active,
            },
            'business_info': business_info
        }
        
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def fix_user_permissions(request):
    """
    Fix user permissions by setting user_type to BUSINESS
    and creating a business profile if needed
    """
    user = request.user
    
    # Update user type to BUSINESS
    user.user_type = 'BUSINESS'
    user.save()
    
    # Check if business profile exists, create if not
    try:
        business_profile = BusinessProfile.objects.get(user=user)
        messages.success(request, "User type updated to BUSINESS. Business profile already exists.")
    except BusinessProfile.DoesNotExist:
        # Create minimal business profile
        business_profile = BusinessProfile.objects.create(
            user=user,
            business_name=f"{user.firstName}'s Business",
            business_address="Default Address",
            business_type="retailer"
        )
        messages.success(request, "User type updated to BUSINESS and created default business profile.")
    
    return redirect('registration:business_dashboard')
