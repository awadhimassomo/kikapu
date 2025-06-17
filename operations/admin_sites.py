from django.contrib.admin import AdminSite
from django.urls import reverse
from django.shortcuts import redirect
from django.http import HttpResponseRedirect
from django.contrib import messages
import logging

# Set up logging
logger = logging.getLogger(__name__)

def is_staff_or_superuser(user):
    """Check if user is staff or superuser"""
    return user.is_staff or user.is_superuser

class OperationsDashboardAdminSite(AdminSite):
    """
    Custom admin site that redirects authenticated users to the operations dashboard
    """
    site_header = 'Kikapu Administration'
    site_title = 'Kikapu Admin'
    index_title = 'Kikapu Administration'
    
    def real_admin(self, request):
        """
        Method to bypass redirection and show the actual Django admin panel
        """
        # Skip redirections when a special parameter is present
        request.session['show_real_admin'] = True
        return super().index(request)

    def login(self, request, extra_context=None):
        """
        Handle admin login but keep the standard login form
        """
        # Check if we should bypass the redirection and show the actual admin
        if request.GET.get('bypass_redirect') == 'true':
            # Use the default login view without redirects
            return super().login(request, extra_context)
            
        # If the user is already authenticated, redirect them
        if request.user.is_authenticated:
            if is_staff_or_superuser(request.user):
                logger.info(f"User {request.user} is already authenticated, redirecting to operations dashboard")
                return HttpResponseRedirect(reverse('operations:dashboard'))
            else:
                messages.warning(request, "You don't have permission to access the admin site.")
                return HttpResponseRedirect(reverse('website:index'))
        
        # Use the default login view
        response = super().login(request, extra_context)
        
        # If the user is authenticated after login, redirect to the operations dashboard
        if request.method == 'POST' and request.user.is_authenticated:
            if is_staff_or_superuser(request.user):
                logger.info(f"User {request.user} just logged in, redirecting to operations dashboard")
                return HttpResponseRedirect(reverse('operations:dashboard'))
            else:
                messages.warning(request, "You don't have permission to access the admin site.")
                return HttpResponseRedirect(reverse('website:index'))
        
        return response   
    
    def index(self, request, extra_context=None):
        """
        If user is already authenticated when visiting admin index, redirect to operations dashboard
        unless bypass parameter is present
        """
        # Check if we should bypass the redirection and show the actual admin
        if request.GET.get('bypass_redirect') == 'true':
            # Show the actual admin interface
            return super().index(request, extra_context)
            
        if request.user.is_authenticated:
            if is_staff_or_superuser(request.user):
                logger.info(f"User {request.user} visited admin index, redirecting to operations dashboard")
                return HttpResponseRedirect(reverse('operations:dashboard'))
            else:
                messages.warning(request, "You don't have permission to access the admin site.")
                return HttpResponseRedirect(reverse('website:index'))
        return super().index(request, extra_context)
        
    def app_index(self, request, app_label, extra_context=None):
        """
        Override the app index view to redirect authenticated users
        """
        if request.user.is_authenticated:
            if is_staff_or_superuser(request.user):
                logger.info(f"User {request.user} visited app index for {app_label}, redirecting to operations dashboard")
                return HttpResponseRedirect(reverse('operations:dashboard'))
            else:
                messages.warning(request, "You don't have permission to access the admin site.")
                return HttpResponseRedirect(reverse('website:index'))
        return super().app_index(request, app_label, extra_context)
