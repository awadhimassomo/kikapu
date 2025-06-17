from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from marketplace.models import Product, RelatedProduct, Order, OrderItem, Category
from registration.models import BusinessProfile, CustomerProfile, DeliveryAgent, User, AgentRecommendation
from credits.models import NFCCard, CreditTransaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

def is_staff_or_superuser(user):
    """Check if user is staff or superuser"""
    return user.is_staff or user.is_superuser

def login_view(request):
    """
    Custom login view for operations staff
    """
    if request.user.is_authenticated:
        if is_staff_or_superuser(request.user):
            return redirect('operations:dashboard')
        else:
            messages.error(request, "You don't have permission to access the operations area.")
            return redirect('website:index')
            
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if is_staff_or_superuser(user):
                login(request, user)
                return redirect('operations:dashboard')
            else:
                messages.error(request, "You don't have permission to access the operations area.")
        else:
            messages.error(request, "Invalid username or password.")
    
    return render(request, 'operations/login.html', {'title': 'Operations Login'})

@login_required
@user_passes_test(is_staff_or_superuser)
def dashboard(request):
    """
    Operations dashboard showing key metrics and links to different operations tools
    """
    # Product statistics
    total_products = Product.objects.count()
    available_products = Product.objects.filter(is_available=True).count()
    out_of_stock_products = Product.objects.filter(stock_quantity=0).count()
    related_product_count = RelatedProduct.objects.count()
    
    # Get recent products
    recent_products = Product.objects.select_related('category', 'business').prefetch_related('images').order_by('-created_at')[:10]
    
    # Category statistics
    from marketplace.models import Category
    category_count = Category.objects.count()
    parent_category_count = Category.objects.filter(parent__isnull=True).count()
    subcategory_count = Category.objects.filter(parent__isnull=False).count()
    
    # Get categories with product counts - explicitly using the imported Count
    from django.db.models import Count as DjangoCount  # Avoid any potential name conflicts
    categories = Category.objects.all().annotate(product_count=DjangoCount('products')).order_by('-product_count')[:10]
    
    # User statistics
    total_users = User.objects.count()
    customer_count = User.objects.filter(user_type='CUSTOMER').count()
    business_count = User.objects.filter(user_type='BUSINESS').count()
    agent_count = User.objects.filter(user_type='AGENT').count()
    
    # Get recently joined users
    recent_users = User.objects.order_by('-date_joined')[:10]
    
    # Agent statistics
    active_agents = DeliveryAgent.objects.filter(is_active=True).count()
    unverified_agents = DeliveryAgent.objects.filter(is_active=True, is_verified=False).count()
    pending_recommendations = AgentRecommendation.objects.filter(status='PENDING').count()
    
    # Group Delivery statistics
    from marketplace.models import DeliveryGroup, Order
    active_groups = DeliveryGroup.objects.filter(is_active=True).count()
    scheduled_deliveries = DeliveryGroup.objects.filter(
        is_active=True, 
        delivery_date__gte=timezone.now().date()
    ).count()
    
    # Calculate average group size based on associated orders
    # Use the already imported Count and Avg
    avg_group_size = DeliveryGroup.objects.filter(is_active=True).annotate(
        order_count=DjangoCount('group_orders')
    ).aggregate(avg_size=Avg('order_count'))['avg_size'] or 0
    
    # Get active delivery groups
    delivery_groups = DeliveryGroup.objects.select_related('leader__user').filter(
        is_active=True,
        delivery_date__gte=timezone.now().date()
    ).annotate(
        order_count=DjangoCount('group_orders')
    ).order_by('delivery_date')[:5]
    
    # Order statistics
    recent_orders = Order.objects.select_related('customer', 'customer__user').prefetch_related('items').order_by('-order_date')[:10]
    
    # Add items count to each order
    for order in recent_orders:
        order.items_count = order.items.count()
    
    # Order status counts
    pending_orders = Order.objects.filter(status='PENDING').count()
    processing_orders = Order.objects.filter(status='PROCESSING').count()
    completed_orders = Order.objects.filter(status='COMPLETED').count()
    cancelled_orders = Order.objects.filter(status='CANCELLED').count()
    total_orders = Order.objects.count() or 1  # Avoid division by zero
    
    # Today's orders
    today = timezone.now().date()
    todays_orders = Order.objects.filter(order_date__date=today).count()
    
    # Calculate average order value
    avg_order_value = Order.objects.aggregate(avg=Avg('total_amount'))['avg'] or 0
    
    # Calculate percentages
    pending_percent = int((pending_orders / total_orders) * 100) if total_orders > 0 else 0
    processing_percent = int((processing_orders / total_orders) * 100) if total_orders > 0 else 0
    completed_percent = int((completed_orders / total_orders) * 100) if total_orders > 0 else 0
    cancelled_percent = int((cancelled_orders / total_orders) * 100) if total_orders > 0 else 0
    
    # Sales statistics
    total_sales = Order.objects.filter(status='COMPLETED').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    
    # NFC Card statistics
    from credits.models import NFCCard
    from registration.models import CustomerProfile

    nfc_cards = NFCCard.objects.select_related('user').all()
    total_cards = nfc_cards.count()
    active_cards = nfc_cards.filter(is_active=True).count()
    assigned_cards = nfc_cards.filter(user__isnull=False).count()

    # Get recent cards with their balances
    recent_cards = nfc_cards.filter(user__isnull=False).order_by('-issued_at')[:5]
    for card in recent_cards:
        try:
            if card.user:
                profile = CustomerProfile.objects.get(user=card.user)
                card.customer_balance = profile.balance
            else:
                card.customer_balance = 0
        except CustomerProfile.DoesNotExist:
            card.customer_balance = 0
    
    context = {
        'title': 'Operations Dashboard',
        # Product stats
        'total_products': total_products,
        'available_products': available_products,
        'out_of_stock_products': out_of_stock_products,
        'related_product_count': related_product_count,
        'recent_products': recent_products,
        
        # NFC Card stats
        'total_cards': total_cards,
        'active_cards': active_cards,
        'assigned_cards': assigned_cards,
        'recent_cards': recent_cards,
        
        # Category stats
        'category_count': category_count,
        'parent_category_count': parent_category_count,
        'subcategory_count': subcategory_count,
        'categories': categories,
        
        # User stats
        'total_users': total_users,
        'customer_count': customer_count,
        'business_count': business_count,
        'agent_count': agent_count,
        'recent_users': recent_users,
        
        # Agent stats
        'active_agents': active_agents,
        'unverified_agents': unverified_agents,
        'pending_recommendations': pending_recommendations,
        
        # Group delivery stats
        'active_groups': active_groups,
        'scheduled_deliveries': scheduled_deliveries,
        'avg_group_size': avg_group_size,
        'delivery_groups': delivery_groups,
        
        # Order stats
        'recent_orders': recent_orders,
        'pending_orders': pending_orders,
        'processing_orders': processing_orders,
        'completed_orders': completed_orders,
        'cancelled_orders': cancelled_orders,
        'total_orders': total_orders,
        'todays_orders': todays_orders,
        'avg_order_value': avg_order_value,
        'pending_percent': pending_percent,
        'processing_percent': processing_percent,
        'completed_percent': completed_percent,
        'cancelled_percent': cancelled_percent,
        'total_sales': total_sales,
    }
    
    return render(request, 'operations/dashboard.html', context)

@login_required
@user_passes_test(is_staff_or_superuser)
def manage_related_products(request):
    """
    View to list all related products with search and filtering
    """
    # Get all related products with their related information
    relationships = RelatedProduct.objects.select_related('product', 'related_product').order_by('-relevance_score')
    
    # Filter if search query provided
    search_query = request.GET.get('search', '')
    if search_query:
        relationships = relationships.filter(
            Q(product__name__icontains=search_query) | 
            Q(related_product__name__icontains=search_query) |
            Q(relationship_type__icontains=search_query)
        )
    
    # Get all products for the add form
    products = Product.objects.filter(is_available=True).order_by('name')
    
    # Get relationship types for dropdown
    relationship_types = ['complementary', 'substitute', 'accessory', 'similar', 'alternative', 'bundle']
    
    context = {
        'title': 'Manage Related Products',
        'relationships': relationships,
        'products': products,
        'relationship_types': relationship_types,
        'search_query': search_query,
    }
    
    return render(request, 'operations/related_products.html', context)

@login_required
@user_passes_test(is_staff_or_superuser)
def add_related_product(request):
    """
    View to add a new related product relationship
    """
    if request.method == 'POST':
        product_id = request.POST.get('product')
        related_product_id = request.POST.get('related_product')
        relationship_type = request.POST.get('relationship_type')
        relevance_score = request.POST.get('relevance_score')
        notes = request.POST.get('notes', '')
        
        # Validation
        errors = []
        if not product_id:
            errors.append("Main product is required")
        if not related_product_id:
            errors.append("Related product is required")
        if product_id == related_product_id:
            errors.append("A product cannot be related to itself")
        
        if not errors:
            try:
                product = Product.objects.get(id=product_id)
                related_product = Product.objects.get(id=related_product_id)
                
                # Check if the relationship already exists
                if RelatedProduct.objects.filter(product=product, related_product=related_product).exists():
                    messages.warning(request, f"Relationship between {product.name} and {related_product.name} already exists.")
                else:
                    # Create the relationship
                    RelatedProduct.objects.create(
                        product=product,
                        related_product=related_product,
                        relationship_type=relationship_type,
                        relevance_score=relevance_score,
                        notes=notes
                    )
                    
                    messages.success(request, f"Relationship between {product.name} and {related_product.name} created successfully.")
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
        else:
            for error in errors:
                messages.error(request, error)
    
    return redirect('operations:related_products')

@login_required
@user_passes_test(is_staff_or_superuser)
def edit_related_product(request, relationship_id):
    """
    View to edit an existing related product relationship
    """
    # Get the relationship or return 404
    relationship = get_object_or_404(RelatedProduct, id=relationship_id)
    
    if request.method == 'POST':
        relationship_type = request.POST.get('relationship_type')
        relevance_score = request.POST.get('relevance_score')
        notes = request.POST.get('notes', '')
        
        try:
            # Update the relationship
            relationship.relationship_type = relationship_type
            relationship.relevance_score = relevance_score
            relationship.notes = notes
            relationship.save()
            
            messages.success(request, "Relationship updated successfully.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    
    return redirect('operations:related_products')

@login_required
@user_passes_test(is_staff_or_superuser)
def delete_related_product(request, relationship_id):
    """
    View to delete a related product relationship
    """
    # Get the relationship or return 404
    relationship = get_object_or_404(RelatedProduct, id=relationship_id)
    
    if request.method == 'POST':
        try:
            # Store names for the success message
            product_name = relationship.product.name
            related_product_name = relationship.related_product.name
            
            # Delete the relationship
            relationship.delete()
            
            messages.success(request, f"Relationship between {product_name} and {related_product_name} deleted successfully.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    
    return redirect('operations:related_products')

@login_required
@user_passes_test(is_staff_or_superuser)
def manage_agents(request):
    """
    View to list all delivery agents with search and filtering
    """
    # Get all delivery agents
    agents = DeliveryAgent.objects.select_related('user').all().order_by('-is_active', '-join_date')
    
    # Filter if search query provided
    search_query = request.GET.get('search', '')
    if search_query:
        agents = agents.filter(
            Q(agent_id__icontains=search_query) | 
            Q(user__firstName__icontains=search_query) |
            Q(user__lastName__icontains=search_query) |
            Q(phoneNumber__icontains=search_query) |
            Q(assigned_area__icontains=search_query)
        )
    
    context = {
        'title': 'Manage Delivery Agents',
        'agents': agents,
        'search_query': search_query,
    }
    
    return render(request, 'operations/manage_agents.html', context)

@login_required
@user_passes_test(is_staff_or_superuser)
def add_agent(request):
    """
    View to add a new delivery agent
    """
    # Get all business owners for the dropdown
    business_owners = BusinessProfile.objects.select_related('user').all()
    
    if request.method == 'POST':
        # Check if we're using an existing user
        use_existing_user = request.POST.get('use_existing_user') == 'on'
        existing_user_id = request.POST.get('existing_user_id')
        
        # Get form data
        firstName = request.POST.get('firstName')
        lastName = request.POST.get('lastName')
        phoneNumber = request.POST.get('phoneNumber')
        email = request.POST.get('email')
        password = request.POST.get('password')
        assigned_area = request.POST.get('assigned_area')
        notes = request.POST.get('notes')
        
        # Validation
        errors = []
        
        if use_existing_user:
            if not existing_user_id or existing_user_id.strip() == '':
                errors.append("Please select an existing user")
            else:
                try:
                    # If using existing user, get their user object
                    user_id = int(existing_user_id)
                    user = User.objects.get(id=user_id)
                    
                    # Check if user is already an agent
                    if DeliveryAgent.objects.filter(user=user).exists():
                        errors.append(f"User {user.get_full_name()} is already a delivery agent")
                    
                except (ValueError, TypeError):
                    errors.append("Invalid user selection. Please select a valid user.")
                except User.DoesNotExist:
                    errors.append("Selected user does not exist")
                
        else:
            # Validate new user fields
            if not firstName:
                errors.append("First name is required")
            if not lastName:
                errors.append("Last name is required")
            if not phoneNumber:
                errors.append("Phone number is required")
            if not password:
                errors.append("Password is required")
                
            # Check if phone number already exists
            if User.objects.filter(phoneNumber=phoneNumber).exists():
                errors.append(f"User with phone number {phoneNumber} already exists. Use the 'Existing User' option instead.")
        
        if not errors:
            try:
                if use_existing_user:
                    # Use existing user
                    user_id = int(existing_user_id)
                    user = User.objects.get(id=user_id)
                    phoneNumber = user.phoneNumber
                else:
                    # Create new user
                    user = User.objects.create_user(
                        phoneNumber=phoneNumber,
                        email=email,
                        password=password,
                        firstName=firstName,
                        lastName=lastName,
                        user_type='CUSTOMER'  # Use CUSTOMER type for agents
                    )
                
                # Create agent profile
                agent = DeliveryAgent.objects.create(
                    user=user,
                    phoneNumber=phoneNumber,
                    assigned_area=assigned_area,
                    notes=notes
                )
                
                messages.success(request, f"Agent {agent.agent_id} created successfully.")
                return redirect('operations:manage_agents')
            except Exception as e:
                messages.error(request, f"Error creating agent: {str(e)}")
        else:
            for error in errors:
                messages.error(request, error)
    
    # Prepare context with business owners
    context = {
        'title': 'Add New Agent',
        'business_owners': business_owners,
    }
    
    return render(request, 'operations/add_agent.html', context)

@login_required
@user_passes_test(is_staff_or_superuser)
def edit_agent(request, agent_id):
    """
    View to edit an existing delivery agent
    """
    # Get the agent or return 404
    agent = get_object_or_404(DeliveryAgent, id=agent_id)
    
    if request.method == 'POST':
        # Get form data
        firstName = request.POST.get('firstName')
        lastName = request.POST.get('lastName')
        email = request.POST.get('email')
        phoneNumber = request.POST.get('phoneNumber')
        assigned_area = request.POST.get('assigned_area')
        is_active = request.POST.get('is_active') == 'on'
        notes = request.POST.get('notes')
        new_password = request.POST.get('new_password')
        
        try:
            # Update user information
            user = agent.user
            user.firstName = firstName
            user.lastName = lastName
            if email:  # Email is optional
                user.email = email
                
            # Only change phone number if it's different and not already taken
            if phoneNumber != user.phoneNumber:
                if User.objects.filter(phoneNumber=phoneNumber).exists():
                    messages.error(request, f"Cannot update phone number. User with phone number {phoneNumber} already exists.")
                else:
                    user.phoneNumber = phoneNumber
                    agent.phoneNumber = phoneNumber
            
            # Update password if provided
            if new_password:
                user.set_password(new_password)
            
            user.save()
              # Update agent information
            agent.assigned_area = assigned_area
            # Don't override is_active flag - it's set automatically when agent verifies OTP
            # We only change is_verified via toggle_agent_status
            agent.notes = notes
            agent.save()
            
            messages.success(request, f"Agent {agent.agent_id} updated successfully.")
        except Exception as e:
            messages.error(request, f"Error updating agent: {str(e)}")
    
    return redirect('operations:manage_agents')

@login_required
@user_passes_test(is_staff_or_superuser)
def agent_details(request, agent_id):
    """
    View to show details of a specific agent, including their recommendations
    """
    # Get the agent or return 404
    agent = get_object_or_404(DeliveryAgent, id=agent_id)
    
    # Get all recommendations by this agent
    recommendations = AgentRecommendation.objects.filter(agent=agent).select_related('customer', 'approved_by').order_by('-recommendation_date')
    
    context = {
        'title': f'Agent Details - {agent.agent_id}',
        'agent': agent,
        'recommendations': recommendations,
    }
    
    return render(request, 'operations/agent_details.html', context)

@login_required
@user_passes_test(is_staff_or_superuser)
def toggle_agent_status(request, agent_id):
    """
    View to toggle an agent's verification status
    """
    # Get the agent or return 404
    agent = get_object_or_404(DeliveryAgent, id=agent_id)
    
    if request.method == 'POST':
        try:
            # Toggle verification status - NOT active status
            # Active status is set automatically when agent verifies OTP
            agent.is_verified = not agent.is_verified
            agent.save()
            
            status = "verified" if agent.is_verified else "unverified"
            messages.success(request, f"Agent {agent.agent_id} {status} successfully.")
        except Exception as e:
            messages.error(request, f"Error toggling agent verification status: {str(e)}")
    
    return redirect('operations:manage_agents')


from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.authtoken.models import Token
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from rest_framework.response import Response
from decimal import Decimal
from registration.models import CustomerProfile, User
from credits.models import NFCCard

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def agent_api_login(request):
    """
    API endpoint for agent authentication via mobile app
    Returns authentication token for valid credentials
    """
    # Get logger first for better error reporting
    import logging
    logger = logging.getLogger(__name__)
    
    # Handle different types of request body formats
    try:
        # Check if we have data in different formats
        if hasattr(request, 'data') and request.data:
            data = request.data
            logger.info(f"Request data found in request.data")
        elif request.body:
            import json
            # Try to parse as JSON
            try:
                data = json.loads(request.body.decode('utf-8'))
                logger.info(f"Successfully parsed JSON data from request.body")
            except json.JSONDecodeError:
                # Try to parse as form data
                from urllib.parse import parse_qs
                form_data = parse_qs(request.body.decode('utf-8'))
                data = {k: v[0] for k, v in form_data.items()}
                logger.info(f"Parsed form data from request.body")
        else:
            logger.warning("No data found in request")
            data = {}
        
        # Extract credentials
        phoneNumber = data.get('phoneNumber', '')
        password = data.get('password', '')
        
        logger.info(f"Agent login attempt with phoneNumber: {phoneNumber}")
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': 'Error processing request',
            'error': 'REQUEST_PROCESSING_ERROR',
            'details': str(e)
        }, status=400)
    
    # Detailed field validation
    field_errors = {}
    if not phoneNumber:
        field_errors['phoneNumber'] = ['Phone number is required']
    if not password:
        field_errors['password'] = ['Password is required']
    if field_errors:
        logger.warning(f"Field validation errors: {field_errors}")
        return JsonResponse({
            'success': False,
            'message': 'One or more required fields are missing',
            'error': 'VALIDATION_ERROR',
            'field_errors': field_errors
        }, status=400)
    
    # Log the login attempt (without logging the password)
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Agent login attempt for phoneNumber: {phoneNumber}")    # Authenticate using phone number
    user = authenticate(request, username=phoneNumber, password=password)
    logger.info(f"Authentication result for {phoneNumber}: {'Success' if user else 'Failed'}")
    
    if user is not None:
        # Check if user is an agent
        try:
            agent = DeliveryAgent.objects.get(user=user)
            
            # Check if agent is active
            if not agent.is_active:
                logger.warning(f"Login attempt for inactive agent account: {phoneNumber}")
                return JsonResponse({
                    'success': False,
                    'message': 'Your agent account is not active. Please contact support.',
                    'error': 'INACTIVE_ACCOUNT',
                    'details': 'Account requires activation by an administrator'
                }, status=403)
                  # Check if agent is verified by operations staff (for making recommendations)
            if not agent.is_verified:
                logger.warning(f"Login attempt for unverified agent account: {phoneNumber}")
                return JsonResponse({
                    'success': False,
                    'message': 'Your account has not been verified by our operations team. Please contact support for verification.',
                    'error': 'UNVERIFIED_ACCOUNT',
                    'details': 'Operations team verification required',
                    'trusted': False
                }, status=403)
                  # Get or create token for this user
            token, created = Token.objects.get_or_create(user=user)
            
            # Ensure the user_type is set to 'AGENT'
            if user.user_type != 'AGENT':
                user.user_type = 'AGENT'
                user.save(update_fields=['user_type'])
                logger.info(f"Updated user_type to AGENT for phoneNumber: {phoneNumber}")
            
            # Log successful login
            logger.info(f"Agent login successful for phoneNumber: {phoneNumber}, agent_id: {agent.agent_id}")
            
            # Return user information and token
            return JsonResponse({
                'success': True,
                'token': token.key,
                'agent_id': agent.agent_id,
                'user': {
                    'id': user.id,
                    'firstName': user.firstName,
                    'lastName': user.lastName,
                    'phoneNumber': user.phoneNumber,
                    'assigned_area': agent.assigned_area
                }
            })
        except DeliveryAgent.DoesNotExist:
            logger.warning(f"Login attempt by non-agent user: {phoneNumber}")
            return JsonResponse({
                'success': False,
                'message': 'This user is not registered as a delivery agent',
                'error': 'NOT_AGENT',
                'details': 'User exists but is not registered with agent privileges'
            }, status=403)
    else:
        # Check if the user exists to provide more specific error message
        from registration.models import User
        try:
            existing_user = User.objects.get(phoneNumber=phoneNumber)
            logger.warning(f"Login attempt with incorrect password for phoneNumber: {phoneNumber}")
            return JsonResponse({
                'success': False,
                'message': 'Incorrect password for this account',
                'error': 'INVALID_PASSWORD',
                'field_errors': {'password': ['The password is incorrect']}
            }, status=401)
        except User.DoesNotExist:
            logger.warning(f"Login attempt with non-existent phoneNumber: {phoneNumber}")
            return JsonResponse({
                'success': False,
                'message': 'No account found with this phone number',
                'error': 'USER_NOT_FOUND',
                'field_errors': {'phoneNumber': ['No account exists with this phone number']}
            }, status=401)

@login_required
@user_passes_test(is_staff_or_superuser)
def sync_card_balance(card_id):
    """
    Utility function to retrieve the NFCCard balance.
    NFCCard.balance is the source of truth for card balances.
    Returns the balance value.
    """
    try:
        card = NFCCard.objects.get(id=card_id)
        return card.balance
    except NFCCard.DoesNotExist:
        return Decimal('0.00')

def manage_nfc_cards(request):
    """
    View to list and manage NFC cards with advanced search and filtering capabilities
    """
    # Handle POST requests for card operations
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Handle delete action
        if action == 'delete':
            card_id = request.POST.get('delete_card_id')
            if card_id:
                try:
                    card = NFCCard.objects.get(id=card_id)
                    card_number = card.card_number
                    card.delete()
                    messages.success(request, f"Card {card_number} has been deleted successfully.")
                except NFCCard.DoesNotExist:
                    messages.error(request, "Card not found.")
                except Exception as e:
                    messages.error(request, f"Error deleting card: {str(e)}")
            else:
                messages.error(request, "No card ID provided.")
            
            return redirect('operations:manage_nfc_cards')

        elif action == 'edit':
            # Handle edit card form submission
            import logging
            logger = logging.getLogger(__name__)
            
            # Log all POST data for debugging
            logger.warning(f"EDIT CARD FORM DATA: {request.POST}")
            
            card_id = request.POST.get('card_id')  # Field name in the form
            is_active_str = request.POST.get('is_active')
            new_balance_str = request.POST.get('new_balance')  # We updated this in the HTML form
            status = request.POST.get('status')  # Get the status from the form
            
            logger.warning(f"Processing edit for card_id={card_id}, is_active={is_active_str}, new_balance={new_balance_str}, status={status}")
            
            if not card_id:
                messages.error(request, "No card ID provided for editing.")
                return redirect('operations:manage_nfc_cards')

            # Use the NFCCard model that's already imported at the top of the file
            logger.warning(f"Searching in model: {NFCCard.__module__}.{NFCCard.__name__}")
            
            # DEBUG: Let's dump all cards in the database to see if our card exists
            all_cards = list(NFCCard.objects.all().values('id', 'uid', 'card_number'))
            logger.warning(f"All cards in database: {all_cards}")
            
            # Find the specific card we're looking for in the list of all cards
            matching_cards = [c for c in all_cards if c.get('uid') == card_id]
            logger.warning(f"Found {len(matching_cards)} cards matching UID={card_id}: {matching_cards}")
            
            try:
                # Try multiple methods to find the card
                card = None
                
                # Method 1: Direct UID lookup
                try:
                    logger.warning(f"Method 1: Looking for card with exact UID='{card_id}' in NFCCard model")
                    card = NFCCard.objects.get(uid=card_id)
                    logger.warning(f"Found card by UID: {card_id}, card details: ID={card.id}, UID={card.uid}, Number={card.card_number}")
                except NFCCard.DoesNotExist:
                    logger.warning(f"Card not found by exact UID match: {card_id}")
                
                # Method 2: Case-insensitive UID lookup
                if not card:
                    try:
                        logger.warning(f"Method 2: Looking for card with case-insensitive UID iexact='{card_id}'")
                        card = NFCCard.objects.get(uid__iexact=card_id)
                        logger.warning(f"Found card by case-insensitive UID: {card_id}, card details: ID={card.id}, UID={card.uid}, Number={card.card_number}")
                    except NFCCard.DoesNotExist:
                        logger.warning(f"Card not found by case-insensitive UID match either")
                
                # Method 3: Try database ID if it's numeric
                if not card:
                    try:
                        card_id_int = int(card_id)
                        logger.warning(f"Method 3: Looking for card with ID={card_id_int}")
                        card = NFCCard.objects.get(id=card_id_int)
                        logger.warning(f"Found card by ID: {card_id_int}, card details: ID={card.id}, UID={card.uid}, Number={card.card_number}")
                    except (ValueError, TypeError, NFCCard.DoesNotExist):
                        logger.warning(f"Card not found by database ID either")
                
                # If still no card found, raise error
                if not card:
                    raise NFCCard.DoesNotExist(f"Could not find card with UID={card_id} using any method")
                
                # Update card status based on form data
                
                # First check if a specific status was selected in the dropdown
                if status is not None and status in ['unassigned', 'assigned', 'active', 'expired', 'blocked', 'lost', 'disabled']:
                    # Update the card status directly from the dropdown
                    old_status = card.status
                    card.status = status
                    logger.warning(f"Changed card status from {old_status} to {status} based on dropdown selection")
                    
                    # Keep is_active in sync with status
                    card.is_active = (status == 'active')
                
                # Then process the is_active checkbox, but only if no status was explicitly selected
                elif is_active_str is not None:
                    # Check for different possible true values - 'on' from normal checkbox, 'true' from the form
                    is_active_lower = is_active_str.lower()
                    card.is_active = is_active_lower in ['on', 'true']
                    
                    # Also update the status field to be consistent with is_active
                    if card.is_active:
                        # Only change status to 'active' if it's not already in a terminal state
                        if card.status in ['unassigned', 'assigned']:
                            card.status = 'active'
                    else:
                        # Only change status if it's currently active
                        if card.status == 'active':
                            card.status = 'assigned' if card.user else 'unassigned'
                
                logger.warning(f"Final values: card.is_active={card.is_active}, card.status={card.status}")
                
                # Update balance in NFCCard
                if new_balance_str is not None and new_balance_str != '':
                    try:
                        new_balance = Decimal(new_balance_str)
                        if new_balance < 0:
                            messages.error(request, "Balance cannot be negative.")
                        else:
                            # Update NFCCard.balance - this is the source of truth
                            card.balance = new_balance
                            
                            if card.user:
                                messages.success(request, f"Balance for card {card.card_number} (User: {card.user.get_full_name()}) updated successfully.")
                            else:
                                messages.success(request, f"Balance for unassigned card {card.card_number} updated successfully.")
                    except ValueError:
                        messages.error(request, "Invalid balance amount provided.")
                elif new_balance_str == '': # Explicitly clearing balance
                    # Set balance to 0 on NFCCard only
                    card.balance = Decimal('0.00')
                        
                    messages.info(request, f"Balance for card {card.card_number} cleared.")

                card.save() # Save NFCCard changes (like is_active or its own balance)
                if not (new_balance_str is not None and new_balance_str != '' and card.user): # Avoid double success message if balance was updated
                    messages.success(request, f"Card {card.card_number} details updated successfully.")

            except NFCCard.DoesNotExist:
                messages.error(request, "Card not found.")
            except User.DoesNotExist: # Should not happen if card.user exists
                messages.error(request, "Associated user not found.")
            except CustomerProfile.DoesNotExist: # Should be handled by get_or_create
                messages.error(request, "Customer profile not found and could not be created.")
            except Exception as e:
                messages.error(request, f"Error updating card: {str(e)}")
            
            return redirect('operations:manage_nfc_cards')

    # Get search parameters from GET request
    search_query = request.GET.get('card_number', '')
    user_filter = request.GET.get('user', '')
    status_filter = request.GET.get('status', '')
    balance_min = request.GET.get('balance_min', '')
    balance_max = request.GET.get('balance_max', '')
    card_type_filter = request.GET.get('card_type', '')
    date_issued = request.GET.get('date_issued', '')
    
    # Flag to indicate if any search filters are active
    search_active = bool(search_query or user_filter or status_filter or 
                         balance_min or balance_max or card_type_filter or date_issued)
    
    # Base queryset
    nfc_cards = NFCCard.objects.select_related('user').all()
    
    # Apply search filter if provided
    if search_query:
        nfc_cards = nfc_cards.filter(
            Q(card_number__icontains=search_query) |
            Q(uid__icontains=search_query)
        )
    
    # Apply user filter if provided
    if user_filter:
        nfc_cards = nfc_cards.filter(
            Q(user__firstName__icontains=user_filter) |
            Q(user__lastName__icontains=user_filter) |
            Q(user__phoneNumber__icontains=user_filter)
        )
    
    # Apply status filter if provided
    if status_filter:
        if status_filter == 'active':
            nfc_cards = nfc_cards.filter(is_active=True)
        elif status_filter == 'inactive':
            nfc_cards = nfc_cards.filter(is_active=False)
        elif status_filter == 'assigned':
            nfc_cards = nfc_cards.filter(status='assigned')
        elif status_filter == 'unassigned':
            nfc_cards = nfc_cards.filter(status='unassigned')
            
    # Apply balance range filter if provided
    if balance_min and balance_min.isdigit():
        nfc_cards = nfc_cards.filter(balance__gte=Decimal(balance_min))
    if balance_max and balance_max.isdigit():
        nfc_cards = nfc_cards.filter(balance__lte=Decimal(balance_max))
        
    # Apply card type filter if provided
    if card_type_filter:
        nfc_cards = nfc_cards.filter(card_type=card_type_filter)
        
    # Apply date issued filter if provided
    if date_issued:
        # Parse the date string to a Python date object
        try:
            issued_date = timezone.datetime.strptime(date_issued, '%Y-%m-%d').date()
            # Filter cards issued on this date
            nfc_cards = nfc_cards.filter(
                issued_at__date=issued_date
            )
        except (ValueError, TypeError):
            # If date parsing fails, ignore this filter
            pass
    
    # Paginate results
    paginator = Paginator(nfc_cards.order_by('-issued_at'), 20)  # 20 cards per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # No need to sync balances - NFCCard.balance is the source of truth
    # Just use the balance directly in the template
    
    # Get card types for the dropdown
    card_types = dict(NFCCard._meta.get_field('card_type').choices)
    
    # Get all users for the dropdown lists
    users = User.objects.filter(user_type='CUSTOMER')
    
    context = {
        'title': 'Manage NFC Cards',
        'cards': page_obj,
        'search_query': search_query,
        'user_filter': user_filter,
        'status_filter': status_filter,
        'balance_min': balance_min,
        'balance_max': balance_max,
        'card_type_filter': card_type_filter,
        'date_issued': date_issued,
        'card_types': card_types,
        'total_cards': nfc_cards.count(),
        'active_cards': nfc_cards.filter(is_active=True).count(),
        'assigned_cards': nfc_cards.filter(user__isnull=False).count(),
        'users': users,
        'search_active': search_active,
    }
    
    return render(request, 'operations/manage_nfc_cards.html', context)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_customers(request):
    """
    API endpoint that returns a list of customer phone numbers
    This is used for dropdowns and selectors in the operations interface
    """
    # Check if user has staff permissions
    if not request.user.is_staff:
        return Response({
            'success': False,
            'message': 'You do not have permission to access this resource'
        }, status=403)
    
    # Get all users with CUSTOMER role
    customers = User.objects.filter(user_type='CUSTOMER')
    
    # Apply search filter if provided
    search_query = request.query_params.get('search', '')
    if search_query:
        customers = customers.filter(
            Q(phoneNumber__icontains=search_query) |
            Q(firstName__icontains=search_query) |
            Q(lastName__icontains=search_query)
        )
    
    # Limit the number of results if needed
    limit = request.query_params.get('limit', None)
    if limit and limit.isdigit():
        customers = customers[:int(limit)]
    
    # Prepare the response data
    customer_data = [{
        'id': customer.id,
        'phoneNumber': customer.phoneNumber,
        'name': f"{customer.firstName} {customer.lastName}".strip(),
    } for customer in customers]
    
    return Response({
        'success': True,
        'count': len(customer_data),
        'customers': customer_data
    })

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def search_customer(request):
    """Simple API endpoint that searches for a customer by phone number"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Log detailed information
    logger.warning("==== CUSTOMER SEARCH REQUEST RECEIVED ====")
    logger.warning(f"Method: {request.method}")
    logger.warning(f"User: {request.user.username}")
    
    # Log the request data
    logger.warning(f"Request data: {request.data}")
    
    # Get the phone number (check both 'phoneNumber' and 'phone' keys)
    phone_number = request.data.get('phoneNumber', request.data.get('phone', ''))
    logger.warning(f"Phone number to search: {phone_number}")
    
    # Log all customers in the system
    customers = User.objects.filter(user_type='CUSTOMER')
    logger.warning(f"Total customers in system: {customers.count()}")
    for idx, customer in enumerate(customers[:5]):
        logger.warning(f"  {idx+1}. {customer.phoneNumber} - {customer.firstName} {customer.lastName}")
    
    if phone_number:
        # Try to find the customer
        try:
            customer = User.objects.get(phoneNumber=phone_number, user_type='CUSTOMER')
            
            # Log all fields for the customer to see what's in the database
            logger.warning("========== CUSTOMER DETAILS IN DATABASE ==========")
            logger.warning(f"Customer ID: {customer.id}")
            logger.warning(f"Phone Number: {customer.phoneNumber}")
            logger.warning(f"First Name: '{customer.firstName}' (length: {len(customer.firstName) if customer.firstName else 0})")
            logger.warning(f"Last Name: '{customer.lastName}' (length: {len(customer.lastName) if customer.lastName else 0})")
            logger.warning(f"Email: '{customer.email}' (length: {len(customer.email) if customer.email else 0})")
            logger.warning(f"Username: '{customer.username}' (length: {len(customer.username) if customer.username else 0})")
            logger.warning(f"User Type: {customer.user_type}")
            logger.warning(f"Date Joined: {customer.date_joined}")
            
            # Try to get customer profile for more details
            try:
                profile = CustomerProfile.objects.get(user=customer)
                logger.warning("------ CustomerProfile Details ------")
                logger.warning(f"Loyalty Points: {profile.loyalty_points}")
                logger.warning(f"Card Type: {profile.card_type}")
                logger.warning(f"Joined Date: {profile.joined_date}")
                logger.warning(f"Credit Score: {profile.credit_score if hasattr(profile, 'credit_score') else 'N/A'}")
            except CustomerProfile.DoesNotExist:
                logger.warning("No CustomerProfile found")
            except Exception as e:
                logger.warning(f"Error fetching CustomerProfile: {e}")
                
            logger.warning("=====================================================")
            logger.warning(f"Found customer: {customer.firstName} {customer.lastName}")
            
            # Get NFC card if available
            try:
                nfc_card = NFCCard.objects.get(user=customer)
                card_number = nfc_card.card_number
                card_status = nfc_card.status
                logger.warning(f"Found card: {card_number}, status: {card_status}")
            except NFCCard.DoesNotExist:
                logger.warning("No NFC card found for this customer")
                card_number = None
                card_status = 'none'
            
            # Return the customer data
            return Response({
                'success': True,
                'customer': {
                    'id': customer.id,
                    'firstname': customer.firstName,
                    'lastname': customer.lastName,
                    'phone': customer.phoneNumber,
                    'cardNumber': card_number,
                    'cardStatus': card_status
                }
            })
        except User.DoesNotExist:
            logger.warning(f"No customer found with phone number: {phone_number}")
            return Response({
                'success': False,
                'message': 'No customer found with this phone number'
            }, status=404)
    else:
        logger.warning("No phone number provided")
        return Response({
            'success': False,
            'message': 'Phone number is required'
        }, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def scan_card(request):
    """API endpoint to scan a card, check if it exists, and activate it if needed"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Log detailed information
    logger.warning("==== CARD SCAN REQUEST RECEIVED ====")
    logger.warning(f"Method: {request.method}")
    logger.warning(f"User: {request.user.username}")
    logger.warning(f"Request data: {request.data}")
    
    # Get the card ID or UID from the request
    card_id = request.data.get('card_id')
    card_uid = request.data.get('card_uid')
    scan_type = request.data.get('scan_type', 'activation')  # Default is activation
    overwrite = request.data.get('overwrite', False)  # Whether to overwrite existing card
    
    if not card_id and not card_uid:
        logger.warning("No card ID or UID provided")
        return Response({
            'success': False,
            'message': 'Card ID or UID is required'
        }, status=400)
    
    # Look up the card
    from credits.models import NFCCard
    
    # Check if we should handle this as a card overwrite scenario
    card_exists = False
    if card_uid and scan_type == 'registration' and overwrite:
        card_exists = NFCCard.objects.filter(uid=card_uid).exists()
        if card_exists:
            logger.warning(f"Card with UID {card_uid} exists and will be overwritten")

    try:
        # Try to find by card_id first (visible number)
        if card_id:
            logger.warning(f"Searching for card with ID: {card_id}")
            card = NFCCard.objects.get(card_number=card_id)
        # Otherwise try by card_uid (internal ID)
        elif card_uid:
            logger.warning(f"Searching for card with UID: {card_uid}")
            card = NFCCard.objects.get(uid=card_uid)
            
        # If we're in overwrite mode and found a card, reset it
        if overwrite and scan_type == 'registration':
            logger.warning(f"Overwriting existing card: {card.card_number}, UID: {card.uid}")
            # Save the card number for reuse
            old_card_number = card.card_number
            
            # Reset the card
            card.status = 'unassigned'
            card.user = None
            card.balance = 0
            card.save()
            
            return Response({
                'success': True,
                'message': f'Card overwritten successfully',
                'card': {
                    'id': card.id,
                    'card_number': card.card_number,
                    'uid': card.uid,
                    'status': card.status,
                    'overwritten': True,
                }
            })
            
        logger.warning(f"Found card: {card.card_number}, status: {card.status}, usage: {card.usage_status if hasattr(card, 'usage_status') else 'N/A'}")
        
        # Get associated user if any
        if card.user:
            logger.warning(f"Card belongs to user: {card.user.firstName} {card.user.lastName}, phone: {card.user.phoneNumber}")
        else:
            logger.warning("Card is not assigned to any user")
        
        # Check if card is inactive and needs activation
        if scan_type == 'activation':
            if card.status == 'inactive' or card.status == 'assigned':
                # Activate the card
                old_status = card.status
                card.status = 'active'
                
                # Update usage status if it has that field
                if hasattr(card, 'usage_status') and (card.usage_status == 'never_used' or not card.usage_status):
                    card.usage_status = 'first_time'
                    logger.warning(f"Updating card usage from 'never_used' to 'first_time'")
                
                card.save()
                logger.warning(f"Card activated: status changed from {old_status} to {card.status}")
                
                return Response({
                    'success': True,
                    'message': f'Card activated successfully',
                    'card': {
                        'id': card.id,
                        'card_number': card.card_number,
                        'status': card.status,
                        'usage_status': getattr(card, 'usage_status', 'N/A'),
                        'user': {
                            'id': card.user.id,
                            'name': f"{card.user.firstName} {card.user.lastName}".strip(),
                            'phone': card.user.phoneNumber
                        } if card.user else None
                    }
                })
            else:
                logger.warning(f"Card is already {card.status}, no activation needed")
                return Response({
                    'success': True,
                    'message': f'Card is already {card.status}',
                    'card': {
                        'id': card.id,
                        'card_number': card.card_number,
                        'status': card.status,
                        'usage_status': getattr(card, 'usage_status', 'N/A'),
                        'user': {
                            'id': card.user.id,
                            'name': f"{card.user.firstName} {card.user.lastName}".strip(),
                            'phone': card.user.phoneNumber
                        } if card.user else None
                    }
                })
        else:
            # Just return card info without activation
            return Response({
                'success': True,
                'message': 'Card information retrieved',
                'card': {
                    'id': card.id,
                    'card_number': card.card_number,
                    'status': card.status,
                    'usage_status': getattr(card, 'usage_status', 'N/A'),
                    'user': {
                        'id': card.user.id,
                        'name': f"{card.user.firstName} {card.user.lastName}".strip(),
                        'phone': card.user.phoneNumber
                    } if card.user else None
                }
            })
    except NFCCard.DoesNotExist:
        logger.warning(f"Card not found")
        return Response({
            'success': False,
            'message': 'Card not found'
        }, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def force_sync_all_balances(request):
    """
    Force sync all balances - making NFCCard.balance the source of truth
    """
    from django.http import HttpResponse
    from credits.models import NFCCard
    from registration.models import CustomerProfile, User
    from decimal import Decimal
    import json
    
    # Get specific card ID from URL if provided
    card_id = request.GET.get('card_id')
    
    # Track results
    updated = []
    not_updated = []
    total_cards = 0
    
    # If a specific card ID was provided
    if card_id:
        try:
            card = NFCCard.objects.get(id=card_id)
            total_cards = 1
            # Update just this card's balance in the admin
            updated.append({
                'card_id': card.id,
                'card_number': card.card_number,
                'balance': str(card.balance),
                'user': card.user.get_full_name() if card.user else 'None'
            })
        except NFCCard.DoesNotExist:
            not_updated.append({
                'card_id': card_id,
                'reason': 'Card not found'
            })
    else:
        # Process all cards
        cards = NFCCard.objects.select_related('user').all()
        total_cards = cards.count()
        
        for card in cards:
            try:
                # NFCCard.balance is the source of truth
                balance = card.balance
                updated.append({
                    'card_id': card.id,
                    'card_number': card.card_number,
                    'balance': str(balance),
                    'user': card.user.get_full_name() if card.user else 'None'
                })
            except Exception as e:
                not_updated.append({
                    'card_id': card.id if card else 'Unknown',
                    'reason': str(e)
                })
    
    # Return a detailed response
    return HttpResponse(
        f"<h2>Balance Sync Results</h2>" +
        f"<p>Processed {total_cards} cards. {len(updated)} updated, {len(not_updated)} failed.</p>" +
        f"<h3>Updated Cards:</h3><pre>{json.dumps(updated, indent=2)}</pre>" +
        f"<h3>Failed Cards:</h3><pre>{json.dumps(not_updated, indent=2)}</pre>"
    )

@api_view(['GET'])
def get_card_details(request, card_id):
    """API endpoint to get card details for editing"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Log that this endpoint was called
    logger.warning(f"Card details requested for card ID: {card_id}")
    
    try:
        # Get the card from the database
        # Try multiple methods to find the card
        from credits.models import NFCCard
        
        # Log all cards in the database to help debug
        all_cards = list(NFCCard.objects.all().values('id', 'uid', 'card_number'))
        logger.warning(f"All cards in database: {all_cards}")
        
        # First try to find by direct UID
        try:
            logger.warning(f"Looking for card with UID={card_id}")
            card = NFCCard.objects.get(uid=card_id)
            logger.warning(f"Found card by UID: {card_id}, card details: ID={card.id}, UID={card.uid}, Number={card.card_number}")
        except NFCCard.DoesNotExist:
            # Then try database ID
            try:
                card_id_int = int(card_id)
                logger.warning(f"Looking for card with ID={card_id_int}")
                card = NFCCard.objects.get(id=card_id_int)
                logger.warning(f"Found card by ID: {card_id_int}, card details: ID={card.id}, UID={card.uid}, Number={card.card_number}")
            except (ValueError, NFCCard.DoesNotExist):
                # If both methods fail, raise error
                logger.warning(f"Card not found by any method with identifier: {card_id}")
                raise NFCCard.DoesNotExist(f"Card not found with identifier: {card_id}")
        
        # Use card.balance directly as the source of truth
        balance = card.balance
        logger.warning(f"Found balance: {balance} for card {card.card_number}")
        
        # Prepare the response data with serializable values
        # Convert Decimal to string to avoid JSON serialization issues
        response_data = {
            'id': card.id,
            'card_number': card.card_number,
            'uid': card.uid,
            'is_active': card.is_active,  # Use is_active field directly
            'status': card.status,
            'balance': str(balance),  # Convert Decimal to string
            'user': None,
        }
        
        # Add user data if the card is assigned
        if card.user:
            response_data['user'] = {
                'id': card.user.id,
                'username': card.user.username,
                'name': f"{card.user.firstName} {card.user.lastName}".strip(),
                'phone': card.user.phoneNumber
            }
        
        import json
        logger.warning(f"Returning card details (raw): {response_data}")
        logger.warning(f"Returning card details (JSON): {json.dumps(response_data)}")
        
        # Log key fields separately for clarity
        logger.warning(f"Key fields: card_number={response_data['card_number']}, ")
        logger.warning(f"           balance={response_data['balance']}, ")
        logger.warning(f"           user={response_data['user']}")
        
        # Format the response in two ways for compatibility
        # 1. Direct format (current frontend expects this)
        direct_response = response_data
        
        # 2. Wrapped format (some other API endpoints use this structure)
        wrapped_response = {
            'success': True,
            'card': response_data
        }
        
        # Use the direct format as that's what the frontend expects
        return Response(direct_response)
    
    except NFCCard.DoesNotExist:
        logger.warning(f"Card not found with ID: {card_id}")
        return Response({'error': 'Card not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting card details: {e}")
        return Response({'error': str(e)}, status=500)

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])  # Allow any user to access for debugging
def debug_api_request(request, path):
    """Debug endpoint to catch all API requests"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.warning(f"==== DEBUG ENDPOINT REACHED ====")
    logger.warning(f"Path: {path}")
    logger.warning(f"Method: {request.method}")
    logger.warning(f"Query params: {request.query_params}")
    logger.warning(f"User: {request.user}")
    logger.warning(f"Headers: {dict(request.headers)}")
    
    # Log request data
    try:
        if hasattr(request, 'data'):
            logger.warning(f"Request data: {request.data}")
    except Exception as e:
        logger.warning(f"Error accessing request.data: {e}")
    
    # Log raw body
    try:
        if request.body:
            logger.warning(f"Raw body: {request.body.decode('utf-8')}")
    except Exception as e:
        logger.warning(f"Error decoding request body: {e}")
    
    # Log all users in the system for reference
    try:
        all_users = User.objects.all()
        logger.warning(f"Total users in system: {all_users.count()}")
        logger.warning("First 5 users:")
        for idx, user in enumerate(all_users[:5]):
            logger.warning(f"  {idx+1}. {user.phoneNumber} - {user.firstName} {user.lastName} - Type: {user.user_type}")
    except Exception as e:
        logger.warning(f"Error listing users: {e}")
    
    return Response({
        'debug': True,
        'message': f'Debug endpoint caught request to: {path}',
        'method': request.method,
        'data_received': request.data if hasattr(request, 'data') else None
    })

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def scan_card(request):
    """Handle NFC card scanning requests"""
    import logging
    from decimal import Decimal
    
    logger = logging.getLogger(__name__)
    
    # Log the raw request to see exactly what's being sent
    logger.warning(f"User: {request.user}")
    logger.warning(f"Request method: {request.method}")
    logger.warning(f"Request content type: {request.content_type if hasattr(request, 'content_type') else 'No content_type'}")
    logger.warning(f"Request headers: {request.headers if hasattr(request, 'headers') else 'No headers'}")
    logger.warning(f"Raw request body: {request.body.decode('utf-8') if request.body else 'Empty body'}")
    
    # Try to get data from different sources
    request_body = None
    try:
        # Try to parse JSON data
        if request.body:
            import json
            request_body = json.loads(request.body)
            logger.warning(f"Request body (JSON): {request_body}")
    except json.JSONDecodeError:
        # Not JSON, might be form data or something else
        logger.warning("Request body is not JSON or is malformed")
    
    # Log all possible sources of data
    logger.warning(f"Request POST data: {request.POST}")
    logger.warning(f"Request GET data: {request.GET}")
    logger.warning(f"Request data attribute: {request.data if hasattr(request, 'data') else 'No request.data'}")
    
    # Get card UID from request (try multiple sources)
    card_id = None
    
    # Try direct access to the raw body if it's a simple value
    raw_body = request.body.decode('utf-8') if request.body else ''
    if raw_body and not '{' in raw_body and not '=' in raw_body:
        # The body might just be the card ID directly
        card_id = raw_body.strip('"\'')
        logger.warning(f"Extracted card_id from raw body: {card_id}")
        
    # Try from request.data (parsed by DRF)
    if not card_id and hasattr(request, 'data'):
        if isinstance(request.data, dict):
            card_id = request.data.get('card_id') or request.data.get('uid') or request.data.get('cardId')
        elif hasattr(request.data, '__str__'):
            # The data might be the card ID directly as a string
            card_id = str(request.data)
    
    # Try from JSON body
    if not card_id and request_body:
        if isinstance(request_body, dict):
            card_id = request_body.get('card_id') or request_body.get('uid') or request_body.get('cardId')
        elif isinstance(request_body, str):
            card_id = request_body
    
    # Try from POST/GET
    if not card_id:
        card_id = (request.POST.get('card_id') or request.POST.get('uid') or request.POST.get('cardId') 
                 if request.method == 'POST' else 
                  request.GET.get('card_id') or request.GET.get('uid') or request.GET.get('cardId'))
    
    logger.warning(f"Final extracted card_id: {card_id}")
    
    if not card_id:
        logger.warning(f"No card ID provided")
        return Response({
            'success': False,
            'message': 'No card ID provided'
        }, status=400)
    
    try:
        # Try to find the card by UID
        card = NFCCard.objects.get(uid=card_id)
        logger.warning(f"Found card: {card.card_number}, status: {card.status}, balance: {card.balance}")
        
        # First check if card is unassigned - if so, return an error
        if card.status == 'unassigned':
            logger.warning(f"Rejecting unassigned card: {card.card_number}")
            return Response({
                'success': False,
                'status': 'UNASSIGNED_CARD',
                'message': 'This card cannot be used for payment or adding credit because it is not assigned to any user',
                'card': {
                    'card_number': card.card_number,
                    'status': card.status
                }
            }, status=400)  # Return HTTP 400 Bad Request
        
        # Check if card is active
        if not card.is_active:
            # Activate the card if it's assigned but not active
            if card.status == 'assigned':
                card.status = 'active'
                card.is_active = True
                card.activated_at = timezone.now()
                card.save()
                logger.warning(f"Activated card: {card.card_number}")
                
                return Response({
                    'success': True,
                    'message': 'Card activated successfully',
                    'card': {
                        'id': card.id,
                        'card_number': card.card_number,
                        'uid': card.uid,
                        'status': card.status,
                        'balance': str(card.balance),
                        'is_active': card.is_active,
                        'user': {
                            'id': card.user.id,
                            'name': f"{card.user.firstName} {card.user.lastName}".strip(),
                            'phone': card.user.phoneNumber
                        } if card.user else None
                    }
                })
        
        # Return card details for assigned or active cards
        return Response({
            'success': True,
            'message': 'Card found',
            'card': {
                'id': card.id,
                'card_number': card.card_number,
                'uid': card.uid,
                'status': card.status,
                'balance': str(card.balance),
                'is_active': card.is_active,
                'user': {
                    'id': card.user.id,
                    'name': f"{card.user.firstName} {card.user.lastName}".strip(),
                    'phone': card.user.phoneNumber
                } if card.user else None
            }
        })
        
    except NFCCard.DoesNotExist:
        logger.warning(f"Card not found")
        return Response({
            'success': False,
            'message': 'Card not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error scanning card: {str(e)}")
        return Response({
            'success': False,
            'message': f"Error: {str(e)}"
        }, status=500)
