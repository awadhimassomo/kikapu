from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import json

from .email_utils import send_cta_email, send_auto_reply_email

# Create your views here.
def schedule_pitch(request):
    """View for scheduling a pitch meeting with the team"""
    context = {
        'page_title': 'Schedule Pitch Meeting',
        'meta_description': 'Schedule a meeting to pitch your ideas and explore collaboration opportunities with the Kikapu team.',
    }
    
    if request.method == 'POST':
        try:
            # Get form data
            name = request.POST.get('name', '').strip()
            email = request.POST.get('email', '').strip()
            company = request.POST.get('company', '').strip()
            message = request.POST.get('message', '').strip()
            
            # Basic validation
            if not all([name, email, company, message]):
                return JsonResponse({'success': False, 'error': 'All fields are required'}, status=400)
            
            # Prepare email content
            subject = f'New Pitch Meeting Request from {name}'
            
            context = {
                'name': name,
                'email': email,
                'company': company,
                'message': message,
                'form_type': 'Pitch Meeting'
            }
            
            html_message = render_to_string('call_to_action/email/cta_notification.html', context)
            
            # Send admin notification
            send_cta_email(subject, html_message)
            
            # Send auto-reply to submitter
            auto_reply_context = {
                'name': name,
                'email': email,
                'company': company,
                'message': message,
                'form_type': 'Pitch Meeting Request'
            }
            send_auto_reply_email(email, auto_reply_context)
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return render(request, 'call_to_action/schedule_pitch.html', context)

def request_investor_pack(request):
    """View for requesting investment information pack"""
    context = {
        'page_title': 'Request Investor Pack',
        'meta_description': 'Request our comprehensive investor pack including business plan, financial projections, and market analysis.',
    }
    
    if request.method == 'POST':
        try:
            # Get form data
            name = request.POST.get('name', '').strip()
            email = request.POST.get('email', '').strip()
            organization = request.POST.get('organization', '').strip()
            
            # Basic validation
            if not all([name, email, organization]):
                return JsonResponse({'success': False, 'error': 'All fields are required'}, status=400)
            
            # Prepare email content
            subject = f'New Investor Pack Request from {name}'
            
            context = {
                'name': name,
                'email': email,
                'organization': organization,
                'form_type': 'Investor Pack Request'
            }
            
            html_message = render_to_string('call_to_action/email/cta_notification.html', context)
            
            # Send admin notification
            send_cta_email(subject, html_message)
            
            # Send auto-reply to submitter
            auto_reply_context = {
                'name': name,
                'email': email,
                'organization': organization,
                'form_type': 'Investor Pack Request'
            }
            send_auto_reply_email(email, auto_reply_context)
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return render(request, 'call_to_action/request_investor_pack.html', context)

def request_partnership(request):
    """View for requesting partnership proposal"""
    context = {
        'page_title': 'Request Partnership Proposal',
        'meta_description': 'Request a customized partnership proposal for your organization to collaborate with Kikapu.',
    }
    
    if request.method == 'POST':
        try:
            # Get form data
            name = request.POST.get('name', '').strip()
            email = request.POST.get('email', '').strip()
            organization = request.POST.get('organization', '').strip()
            message = request.POST.get('message', '').strip()
            
            # Basic validation
            if not all([name, email, organization, message]):
                return JsonResponse({'success': False, 'error': 'All fields are required'}, status=400)
            
            # Prepare email content
            subject = f'New Partnership Request from {organization}'
            
            context = {
                'name': name,
                'email': email,
                'organization': organization,
                'message': message,
                'form_type': 'Partnership Request'
            }
            
            html_message = render_to_string('call_to_action/email/cta_notification.html', context)
            
            # Send admin notification
            send_cta_email(subject, html_message)
            
            # Send auto-reply to submitter
            auto_reply_context = {
                'name': name,
                'email': email,
                'organization': organization,
                'message': message,
                'form_type': 'Partnership Request'
            }
            send_auto_reply_email(email, auto_reply_context)
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return render(request, 'call_to_action/request_partnership.html', context)

def explore_development(request):
    """View for exploring development partnerships"""
    context = {
        'page_title': 'Explore Development Partnerships',
        'meta_description': 'Explore technical development partnership opportunities with Kikapu technology and innovation team.',
    }
    
    if request.method == 'POST':
        try:
            # Get form data
            name = request.POST.get('name', '').strip()
            email = request.POST.get('email', '').strip()
            organization = request.POST.get('organization', '').strip()
            message = request.POST.get('message', '').strip()
            
            # Basic validation
            if not all([name, email, organization, message]):
                return JsonResponse({'success': False, 'error': 'All fields are required'}, status=400)
            
            # Prepare email content
            subject = f'New Development Partnership Inquiry from {organization}'
            
            context = {
                'name': name,
                'email': email,
                'organization': organization,
                'message': message,
                'form_type': 'Development Partnership Inquiry'
            }
            
            html_message = render_to_string('call_to_action/email/cta_notification.html', context)
            
            # Send admin notification
            send_cta_email(subject, html_message)
            
            # Send auto-reply to submitter
            auto_reply_context = {
                'name': name,
                'email': email,
                'organization': organization,
                'message': message,
                'form_type': 'Development Partnership Inquiry'
            }
            send_auto_reply_email(email, auto_reply_context)
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return render(request, 'call_to_action/explore_development.html', context)
