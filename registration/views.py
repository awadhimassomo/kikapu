from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.views.generic import CreateView, UpdateView, TemplateView, ListView, DetailView
from django.views import View
from django.urls import reverse_lazy, reverse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
import json
import logging
import random
import string
import uuid
import requests
from datetime import datetime, timedelta
from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.core.exceptions import ValidationError
from django.utils.crypto import get_random_string
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import DeliveryAgent, AgentRecommendation, User, OTPCredit, BenefitedPhoneNumber
from credits.serializers import AgentRecommendationSerializer, CustomerSerializer

@csrf_exempt
def agent_login_view(request):
    """
    Custom login view for delivery agents with CSRF exemption to fix login issues
    """
    if request.user.is_authenticated:
        # Check if the user is a delivery agent
        try:
            agent = DeliveryAgent.objects.get(user=request.user)
            if agent.is_active:
                # User is already logged in as an active agent, redirect to agent dashboard
                return redirect('operations:agent_dashboard')
            else:
                messages.warning(request, "Your agent account is inactive. Please contact an administrator.")
                logout(request)
        except DeliveryAgent.DoesNotExist:
            # User is logged in but not as an agent, log them out for security
            messages.warning(request, "You are not registered as a delivery agent.")
            logout(request)
    
    if request.method == 'POST':
        phoneNumber = request.POST.get('phoneNumber')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me') == 'on'
        
        # Authenticate user
        user = authenticate(request, username=phoneNumber, password=password)
        
        if user is not None:
            # Check if user is a delivery agent
            try:
                agent = DeliveryAgent.objects.get(user=user)
                if agent.is_active:
                    # Log the user in
                    login(request, user)
                    
                    # Set session expiry based on remember_me
                    if remember_me:
                        # Set session to expire in 30 days (2592000 seconds)
                        request.session.set_expiry(2592000)
                    else:
                        # Default session expiry (browser close)
                        request.session.set_expiry(0)
                    
                    # Update last_active timestamp
                    agent.last_active = timezone.now()
                    agent.save(update_fields=['last_active'])
                    
                    messages.success(request, f"Welcome, {user.get_full_name()}!")
                    return redirect('operations:agent_dashboard')
                else:
                    messages.error(request, "Your agent account is inactive. Please contact an administrator.")
            except DeliveryAgent.DoesNotExist:
                messages.error(request, "You are not registered as a delivery agent.")
        else:
            messages.error(request, "Invalid phone number or password.")
    
    return render(request, 'registration/agent_login.html')

# Add missing API functions that are referenced in urls.py

@api_view(['POST'])
@permission_classes([AllowAny])
def register_customer(request):
    """
    API endpoint for registering new customers
    """
    serializer = CustomerSerializer(data=request.data)
    if serializer.is_valid():
        customer = serializer.save()
        return Response({
            'id': customer.id,
            'message': 'Customer registered successfully'
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """
    API endpoint for retrieving and updating user profile
    """
    if request.method == 'GET':
        # Return user profile data
        try:
            user = request.user
            if user.user_type == 'CUSTOMER':
                profile = user.customer_profile
                data = {
                    'id': user.id,
                    'name': user.get_full_name(),
                    'phoneNumber': user.phoneNumber,
                    'email': user.email,
                    'user_type': user.user_type,
                    'joined_date': profile.joined_date,
                    'loyalty_points': getattr(profile, 'loyalty_points', 0),
                    'card_type': profile.card_type,
                }
            else:
                data = {
                    'id': user.id,
                    'name': user.get_full_name(),
                    'phoneNumber': user.phoneNumber,
                    'email': user.email,
                    'user_type': user.user_type,
                }
            return Response(data)
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    elif request.method == 'PUT':
        # Update user profile data
        try:
            user = request.user
            
            # Update basic user info
            if 'firstName' in request.data:
                user.firstName = request.data.get('firstName')
            if 'lastName' in request.data:
                user.lastName = request.data.get('lastName')
            if 'email' in request.data:
                user.email = request.data.get('email')
                
            user.save()
            
            return Response({
                'message': 'Profile updated successfully'
            })
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_pin(request):
    """
    API endpoint for updating customer PIN
    """
    current_pin = request.data.get('current_pin')
    new_pin = request.data.get('new_pin')
    
    if not current_pin or not new_pin:
        return Response({
            'error': 'Current PIN and new PIN are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate PIN format
    if not new_pin.isdigit() or len(new_pin) != 4:
        return Response({
            'error': 'PIN must be a 4-digit number'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = request.user
        profile = user.customer_profile
        
        # Verify current PIN
        pin_valid, message = profile.verify_pin(current_pin)
        if not pin_valid:
            return Response({
                'error': message
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update PIN
        profile.set_pin(new_pin)
        
        return Response({
            'message': 'PIN updated successfully'
        })
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Enhanced LoginView class with better error handling
class LoginView(APIView):
    """
    API endpoint for user login
    Returns authentication token and user info
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        phoneNumber = request.data.get('phoneNumber')
        password = request.data.get('password')
        
        # Detailed field validation
        field_errors = {}
        if not phoneNumber:
            field_errors['phoneNumber'] = ['Phone number is required']
        if not password:
            field_errors['password'] = ['Password is required']
        
        if field_errors:
            return Response({
                'success': False,
                'message': 'One or more required fields are missing',
                'field_errors': field_errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Log the login attempt (without logging the password)
        logger.info(f"API login attempt for phoneNumber: {phoneNumber}")
        
        user = authenticate(request, username=phoneNumber, password=password)
        
        if user is not None:
            # Check if user account requires OTP verification
            otp_record = OTPCredit.objects.filter(user=user, is_used=False).first()
            if otp_record:
                logger.info(f"User {phoneNumber} requires OTP verification")
                return Response({
                    'success': False,
                    'message': 'Account requires phone verification',
                    'verification_required': True,
                    'otp_sent': True
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Check if user account is active
            if not user.is_active:
                logger.warning(f"Login attempt for inactive user account: {phoneNumber}")
                return Response({
                    'success': False,
                    'message': 'Your account is not active. Please contact support.',
                    'error': 'INACTIVE_ACCOUNT'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Log successful login
            logger.info(f"API login successful for phoneNumber: {phoneNumber}, user_type: {user.user_type}")
            login(request, user)
            refresh = RefreshToken.for_user(user)
            
            # Build user data to return based on user type
            user_data = {
                'id': user.id,
                'name': user.get_full_name(),
                'phoneNumber': user.phoneNumber,
                'user_type': user.user_type,
                'email': user.email
            }
            
            # Add customer/business specific data if available
            if user.user_type == 'CUSTOMER':
                try:
                    profile = user.customer_profile
                    user_data['has_pin'] = bool(profile.pin_hash)
                except Exception as e:
                    logger.error(f"Error getting customer profile: {str(e)}")
            elif user.user_type == 'BUSINESS':
                try:
                    profile = user.business_profile
                    user_data['business_name'] = profile.business_name
                except Exception as e:
                    logger.error(f"Error getting business profile: {str(e)}")
            
            return Response({
                'success': True,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': user_data
            })
        else:
            # Check if the user exists to provide more specific error message
            try:
                existing_user = User.objects.get(phoneNumber=phoneNumber)
                logger.warning(f"API login attempt with incorrect password for phoneNumber: {phoneNumber}")
                return Response({
                    'success': False,
                    'message': 'Incorrect password for this account',
                    'field_errors': {'password': ['The password is incorrect']}
                }, status=status.HTTP_401_UNAUTHORIZED)
            except User.DoesNotExist:
                logger.warning(f"API login attempt with non-existent phoneNumber: {phoneNumber}")
                return Response({
                    'success': False,
                    'message': 'No account found with this phone number',
                    'field_errors': {'phoneNumber': ['No account exists with this phone number']}
                }, status=status.HTTP_401_UNAUTHORIZED)

# Set up logging
logger = logging.getLogger(__name__)

def generate_otp():
    """Generate a random 5-digit OTP"""
    return get_random_string(length=5, allowed_chars='0123456789')

from .models import User, BusinessProfile, CustomerProfile, LoyaltyCard, CardTransaction, OTPCredit, BenefitedPhoneNumber
from .forms import (
    UserRegistrationForm, BusinessRegistrationForm, CustomerRegistrationForm, 
    LoginForm, LoyaltyCardForm, CardTransactionForm, NFCTagReadForm, 
    CustomerMobileRegistrationForm
)


class HomeView(TemplateView):
    template_name = 'registration/home.html'

class CustomerRegistrationView(CreateView):
    model = User
    form_class = CustomerRegistrationForm
    template_name = 'registration/customer_register.html'
    success_url = reverse_lazy('registration:verify_otp')
    
    def form_valid(self, form):
        # Save the user but don't show success message yet
        response = super().form_valid(form)
        user = self.object
        # Set the backend attribute explicitly
        user.backend = 'registration.auth_backends.PhoneNumberOrEmailBackend'
        
        # Generate and send OTP
        otp_code = generate_otp()
        OTPCredit.objects.create(
            user=user,
            otp=otp_code
        )
        
        # Send SMS with OTP code
        sms_sent = send_otp_via_sms(user.phoneNumber, otp_code)
        if sms_sent:
            logger.info(f"OTP sent successfully to {user.phoneNumber}")
            messages.success(self.request, f"Verification code sent to {user.phoneNumber}. Please verify your phone number.")
        else:
            logger.warning(f"Failed to send OTP to {user.phoneNumber}.")
            messages.warning(self.request, f"We've encountered an issue sending your verification code. Please try again or contact support if the problem persists.")
        
        # Store user_id in session for OTP verification
        self.request.session['user_id_for_otp'] = user.id
        self.request.session['is_new_registration'] = True
        
        return response

class BusinessRegistrationView(CreateView):
    model = User
    form_class = BusinessRegistrationForm
    template_name = 'registration/business_register.html'
    success_url = reverse_lazy('registration:verify_otp')
    
    def form_valid(self, form):
        if form.cleaned_data.get('existing_account'):
            # Get the existing user based on phone number
            existing_phone = form.cleaned_data.get('existing_phone')
            try:
                user = User.objects.get(phoneNumber=existing_phone)
                # Update the user type
                user.user_type = 'BUSINESS'
                # Set the backend attribute
                user.backend = 'registration.auth_backends.PhoneNumberOrEmailBackend'
                user.save()
                
                # Create the business profile using the existing user
                business_profile = BusinessProfile.objects.create(
                    user=user,
                    business_name=form.cleaned_data.get('business_name'),
                    business_address=form.cleaned_data.get('business_address'),
                    business_description=form.cleaned_data.get('business_description'),
                    registration_number=form.cleaned_data.get('registration_number'),
                    business_type=form.cleaned_data.get('business_type'),
                )
                
                # Generate and send OTP
                otp_code = generate_otp()
                
                # Check if an OTP record already exists for this user
                try:
                    otp_record = OTPCredit.objects.get(user=user, business=business_profile)
                    # Update existing OTP
                    otp_record.otp = otp_code
                    otp_record.created_at = timezone.now()  # Reset expiration time
                    otp_record.is_used = False
                    otp_record.save()
                    logger.info(f"Updated existing OTP for user {user.phoneNumber}")
                except OTPCredit.DoesNotExist:
                    # Create new OTP record
                    OTPCredit.objects.create(
                        user=user,
                        otp=otp_code,
                        business=business_profile
                    )
                    logger.info(f"Created new OTP for user {user.phoneNumber}")
                
                # Don't store OTP in session for security reasons
                # self.request.session['temp_otp'] = otp_code
                
                # Try to send SMS with OTP
                sms_sent = send_otp_via_sms(user.phoneNumber, otp_code)
                if sms_sent:
                    logger.info(f"OTP sent successfully to {user.phoneNumber}")
                    messages.success(self.request, f"OTP sent to {user.phoneNumber}. Please verify your phone number.")
                else:
                    # Log the issue but still proceed (in case SMS service is down)
                    logger.warning(f"Failed to send OTP to {user.phoneNumber}.")
                    messages.warning(self.request, f"We've encountered an issue sending your verification code. Please try again or contact support if the problem persists.")
                
                # Store user_id in session for OTP verification
                self.request.session['user_id_for_otp'] = user.id
                self.request.session['is_new_registration'] = False
                self.request.session['business_name'] = business_profile.business_name
                
                return redirect('registration:verify_otp')
                
            except User.DoesNotExist:
                messages.error(self.request, "No account found with that phone number. Please check and try again.")
                return self.form_invalid(form)
        else:
            # Save form but don't send success message yet
            response = super().form_valid(form)
            user = self.object
            
            # Check if a business profile already exists for this user
            try:
                business_profile = BusinessProfile.objects.get(user=user)
                # Update existing business profile
                business_profile.business_name = form.cleaned_data.get('business_name')
                business_profile.business_address = form.cleaned_data.get('business_address')
                business_profile.business_description = form.cleaned_data.get('business_description')
                business_profile.registration_number = form.cleaned_data.get('registration_number')
                business_profile.business_type = form.cleaned_data.get('business_type')
                business_profile.business_phone = form.cleaned_data.get('business_phone')
                business_profile.business_email = form.cleaned_data.get('business_email')
                business_profile.business_hours = form.cleaned_data.get('business_hours')
                business_profile.save()
                logger.info(f"Updated existing business profile for user {user.phoneNumber}")
            except BusinessProfile.DoesNotExist:
                # Create a new business profile
                business_profile = BusinessProfile.objects.create(
                    user=user,
                    business_name=form.cleaned_data.get('business_name'),
                    business_address=form.cleaned_data.get('business_address'),
                    business_description=form.cleaned_data.get('business_description'),
                    registration_number=form.cleaned_data.get('registration_number'),
                    business_type=form.cleaned_data.get('business_type'),
                    business_phone=form.cleaned_data.get('business_phone'),
                    business_email=form.cleaned_data.get('business_email'),
                    business_hours=form.cleaned_data.get('business_hours'),
                )
                logger.info(f"Created new business profile for user {user.phoneNumber}")
            
            # Generate and send OTP
            otp_code = generate_otp()
            
            # Check if an OTP record already exists for this user
            try:
                # Make sure user is a User instance, not a string representation
                if not isinstance(user, User):
                    logger.error(f"User variable is not a User instance: {type(user)}")
                    # Try to get the actual user instance if we have a string
                    if isinstance(user, str) and '+' in user:
                        # This might be a phone number string
                        try:
                            user = User.objects.get(phoneNumber=user)
                        except User.DoesNotExist:
                            logger.error(f"Could not find user with phone number: {user}")
                            raise
                    else:
                        logger.error(f"Cannot convert user to User instance: {user}")
                        raise ValueError(f"Invalid user: {user}")
                
                otp_record = OTPCredit.objects.get(user=user, business=business_profile)
                # Update existing OTP
                otp_record.otp = otp_code
                otp_record.created_at = timezone.now()  # Reset expiration time
                otp_record.is_used = False
                otp_record.save()
                logger.info(f"Updated existing OTP for user {user.phoneNumber}")
            except OTPCredit.DoesNotExist:
                # Create new OTP record
                OTPCredit.objects.create(
                    user=user,
                    otp=otp_code,
                    business=business_profile
                )
                logger.info(f"Created new OTP for user {user.phoneNumber}")
            
            # Store OTP in session for display (for development purposes)
            self.request.session['temp_otp'] = otp_code
            
            # Try to send SMS with OTP
            sms_sent = send_otp_via_sms(user.phoneNumber, otp_code)
            if sms_sent:
                logger.info(f"OTP sent successfully to {user.phoneNumber}")
                messages.success(self.request, f"OTP sent to {user.phoneNumber}. Please verify your phone number.")
            else:
                # Log the issue but still proceed (in case SMS service is down)
                logger.warning(f"Failed to send OTP to {user.phoneNumber}. Using fallback method.")
                messages.warning(self.request, f"Could not send OTP via SMS. For testing, use: {otp_code}")
            
            # Store user_id in session for OTP verification
            self.request.session['user_id_for_otp'] = user.id 
            self.request.session['is_new_registration'] = True
            self.request.session['business_name'] = business_profile.business_name
            
            return response

def login_view(request):
    if request.user.is_authenticated:
        # User is already logged in, redirect based on user type
        if request.user.user_type == 'ADMIN':
            return redirect('admin:index')
        elif request.user.user_type == 'BUSINESS':
            return redirect('registration:business_dashboard')
        else:  # CUSTOMER
            return redirect('marketplace:marketplace')
    
    if request.method == 'POST':
        form = LoginForm(data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            
            # Auth form already authenticates the user, get user directly
            user = form.get_user()
            
            if user is not None:
                # Login with extended session duration
                login(request, user)
                
                # Set session expiry to 7 days (604800 seconds)
                request.session.set_expiry(604800)
                
                # Set location to Arusha, Tanzania
                request.session['location'] = 'Arusha, Tanzania'
                
                # Set currency to Tanzanian Shillings
                request.session['currency'] = 'TSh'
                
                # Ensure session is saved immediately
                request.session.save()
                
                # Try to migrate guest cart to user cart if needed
                try:
                    from marketplace.cart_utils import migrate_guest_cart_to_user
                    success = migrate_guest_cart_to_user(request)
                    if success:
                        messages.info(request, "Items from your previous shopping session have been added to your cart.")
                except Exception as e:
                    print(f"Error migrating cart during login: {e}")
                
                # Redirect based on user type
                if user.user_type == 'ADMIN':
                    return redirect('admin:index')
                elif user.user_type == 'BUSINESS':
                    return redirect('registration:business_dashboard')
                else:  # CUSTOMER
                    # Redirect customers directly to the marketplace
                    return redirect('marketplace:marketplace')
            else:
                # Authentication failed
                form.add_error(None, "Invalid username or password. Please try again.")
    else:
        form = LoginForm()
    
    # Include CSRF token explicitly in the context
    return render(request, 'registration/login.html', {
        'form': form,
    })

def logout_view(request):
    # Clear all session data and cookies
    response = redirect('registration:login')
    
    # Complete session cleanup
    request.session.flush()
    
    # Perform Django's standard logout process
    logout(request)
    
    # Clear any lingering cookies that might cause authentication issues
    if hasattr(request, 'COOKIES'):
        for cookie in request.COOKIES:
            if cookie.startswith('kikapu_') or cookie in ['csrftoken', 'sessionid']:
                response.delete_cookie(cookie)
    
    # Add a message indicating successful logout
    messages.success(request, "You have been successfully logged out.")
    
    return response


def login_redirect(request):
    """
    Redirects from the old login URL pattern to the new login URL
    This handles legacy URLs and maintains compatibility
    """
    # Add a message to inform users about the URL change
    messages.info(request, "You've been redirected to our new login page.")
    
    # Preserve any GET parameters in the redirect
    if request.GET:
        query_string = request.GET.urlencode()
        redirect_url = f"{reverse('registration:login')}?{query_string}"
        return redirect(redirect_url)
    
    # Standard redirect if no GET parameters
    return redirect('registration:login')

def profile_redirect_view(request):
    """Redirect users to their appropriate dashboard based on user type"""
    if not request.user.is_authenticated:
        return redirect('registration:login')
    
    if request.user.user_type == 'BUSINESS':
        return redirect('registration:business_dashboard')
    elif request.user.user_type == 'CUSTOMER':
        return redirect('registration:customer_dashboard')
    else:
        # Default fallback for admin or other user types
        return redirect('website:index')

class CustomerDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'registration/customer_dashboard.html'
    
    # ... (rest of the code remains the same)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated and self.request.user.user_type == 'CUSTOMER':
            context['profile'] = self.request.user.customer_profile
        return context
        
    def get(self, request, *args, **kwargs):
        # Check if there's a 'marketplace' parameter in the request
        if request.GET.get('marketplace') == 'true':
            # Redirect to marketplace while preserving the session
            return redirect('marketplace:marketplace')
        return super().get(request, **kwargs)

class BusinessDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'registration/business_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated and self.request.user.user_type == 'BUSINESS':
            # Add business profile to context
            business_profile = self.request.user.business_profile
            context['business'] = business_profile
            context['profile'] = business_profile  # Keep for backward compatibility
            
            # Get product count
            from django.db.models import Count, Sum
            context['product_count'] = getattr(business_profile, 'products', []).count() if hasattr(business_profile, 'products') else 0
            
            # Get orders for this business
            from marketplace.models import Order, OrderItem, BusinessNotification
            # Find order items that contain products from this business
            order_items = OrderItem.objects.filter(product__business=business_profile)
            # Get the distinct orders from these items
            order_ids = order_items.values_list('order_id', flat=True).distinct()
            orders = Order.objects.filter(id__in=order_ids).order_by('-order_date')
            
            # Add order count to context
            context['order_count'] = orders.count()
            
            # Add recent orders to context (limit to 5)
            context['recent_orders'] = orders[:5]
            
            # Get unread notifications count
            context['unread_notifications_count'] = BusinessNotification.objects.filter(
                business=business_profile,
                is_read=False
            ).count()
            
            # Get recent notifications (limit to 5)
            context['recent_notifications'] = BusinessNotification.objects.filter(
                business=business_profile
            ).order_by('-created_at')[:5]
            
            # Placeholder stats
            context['review_count'] = 0
            context['customer_count'] = orders.values('customer').distinct().count()
        return context


# Loyalty Card Management Views
class StaffOnlyMixin(UserPassesTestMixin):
    """Mixin to ensure only staff/admin users can access views"""
    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.user_type == 'ADMIN' or 
            self.request.user.user_type == 'BUSINESS'
        )


class LoyaltyCardListView(LoginRequiredMixin, ListView):
    """View for listing all loyalty cards"""
    model = LoyaltyCard
    template_name = 'registration/loyalty/card_list.html'
    context_object_name = 'cards'
    paginate_by = 10
    
    def get_queryset(self):
        # Admin users see all cards, customers only see their own
        if self.request.user.user_type == 'ADMIN':
            return LoyaltyCard.objects.all().order_by('-issue_date')
        elif self.request.user.user_type == 'CUSTOMER':
            try:
                return LoyaltyCard.objects.filter(customer=self.request.user.customer_profile)
            except CustomerProfile.DoesNotExist:
                return LoyaltyCard.objects.none()
        return LoyaltyCard.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_type'] = self.request.user.user_type
        return context


class LoyaltyCardDetailView(LoginRequiredMixin, DetailView):
    """View for displaying loyalty card details"""
    model = LoyaltyCard
    template_name = 'registration/loyalty/card_detail.html'
    context_object_name = 'card'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        card = self.get_object()
        
        # Get recent transactions
        context['transactions'] = card.transactions.order_by('-transaction_date')[:10]
        
        # Add form for adding points if user is staff
        if self.request.user.user_type in ['ADMIN', 'BUSINESS']:
            context['transaction_form'] = CardTransactionForm()
        
        return context


class LoyaltyCardCreateView(LoginRequiredMixin, StaffOnlyMixin, CreateView):
    """View for creating a new loyalty card"""
    model = LoyaltyCard
    form_class = LoyaltyCardForm
    template_name = 'registration/loyalty/card_form.html'
    success_url = reverse_lazy('registration:loyalty_card_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Generate a random card number if not provided
        form.initial['card_number'] = self.generate_card_number()
        return form
    
    def form_valid(self, form):
        customer_id = self.kwargs.get('customer_id')
        customer = get_object_or_404(CustomerProfile, id=customer_id)
        
        # Check if customer already has a card
        if hasattr(customer, 'loyalty_card'):
            messages.error(self.request, f"Customer {customer.user.email} already has a loyalty card.")
            return redirect('registration:loyalty_card_list')
        
        card = form.save(commit=False)
        card.customer = customer
        card.save()
        
        messages.success(self.request, f"Loyalty card successfully created for {customer.user.email}")
        return super().form_valid(form)
    
    def generate_card_number(self):
        """Generate a unique card number"""
        prefix = "KIK"  # Kikapu prefix
        random_digits = ''.join(random.choice(string.digits) for _ in range(8))
        card_number = f"{prefix}{random_digits}"
        
        # Ensure uniqueness
        while LoyaltyCard.objects.filter(card_number=card_number).exists():
            random_digits = ''.join(random.choice(string.digits) for _ in range(8))
            card_number = f"{prefix}{random_digits}"
        
        return card_number


class LoyaltyCardUpdateView(LoginRequiredMixin, StaffOnlyMixin, UpdateView):
    """View for updating a loyalty card"""
    model = LoyaltyCard
    form_class = LoyaltyCardForm
    template_name = 'registration/loyalty/card_form.html'
    success_url = reverse_lazy('registration:loyalty_card_list')
    
    def form_valid(self, form):
        messages.success(self.request, f"Loyalty card {form.instance.card_number} updated successfully.")
        return super().form_valid(form)


def add_transaction(request, card_id):
    """View to add a transaction to a loyalty card"""
    if not request.user.is_authenticated or request.user.user_type not in ['ADMIN', 'BUSINESS']:
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('registration:login')
    
    card = get_object_or_404(LoyaltyCard, id=card_id)
    
    if request.method == 'POST':
        form = CardTransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.loyalty_card = card
            transaction.staff_user = request.user
            transaction.save()
            
            # Update customer points based on transaction type
            if transaction.transaction_type == 'EARN' or transaction.transaction_type == 'BONUS':
                card.customer.add_points(transaction.points)
            elif transaction.transaction_type == 'REDEEM':
                if card.customer.loyalty_points >= transaction.points:
                    card.customer.use_points(transaction.points)
                else:
                    messages.error(request, "Customer doesn't have enough points.")
                    transaction.delete()
                    return redirect('registration:loyalty_card_detail', pk=card.id)
            elif transaction.transaction_type == 'ADJUSTMENT':
                # For adjustments, points can be positive or negative
                card.customer.add_points(transaction.points)
            
            # Update card tier based on new point total
            card.update_tier()
            card.use_card()
            
            messages.success(request, f"Transaction recorded successfully. Customer now has {card.customer.loyalty_points} points.")
            return redirect('registration:loyalty_card_detail', pk=card.id)
        else:
            messages.error(request, "There was an error with your submission.")
    
    return redirect('registration:loyalty_card_detail', pk=card.id)


# API endpoints for mobile app integration
@method_decorator(csrf_exempt, name='dispatch')
class MobileRegistrationAPIView(View):
    """API endpoint for mobile app customer registration"""
    def post(self, request):
        try:
            data = json.loads(request.body)
            form = CustomerMobileRegistrationForm(data)
            
            if form.is_valid():
                # Create user
                user = User.objects.create_user(
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password'],
                    firstName=form.cleaned_data['firstName'],
                    lastName=form.cleaned_data['lastName'],
                    phoneNumber=form.cleaned_data['phoneNumber'],
                    user_type='CUSTOMER'
                )
                
                # Create customer profile
                customer = CustomerProfile.objects.create(user=user)
                
                # Create loyalty card with provided NFC tag ID
                nfc_tag_id = form.cleaned_data['nfc_tag_id']
                card_number = f"KIK{''.join(random.choice(string.digits) for _ in range(8))}"
                expiry_date = datetime.date.today() + datetime.timedelta(days=730)  # 2 years
                
                card = LoyaltyCard.objects.create(
                    customer=customer,
                    card_number=card_number,
                    nfc_tag_id=nfc_tag_id,
                    expiry_date=expiry_date,
                    status='ACTIVE',
                    tier='STANDARD'
                )
                
                # Add welcome bonus points
                CardTransaction.objects.create(
                    loyalty_card=card,
                    points=100,
                    transaction_type='BONUS',
                    description='Welcome bonus'
                )
                customer.add_points(100)
                
                return JsonResponse({
                    'success': True,
                    'message': 'Registration successful',
                    'user_id': user.id,
                    'card_number': card.card_number,
                    'loyalty_points': customer.loyalty_points
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Validation error',
                    'errors': form.errors
                }, status=400)
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'An error occurred: {str(e)}'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class NFCTagScanAPIView(View):
    """API endpoint for processing NFC tag scans"""
    def post(self, request):
        try:
            data = json.loads(request.body)
            form = NFCTagReadForm(data)
            
            if form.is_valid():
                nfc_tag_id = form.cleaned_data['nfc_tag_id']
                
                try:
                    card = LoyaltyCard.objects.get(nfc_tag_id=nfc_tag_id)
                    
                    if not card.is_valid():
                        return JsonResponse({
                            'success': False,
                            'message': f'Card is not valid. Status: {card.get_status_display()}'
                        }, status=400)
                    
                    # Record card usage
                    card.use_card()
                    
                    return JsonResponse({
                        'success': True,
                        'card_number': card.card_number,
                        'customer_name': f"{card.customer.user.firstName} {card.customer.user.lastName}",
                        'loyalty_points': card.customer.loyalty_points,
                        'tier': card.get_tier_display(),
                        'status': card.get_status_display()
                    })
                
                except LoyaltyCard.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'message': 'NFC tag not registered to any card'
                    }, status=404)
            
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Validation error',
                    'errors': form.errors
                }, status=400)
        
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'An error occurred: {str(e)}'
            }, status=500)


from django.views import View
class CustomerLoyaltyDashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard view for customers to see their loyalty information"""
    template_name = 'registration/loyalty/customer_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.user.user_type != 'CUSTOMER':
            messages.error(self.request, "You don't have permission to access this page.")
            return context
        
        try:
            customer = self.request.user.customer_profile
            context['customer'] = customer
            
            try:
                card = customer.loyalty_card
                context['card'] = card
                context['transactions'] = card.transactions.order_by('-transaction_date')[:5]
            except LoyaltyCard.DoesNotExist:
                context['card'] = None
        
        except CustomerProfile.DoesNotExist:
            context['customer'] = None
        
        return context



class SendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        personal_number = request.data.get('personal_number')
        business_id = request.data.get('business_id')

        try:
            user = User.objects.get(phoneNumber=personal_number)
            business = Business.objects.get(id=business_id, owner=user)

            otp_credit, created = OTPCredit.objects.get_or_create(user=user, business=business)

            otp = generate_otp()
            otp_credit.otp = otp
            otp_credit.otp_timestamp = timezone.now()
            otp_credit.save()

            if send_otp_via_sms(personal_number, otp):
                return Response({"message": "OTP sent successfully"}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Failed to send OTP"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except User.DoesNotExist:
            return Response({"error": "Personal number not found"}, status=status.HTTP_404_NOT_FOUND)
        except Business.DoesNotExist:
            return Response({"error": "Business not found or not associated with this user"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def generate_otp():
    return str(random.randint(10000, 99999)).zfill(5)

def generate_reference():
    return str(uuid.uuid4())



class ResendOTPView(APIView):
    """API endpoint for resending One-Time Passwords (OTP)"""
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        operation_description="Resend a one-time password (OTP) to a user's phone number",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['phoneNumber'],
            properties={
                'phoneNumber': openapi.Schema(type=openapi.TYPE_STRING, description="User's phone number including country code"),
            },
        ),
        responses={
            200: openapi.Response(
                description="OTP resent successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING, description="Success message")
                    }
                )
            ),
            400: openapi.Response(description="Invalid input or OTP resent too soon"),
            404: openapi.Response(description="User or OTP record not found"),
            500: openapi.Response(description="Failed to send SMS")
        }
    )
    def post(self, request):
        logger.info("Received OTP resend request")
        logger.debug(f"Request data: {request.data}")

        serializer = ResendOTPSerializer(data=request.data)
        if serializer.is_valid():
            phoneNumber = serializer.validated_data['phoneNumber']
            logger.debug(f"Validated phone number: {phoneNumber}")

            try:
                user = User.objects.get(phoneNumber=phoneNumber)
                logger.debug(f"User found: {user}")

                try:
                    otp_credit = OTPCredit.objects.get(user=user)
                    logger.debug(f"OTP record found: {otp_credit}")

                    # Check if the resend request is too soon
                    if otp_credit.otp_timestamp and (timezone.now() - otp_credit.otp_timestamp).seconds < 60:
                        logger.warning("OTP resend requested too soon")
                        return Response({"error": "OTP resend is allowed after 60 seconds"}, status=status.HTTP_400_BAD_REQUEST)

                    # Generate a new OTP and update the expiry time
                    otp = generate_otp()
                    otp_credit.otp = otp
                    otp_credit.otp_expiry = timezone.now() + timedelta(minutes=10)  # Reset expiry time
                    otp_credit.otp_timestamp = timezone.now()
                    otp_credit.save()
                    logger.info(f"OTP updated and saved: {otp}")

                    # Send OTP via SMS
                    if send_otp_via_sms(phoneNumber, otp):
                        logger.info("OTP sent successfully via SMS")
                        return Response({"message": "OTP resent successfully"}, status=status.HTTP_200_OK)
                    else:
                        logger.error("Failed to send OTP via SMS")
                        return Response({"error": "Failed to resend OTP"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                except OTPCredit.DoesNotExist:
                    logger.error("No OTP record found for this user")
                    
                    # Create new OTP for the user
                    otp = generate_otp()
                    OTPCredit.objects.create(
                        user=user,
                        otp=otp
                    )
                    
                    # Send OTP via SMS
                    if send_otp_via_sms(user.phoneNumber, otp):
                        logger.info("New OTP created and sent successfully via SMS")
                        return Response({"message": "OTP sent successfully"}, status=status.HTTP_200_OK)
                    else:
                        logger.error("Failed to send OTP via SMS")
                        return Response({"error": "Failed to send OTP"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            except User.DoesNotExist:
                logger.error("Personal number not found")
                return Response({"error": "Personal number not found"}, status=status.HTTP_404_NOT_FOUND)
        
        logger.error(f"Serializer validation errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def send_otp_via_sms(phoneNumber, otp):
    try:
        # Format phone number - ensure it has country code
        if not phoneNumber.startswith('+'):
            phoneNumber = '+' + phoneNumber
            
        from_ = "OTP"  # Sender name
        url = 'https://messaging-service.co.tz/api/sms/v1/text/single'
        headers = {
            'Authorization': "Basic YXRoaW06TWFtYXNob2tv",
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        reference = generate_reference()  # Generate the reference
        
        # Improve message format for clarity
        payload = {
            "from": from_,
            "to": phoneNumber,
            "text": f"Your verification code is: {otp}. Do not share this code with anyone.",
            "reference": reference,
        }

        # Enhanced logging
        logger.info(f"Sending OTP to: {phoneNumber}, Reference: {reference}")
        
        response = requests.post(url, headers=headers, json=payload)
        response_data = response.json() if response.text else {}
        
        if response.status_code == 200:
            logger.info(f"OTP message sent successfully! Response: {response_data}")
            return True
        else:
            logger.error(f"Failed to send OTP message. Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        logger.exception(f'Error sending OTP: {e}')
        return False


def generate_reference():
    """Generate a unique reference for SMS tracking."""
    return f"REF-{datetime.now().strftime('%Y%m%d%H%M%S')}"


def test_sms_delivery(request):
    """View to test SMS delivery functionality - FOR DEVELOPMENT ONLY"""
    # Add a warning in the logs that this is a testing-only feature
    logger.warning("TEST SMS DELIVERY FUNCTION USED - This should be disabled in production")
    
    if request.method == 'POST':
        phoneNumber = request.POST.get('phoneNumber')
        
        if not phoneNumber:
            messages.error(request, "Please provide a phone number to test SMS delivery.")
            return render(request, 'registration/test_sms.html', {'testing_mode': True})
        
        # Format phone number to ensure proper delivery
        formatted_phone = format_phoneNumber(phoneNumber)
        if not formatted_phone:
            messages.error(request, "Invalid phone number format. Please enter a valid phone number.")
            return render(request, 'registration/test_sms.html', {'testing_mode': True})
        
        # Generate a test OTP
        test_otp = get_random_string(length=5, allowed_chars='0123456789')
        
        # Try to send the SMS
        sms_sent = send_otp_via_sms(formatted_phone, test_otp)
        
        if sms_sent:
            messages.success(request, f"Test message sent successfully to {formatted_phone}.")
            # Only in test environment show the actual OTP
            messages.info(request, f"TEST MODE ONLY: The verification code sent was {test_otp}")
        else:
            messages.error(request, f"Failed to send test message to {formatted_phone}. Please check server logs for details.")
        
        return render(request, 'registration/test_sms.html', {'testing_mode': True})
    else:
        return render(request, 'registration/test_sms.html', {'testing_mode': True})




# Get the user model
User = settings.AUTH_USER_MODEL
from django.contrib.auth import get_user_model
User = get_user_model()

# Define ResendOTP serializer
class ResendOTPSerializer(serializers.Serializer):
    phoneNumber = serializers.CharField(required=True, help_text="User's phone number with country code")

class VerifyOTPView(APIView):
    """API endpoint for verifying One-Time Passwords (OTP)"""
    permission_classes = [AllowAny]
    
    @swagger_auto_schema(
        operation_description="Verify a one-time password (OTP) sent to a user's phone number",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['phoneNumber', 'otp'],
            properties={
                'phoneNumber': openapi.Schema(type=openapi.TYPE_STRING, description="User's phone number including country code"),
                'otp': openapi.Schema(type=openapi.TYPE_STRING, description="5-digit One-Time Password"),
                'business_id': openapi.Schema(type=openapi.TYPE_INTEGER, description="Optional business ID")
            },
        ),
        responses={
            200: openapi.Response(
                description="OTP verified successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'access_token': openapi.Schema(type=openapi.TYPE_STRING),
                        'refresh_token': openapi.Schema(type=openapi.TYPE_STRING),
                        'businesses': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                        'message': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            400: openapi.Response(description="Invalid input data"),
            404: openapi.Response(description="User or OTP not found"),
            401: openapi.Response(description="OTP expired or invalid")
        }
    )
    def post(self, request):
        phoneNumber = request.data.get('phoneNumber')
        otp = request.data.get('otp')
        business_id = request.data.get('business_id')

        logger.info(f"Received OTP verification request for phone number: {phoneNumber}, OTP: {otp}, business ID: {business_id}")
        
        # Enhanced debugging
        logger.info(f"Current server time: {timezone.now()}")
        
        # Format phone number - ensure consistency
        if phoneNumber and not phoneNumber.startswith('+'):
            phoneNumber = '+' + phoneNumber
            logger.info(f"Phone number formatted to: {phoneNumber}")

        # Step 1: Authenticate the user by verifying the OTP
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(phoneNumber=phoneNumber)
            logger.info(f"User found: ID {user.id}, Name: {user.firstName} {user.lastName}")
        except User.DoesNotExist:
            logger.error(f"User with phone number {phoneNumber} does not exist.")
            return Response({"error": "User with this phone number not found"}, status=status.HTTP_404_NOT_FOUND)

        try:
            # Check if there's any OTP record for this user
            all_otps = OTPCredit.objects.filter(user=user).order_by('-otp_timestamp')
            if all_otps.exists():
                latest_otp = all_otps.first()
                logger.info(f"Latest OTP for user: {latest_otp.otp}, timestamp: {latest_otp.otp_timestamp}, expiry: {latest_otp.otp_expiry}")
                
                # Check if the entered OTP matches the latest OTP
                if latest_otp.otp != otp:
                    logger.error(f"OTP mismatch. Expected: {latest_otp.otp}, Received: {otp}")
                    return Response({"error": "Invalid OTP code"}, status=status.HTTP_400_BAD_REQUEST)
                    
                # Check if OTP has expired
                if timezone.now() > latest_otp.otp_expiry:
                    logger.error(f"OTP expired at {latest_otp.otp_expiry}. Current time: {timezone.now()}")
                    return Response({"error": "OTP has expired. Please request a new one."}, status=status.HTTP_400_BAD_REQUEST)
                
                otp_record = latest_otp
            else:
                logger.error("No OTP records found for this user")
                return Response({"error": "No verification code has been sent to this number"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error during OTP verification: {str(e)}")
            return Response({"error": f"Error during verification: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Step 2: Activate the user account
        user.is_active = True
        user.save()
        logger.info(f"User account activated for {user.phoneNumber}")
        
        # Step 3: Mark user's profile as verified if it exists
        if user.user_type == 'BUSINESS':
            try:
                business_profile = BusinessProfile.objects.get(user=user)
                business_profile.is_phone_verified = True
                business_profile.is_active = True
                business_profile.save()
                logger.info(f"Business profile activated for user {user.phoneNumber}")
            except BusinessProfile.DoesNotExist:
                logger.warning(f"Business profile not found for user {user.phoneNumber}")
                
        logger.info(f"User with phone number {phoneNumber} has been verified successfully.")

        # Step 3: Generate tokens (access and refresh)
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        logger.info(f"Generated tokens for user ID {user.id}: Access token: {access_token}, Refresh token: {refresh_token}")

        # Step 4: Return user info based on user type
        if user.user_type == 'BUSINESS':
            try:
                business_profile = BusinessProfile.objects.get(user=user)
                logger.info(f"Returning business profile for user ID {user.id}")
                return Response({
                    'access_token': access_token,
                    'refresh_token': refresh_token,
                    'business': {
                        'id': business_profile.id,
                        'name': business_profile.business_name,
                        'type': business_profile.business_type,
                        'is_verified': business_profile.is_phone_verified
                    },
                    'user': {
                        'id': user.id,
                        'name': f"{user.firstName} {user.lastName}",
                        'phoneNumber': user.phoneNumber,
                        'email': user.email
                    }
                }, status=status.HTTP_200_OK)
            except BusinessProfile.DoesNotExist:
                logger.warning(f"No business profile found for user ID {user.id}")
        
        # For customers or if business profile not found
        return Response({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': {
                'id': user.id,
                'name': f"{user.firstName} {user.lastName}",
                'phoneNumber': user.phoneNumber,
                'email': user.email,
                'user_type': user.user_type
            }
        }, status=status.HTTP_200_OK)


class PasswordResetRequestView(APIView):
    def post(self, request):
        phoneNumber = request.data.get('phoneNumber')  # Using request.data for better compatibility with DRF
        if not phoneNumber:
            return JsonResponse({'error': 'Phone number is required'}, status=400)
        
        # Check if the user with the given phone number exists
        try:
            user = User.objects.get(phoneNumber=phoneNumber)
        except User.DoesNotExist:
            return JsonResponse({'error': 'Invalid phone number'}, status=400)
        
        # Retrieve the business associated with the user
        try:
            business = Business.objects.get(owner=user)
            business_id = business.id
        except Business.DoesNotExist:
            return JsonResponse({'error': 'No business associated with this user.'}, status=400)

        # Generate OTP
        otp = generate_otp()  # Generate OTP
        
        # Store the OTP in the OTPCredit model with an expiry time
        otp_expiry = timezone.now() + timedelta(minutes=10)  # OTP valid for 10 minutes

        # Include business_id in defaults
        OTPCredit.objects.update_or_create(
            user=user, 
            defaults={'otp': otp, 'otp_expiry': otp_expiry, 'business_id': business_id}
        )
        
        # Generate the message to be sent
        message = f'Your password reset OTP is: {otp}'
        if reset_password(user.phoneNumber, message):
            return JsonResponse({'message': 'OTP sent successfully'})
        else:
            return JsonResponse({'error': 'Failed to send SMS'}, status=500)



def reset_password(phoneNumber, message):
    try:
        from_ = "OTP"  # Sender name
        url = 'https://messaging-service.co.tz/api/sms/v1/text/single'
        headers = {
            'Authorization': "Basic YXRoaW06TWFtYXNob2tv",
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        payload = {
            "from": from_,
            "to": phoneNumber,
            "text": message,  # The message parameter is used here
            "reference": generate_reference(),
        }
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 200:
            print("SMS sent successfully!")
            return True
        else:
            print("Failed to send SMS.")
            print(response.status_code)
            print(response.text)
            return False
    except Exception as e:
        print(f'Error sending SMS: {e}')
        return False

def generate_otp():
    import random
    return str(random.randint(10000, 99999))



def verify_otp_view(request):
    """View for OTP verification during registration"""
    if request.method == 'POST':
        otp_entered = request.POST.get('otp')
        user_id = request.session.get('user_id_for_otp')
        is_new_registration = request.session.get('is_new_registration', True)
        
        if not user_id or not otp_entered:
            messages.error(request, "Invalid verification attempt. Please try again.")
            return redirect('registration:login')
        
        try:
            user = User.objects.get(id=user_id)
            # Set the backend attribute explicitly
            user.backend = 'registration.auth_backends.PhoneNumberOrEmailBackend'
            otp_record = OTPCredit.objects.filter(user=user, otp=otp_entered).order_by('-otp_timestamp').first()
            
            if not otp_record:
                messages.error(request, "Invalid OTP code. Please check and try again.")
                return render(request, 'registration/verify_otp.html', {'phoneNumber': user.phoneNumber})
            
            if timezone.now() > otp_record.otp_expiry:
                messages.error(request, "OTP has expired. Please request a new one.")
                # Delete expired OTP
                otp_record.delete()
                return render(request, 'registration/verify_otp.html', {'phoneNumber': user.phoneNumber})
            
            # Add to benefited phone numbers
            BenefitedPhoneNumber.objects.get_or_create(phoneNumber=user.phoneNumber)
            
            # Activate the user account
            user.is_active = True
            user.save()
            logger.info(f"User account activated for {user.phoneNumber}")
            
            # Check if user has a business profile and activate it
            if user.user_type == 'BUSINESS':
                try:
                    business_profile = BusinessProfile.objects.get(user=user)
                    business_profile.is_phone_verified = True
                    business_profile.is_active = True  # Activate business after phone verification
                    business_profile.save()
                    logger.info(f"Business profile activated for user {user.phoneNumber}")
                except BusinessProfile.DoesNotExist:
                    logger.warning(f"Business profile not found for user {user.phoneNumber}")
            
            # OTP is valid, mark it as used
            otp_record.is_used = True
            otp_record.save()
            
            # Clear session data
            if 'user_id_for_otp' in request.session:
                del request.session['user_id_for_otp']
            if 'is_new_registration' in request.session:
                del request.session['is_new_registration']
            if 'temp_otp' in request.session:
                del request.session['temp_otp']
            if 'business_name' in request.session:
                del request.session['business_name']
            
            # Log the user in
            # Get the backend used for authentication
            backend = user.backend if hasattr(user, 'backend') else None
            # Pass the backend to the login function
            login(request, user, backend=backend)
            
            # Redirect based on user type and registration type
            if is_new_registration:
                messages.success(request, f"Your phone number has been verified. Welcome, {user.firstName}!")
            else:
                messages.success(request, f"Your phone number has been verified. Welcome back, {user.firstName}!")
                
            if user.user_type == 'BUSINESS':
                messages.success(request, "Your business account has been activated! You can now add products to your store.")
                return redirect('registration:business_dashboard')
            else:
                return redirect('registration:customer_dashboard')
                
        except User.DoesNotExist:
            messages.error(request, "User not found. Please register again.")
            return redirect('registration:customer_register')
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return render(request, 'registration/verify_otp.html', {'phoneNumber': 'your phone number'})
    else:
        # GET request - show OTP verification form
        user_id = request.session.get('user_id_for_otp')
        if not user_id:
            messages.error(request, "Invalid verification attempt. Please register first.")
            return redirect('registration:login')
            
        try:
            user = User.objects.get(id=user_id)
            return render(request, 'registration/verify_otp.html', {
                'phoneNumber': user.phoneNumber
            })
        except User.DoesNotExist:
            messages.error(request, "User not found. Please register again.")
            return redirect('registration:customer_register')


def resend_otp_view(request):
    """View to resend OTP"""
    user_id = request.session.get('user_id_for_otp')
    
    if not user_id:
        messages.error(request, "Invalid request. Please register first.")
        return redirect('registration:login')
        
    try:
        user = User.objects.get(id=user_id)
        # Set the backend attribute explicitly
        user.backend = 'registration.auth_backends.PhoneNumberOrEmailBackend'
        
        # Delete any existing OTPs for this user
        OTPCredit.objects.filter(user=user).delete()
        
        # Generate and save new OTP
        otp_code = generate_otp()
        OTPCredit.objects.create(
            user=user,
            otp=otp_code
        )
        
        # Send SMS with OTP
        sms_sent = send_otp_via_sms(user.phoneNumber, otp_code)
        if sms_sent:
            logger.info(f"New OTP sent successfully to {user.phoneNumber}")
            messages.success(request, f"New verification code sent to {user.phoneNumber}. Please check your phone.")
        else:
            logger.warning(f"Failed to send new OTP to {user.phoneNumber}.")
            messages.warning(request, f"We've encountered an issue sending your verification code. Please try again or contact support if the problem persists.")
        
        return redirect('registration:verify_otp')
        
    except User.DoesNotExist:
        messages.error(request, "User not found. Please register again.")
        return redirect('registration:customer_register')


class OTPVerificationAPIView(View):
    def post(self, request):
        phoneNumber = request.POST.get('phoneNumber')
        otp = request.POST.get('otp')

        if not phoneNumber or not otp:
            return JsonResponse({'error': 'Phone number and OTP are required'}, status=400)

        try:
            user = User.objects.get(phoneNumber=phoneNumber)
        except User.DoesNotExist:
            return JsonResponse({'error': 'Invalid phone number'}, status=400)

        # Verify OTP using OTPCredit model
        try:
            otp_record = OTPCredit.objects.get(user=user, otp=otp)
            if timezone.now() > otp_record.otp_expiry:
                return JsonResponse({'error': 'OTP has expired'}, status=400)
        except OTPCredit.DoesNotExist:
            return JsonResponse({'error': 'Invalid OTP'}, status=400)

        # OTP verified successfully, delete OTP record
        otp_record.delete()

        return JsonResponse({'message': 'OTP verified successfully'})

class PasswordResetView(APIView):
    def post(self, request):
        phoneNumber = request.data.get('phoneNumber')
        newPassword = request.data.get('newPassword')

        if not phoneNumber or not newPassword:
            return JsonResponse({'error': 'Phone number and new password are required'}, status=400)

        try:
            user = User.objects.get(phoneNumber=phoneNumber)
        except User.DoesNotExist:
            return JsonResponse({'error': 'Invalid phone number'}, status=400)

        # Update password
        user.set_password(newPassword)
        user.otp = None  # Clear the OTP after successful password reset
        user.save()

        return JsonResponse({'message': 'Password reset successfully'})

#comfirming password

class PasswordResetConfirmView(APIView):
    def post(self, request):
        phoneNumber = request.data.get('phoneNumber')
        new_password = request.data.get('new_password')

        # Get the user with the provided phone number
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(phoneNumber=phoneNumber)
        except User.DoesNotExist:
            return Response({'error': 'User with this phone number does not exist.'}, status=status.HTTP_404_NOT_FOUND)

        # Set the new password
        user.set_password(new_password)
        user.save()

        return Response({'message': 'Password reset successfully'}, status=status.HTTP_200_OK)




# Add this class to fix the ImportError
class DeliveryAgentViewSet(viewsets.ModelViewSet):
    """API viewset for delivery agents"""
    queryset = DeliveryAgent.objects.all()
    serializer_class = None  # Will be set in __init__
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Define the serializer classes here to avoid circular imports
        from rest_framework import serializers
        
        class DeliveryAgentSerializer(serializers.ModelSerializer):
            """Normal serializer for viewing/updating delivery agents"""
            class Meta:
                model = DeliveryAgent
                fields = ['id', 'user', 'agent_id', 'phoneNumber', 'is_active', 
                         'join_date', 'last_active', 'assigned_area',
                         'total_recommendations', 'successful_recommendations']
                read_only_fields = ['join_date', 'last_active']
                ref_name = 'DeliveryAgentViewSetSerializer'
                
        class DeliveryAgentRegistrationSerializer(serializers.Serializer):
            """Special serializer just for agent registration"""
            # User fields
            phoneNumber = serializers.CharField(required=True)
            password = serializers.CharField(write_only=True, required=True)
            firstName = serializers.CharField(required=True)
            lastName = serializers.CharField(required=True)
            email = serializers.EmailField(required=False, allow_blank=True)
            
            # Agent fields
            assigned_area = serializers.CharField(required=False, allow_blank=True)
            notes = serializers.CharField(required=False, allow_blank=True)
            is_verified = serializers.BooleanField(required=False, default=False)
            
            class Meta:
                ref_name = "DeliveryAgentRegistrationSerializer"
            
            def create(self, validated_data):
                """Create a new User and DeliveryAgent"""
                logger.info(f"Creating new delivery agent with data: {validated_data}")
                
                # Extract user data
                user_data = {
                    'phoneNumber': validated_data['phoneNumber'],
                    'password': validated_data['password'],
                    'firstName': validated_data['firstName'],
                    'lastName': validated_data['lastName'],
                    'email': validated_data.get('email', ''),
                    'user_type': 'AGENT'  # Set user type to AGENT
                }
                
                # Create user
                from .models import User
                user = User.objects.create_user(**user_data)
                logger.info(f"Created new user {user.id} for delivery agent")
                
                # Create delivery agent
                agent_data = {
                    'user': user,
                    'phoneNumber': validated_data['phoneNumber'],
                    'assigned_area': validated_data.get('assigned_area', ''),
                    'notes': validated_data.get('notes', ''),
                    'is_verified': validated_data.get('is_verified', False)  # Default to False for new agents
                }
                
                agent = DeliveryAgent.objects.create(**agent_data)
                logger.info(f"Created new delivery agent with ID {agent.id} and agent_id {agent.agent_id}")
                
                return agent
    
        self.serializer_class = DeliveryAgentSerializer
        self.registration_serializer_class = DeliveryAgentRegistrationSerializer
    
    def get_serializer_class(self):
        """Use different serializers based on the action"""
        if self.action == 'create':
            return self.registration_serializer_class
        return self.serializer_class
    
    def get_permissions(self):
        """
        Allow unauthenticated access for the create action (agent registration)
        while requiring authentication for all other actions
        """
        logger.info(f"DeliveryAgentViewSet: Permission check for action '{self.action}'")
        if self.action == 'create':
            logger.info("DeliveryAgentViewSet: Allowing unauthenticated access for create action")
            return [permissions.AllowAny()]
        logger.info("DeliveryAgentViewSet: Requiring authentication for non-create action")
        return [permissions.IsAuthenticated()]
    
    def create(self, request, *args, **kwargs):
        """Override create method to add detailed logging"""
        logger.info("DeliveryAgentViewSet.create: Processing agent registration request")
        logger.info(f"DeliveryAgentViewSet.create: Request method: {request.method}")
        logger.info(f"DeliveryAgentViewSet.create: Content type: {request.content_type}")
        logger.info(f"DeliveryAgentViewSet.create: Auth header: {request.headers.get('Authorization', 'None')}")
        
        # Log request body for debugging
        try:
            if request.body:
                if 'password' in request.data:
                    # Create a copy of data without the password for safe logging
                    safe_data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
                    safe_data['password'] = '******'
                    logger.info(f"DeliveryAgentViewSet.create: Request data: {safe_data}")
                else:
                    logger.info(f"DeliveryAgentViewSet.create: Request data: {request.data}")
        except Exception as e:
            logger.info(f"DeliveryAgentViewSet.create: Could not log request data: {str(e)}")
            
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                agent = serializer.save()
                logger.info(f"Agent registration successful for agent_id: {agent.agent_id}")
                
                # Generate and save new OTP
                otp_code = generate_otp()
                OTPCredit.objects.create(
                    user=agent.user,
                    otp=otp_code
                )
                
                # Send SMS with OTP
                sms_sent = send_otp_via_sms(agent.phoneNumber, otp_code)
                
                if sms_sent:
                    logger.info(f"OTP sent successfully to agent {agent.phoneNumber}")
                    return Response({
                        'success': True,
                        'message': 'Agent registered successfully. Please verify your phone number with the OTP sent.',
                        'data': {
                            'agent_id': agent.agent_id,
                            'phoneNumber': agent.phoneNumber,
                            'assigned_area': agent.assigned_area,
                            'is_active': agent.is_active,
                            'verification_required': True
                        }
                    }, status=status.HTTP_201_CREATED)
                else:
                    logger.warning(f"Failed to send OTP to agent {agent.phoneNumber}")
                    return Response({
                        'success': True,
                        'message': 'Agent registered successfully, but verification SMS could not be sent. Contact administrator for assistance.',
                        'data': {
                            'agent_id': agent.agent_id,
                            'phoneNumber': agent.phoneNumber,
                            'assigned_area': agent.assigned_area,
                            'is_active': agent.is_active,
                            'verification_required': True
                        }
                    }, status=status.HTTP_201_CREATED)
            else:
                logger.error(f"Validation errors: {serializer.errors}")
                return Response({
                    'success': False,
                    'message': 'Invalid data provided',
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error in agent registration: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return Response({
                'success': False,
                'message': 'An error occurred during agent registration',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def list(self, request, *args, **kwargs):
        """Override list method to add detailed logging"""
        logger.info("DeliveryAgentViewSet.list: Processing request to list agents")
        logger.info(f"DeliveryAgentViewSet.list: User authenticated: {request.user.is_authenticated}")
        logger.info(f"DeliveryAgentViewSet.list: User: {request.user}")
        
        try:
            response = super().list(request, *args, **kwargs)
            logger.info(f"DeliveryAgentViewSet.list: Request successful. Response status: {response.status_code}")
            return response
        except Exception as e:
            logger.error(f"DeliveryAgentViewSet.list: Error listing agents: {str(e)}", exc_info=True)
            raise
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or hasattr(user, 'admin_profile'):
            return DeliveryAgent.objects.all()
        elif hasattr(user, 'delivery_agent'):
            return DeliveryAgent.objects.filter(id=user.delivery_agent.id)
    
    @action(methods=['POST'], detail=False, permission_classes=[AllowAny])
    def resend_otp(self, request):
        """Resend OTP to the agent's phone number"""
        phoneNumber = request.data.get('phoneNumber')
        
        logger.info(f"Resend OTP request for agent phone: {phoneNumber}")
        
        if not phoneNumber:
            return Response({
                'success': False,
                'message': 'Phone number is required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            # First find the user
            user = User.objects.get(phoneNumber=phoneNumber)
            
            # Try to find the delivery agent 
            try:
                agent = DeliveryAgent.objects.get(user=user)
            except DeliveryAgent.DoesNotExist:
                logger.error(f"No agent found for user with phone number: {phoneNumber}")
                return Response({
                    'success': False,
                    'message': 'No agent found with this phone number'
                }, status=status.HTTP_404_NOT_FOUND)
                
            # Check if there's an existing OTP record
            try:
                otp_record = OTPCredit.objects.get(user=user)
                
                # Check if the resend request is too soon
                if otp_record.otp_timestamp and (timezone.now() - otp_record.otp_timestamp).seconds < 60:
                    logger.warning("Agent OTP resend requested too soon")
                    return Response({
                        'success': False,
                        'message': 'Please wait at least 60 seconds before requesting a new OTP'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
                # Generate new OTP
                otp = generate_otp()
                otp_record.otp = otp
                otp_record.otp_timestamp = timezone.now()
                otp_record.otp_expiry = timezone.now() + timedelta(minutes=5)
                otp_record.save()
                
            except OTPCredit.DoesNotExist:
                # Create new OTP record
                otp = generate_otp()
                otp_record = OTPCredit.objects.create(
                    user=user,
                    otp=otp
                )
            
            # Send the OTP via SMS
            sms_sent = send_otp_via_sms(phoneNumber, otp_record.otp)
            
            if sms_sent:
                logger.info(f"OTP resent successfully to agent {phoneNumber}")
                return Response({
                    'success': True,
                    'message': 'OTP resent successfully'
                }, status=status.HTTP_200_OK)
            else:
                logger.error(f"Failed to resend OTP to agent {phoneNumber}")
                return Response({
                    'success': False,
                    'message': 'Failed to send OTP. Please try again later.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except User.DoesNotExist:
            logger.error(f"No user found with phone number: {phoneNumber}")
            return Response({
                'success': False,
                'message': 'No user found with this phone number'
            }, status=status.HTTP_404_NOT_FOUND)

    @action(methods=['POST'], detail=False, permission_classes=[AllowAny])
    def verify_otp(self, request):
        """Verify the OTP for an agent and activate their account"""
        phoneNumber = request.data.get('phoneNumber')
        otp = request.data.get('otp')
        
        logger.info(f"Agent OTP verification request for phone: {phoneNumber}")
        
        if not phoneNumber or not otp:
            return Response({
                'success': False,
                'message': 'Phone number and OTP are required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            # First find the user
            user = User.objects.get(phoneNumber=phoneNumber)
            
            # Try to find the delivery agent 
            try:
                agent = DeliveryAgent.objects.get(user=user)
            except DeliveryAgent.DoesNotExist:
                logger.error(f"No agent found for user with phone number: {phoneNumber}")
                return Response({
                    'success': False,
                    'message': 'No agent found with this phone number'
                }, status=status.HTTP_404_NOT_FOUND)
                
            # Check if OTP exists and is valid
            try:
                otp_record = OTPCredit.objects.filter(user=user, otp=otp).order_by('-otp_timestamp').first()
                
                if not otp_record:
                    logger.error(f"Invalid OTP entered for agent {phoneNumber}")
                    return Response({
                        'success': False,
                        'message': 'Invalid OTP code. Please try again.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                if timezone.now() > otp_record.otp_expiry:
                    logger.error(f"Expired OTP for agent {phoneNumber}")
                    return Response({
                        'success': False,
                        'message': 'OTP has expired. Please request a new one.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # OTP is valid, activate the agent
                agent.is_verified = True
                agent.is_active = True
                agent.save()
                
                # Also activate the User model
                user.is_active = True
                user.save()
                
                # Mark OTP as used
                otp_record.delete()
                logger.info(f"Agent {phoneNumber} verified successfully")
                
                # Add to benefited phone numbers
                BenefitedPhoneNumber.objects.get_or_create(phoneNumber=phoneNumber)
                
                # Generate tokens for authentication
                refresh = RefreshToken.for_user(user)
                
                return Response({
                    'success': True,
                    'message': 'Agent verified successfully',
                    'data': {
                        'access_token': str(refresh.access_token),
                        'refresh_token': str(refresh),
                        'agent': {
                            'agent_id': agent.agent_id,
                            'phoneNumber': agent.phoneNumber,
                            'name': f"{user.firstName} {user.lastName}",
                            'is_active': agent.is_active,
                            'is_verified': agent.is_verified,
                            'assigned_area': agent.assigned_area
                        }
                    }
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                logger.error(f"Error during agent OTP verification: {str(e)}")
                return Response({
                    'success': False,
                    'message': 'An error occurred during verification',
                    'error': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except User.DoesNotExist:
            logger.error(f"No user found with phone number: {phoneNumber}")
            return Response({
                'success': False,
                'message': 'No user found with this phone number'
            }, status=status.HTTP_404_NOT_FOUND)
        return DeliveryAgent.objects.none()
    
    @action(detail=False, methods=['get'])
    def my_profile(self, request):
        """Get the current agent's profile"""
        if not hasattr(request.user, 'delivery_agent'):
            return Response(
                {"detail": "You are not registered as a delivery agent"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(request.user.delivery_agent)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def recommendations(self, request, pk=None):
        """Get recommendations made by an agent"""
        agent = self.get_object()
        recommendations = AgentRecommendation.objects.filter(agent=agent)
        
        serializer = AgentRecommendationSerializer(recommendations, many=True)
        return Response(serializer.data)

@api_view(['POST'])
@permission_classes([AllowAny])
@swagger_auto_schema(
    operation_description="API endpoint for delivery agents mobile/app login",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['phoneNumber', 'password'],
        properties={
            'phoneNumber': openapi.Schema(type=openapi.TYPE_STRING, description="Agent's phone number"),
            'username': openapi.Schema(type=openapi.TYPE_STRING, description="Alternative to phoneNumber for Flutter apps"),
            'password': openapi.Schema(type=openapi.TYPE_STRING, description="Agent's password"),
        },
    ),
    responses={
        200: openapi.Response(
            description="Login successful",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'message': openapi.Schema(type=openapi.TYPE_STRING),
                    'user': openapi.Schema(type=openapi.TYPE_OBJECT),
                    'token': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'access': openapi.Schema(type=openapi.TYPE_STRING),
                            'refresh': openapi.Schema(type=openapi.TYPE_STRING),
                        }
                    )
                }
            )
        ),
        400: openapi.Response(description="Invalid credentials"),
        403: openapi.Response(description="Agent account inactive"),
    }
)
def agent_api_login(request):
    """
    API endpoint for delivery agents mobile/app login
    Returns JSON response with authentication token and user info
    """
    if request.method == 'POST':
        try:
            # Try to parse JSON data first (application/json)
            try:
                data = json.loads(request.body)
                # Keep original phoneNumber parameter but also check username field from Flutter app
                phoneNumber = data.get('phoneNumber')
                # If phoneNumber is not provided, check if username is provided (Flutter app might be using username)
                if not phoneNumber:
                    phoneNumber = data.get('username')
                password = data.get('password')
            except json.JSONDecodeError:
                # Fall back to form data (application/x-www-form-urlencoded)
                phoneNumber = request.POST.get('phoneNumber')
                # If phoneNumber is not provided, check if username is provided
                if not phoneNumber:
                    phoneNumber = request.POST.get('username')
                password = request.POST.get('password')
            
            if not phoneNumber or not password:
                return Response({
                    'success': False,
                    'message': 'Phone number and password are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Authenticate user using the phone number
            user = authenticate(request, username=phoneNumber, password=password)
            
            if user is not None:
                # Check if user is a delivery agent
                try:
                    agent = DeliveryAgent.objects.get(user=user)
                    if agent.is_active:
                        # Log the user in (for session support)
                        login(request, user)
                        
                        # Update last_active timestamp
                        agent.last_active = timezone.now()
                        agent.save(update_fields=['last_active'])
                        
                        # Generate token using REST framework
                        from rest_framework_simplejwt.tokens import RefreshToken
                        refresh = RefreshToken.for_user(user)
                        
                        return Response({
                            'success': True,
                            'message': 'Login successful',
                            'user': {
                                'id': user.id,
                                'name': user.get_full_name(),
                                'phoneNumber': user.phoneNumber,
                                'email': user.email,
                                'agent_id': agent.agent_id,
                                'assigned_area': agent.assigned_area,
                            },
                            'token': {
                                'access': str(refresh.access_token),
                                'refresh': str(refresh),
                            }
                        })
                    else:
                        return Response({
                            'success': False,
                            'message': 'Your agent account is inactive. Please contact an administrator.'
                        }, status=status.HTTP_403_FORBIDDEN)
                except DeliveryAgent.DoesNotExist:
                    return Response({
                        'success': False,
                        'message': 'You are not registered as a delivery agent.'
                    }, status=status.HTTP_403_FORBIDDEN)
            else:
                return Response({
                    'success': False,
                    'message': 'Invalid phone number or password.'
                }, status=status.HTTP_401_UNAUTHORIZED)
        
        except Exception as e:
            return Response({
                'success': False,
                'message': f'An error occurred: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # If not a POST request - this shouldn't happen with @api_view(['POST'])
    return Response({
        'success': False,
        'message': 'Only POST requests are supported for this endpoint.'
    }, status=status.HTTP_405_METHOD_NOT_ALLOWED)


