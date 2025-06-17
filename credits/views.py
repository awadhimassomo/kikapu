from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, permission_classes
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Sum

from .models import NFCCard, CreditTransaction, CardApplication
from .serializers import (
    NFCCardSerializer,
    CustomerSerializer,
    TransactionSerializer,
    PostpaidApplicationSerializer,
    CreditEventSerializer,
    AgentRecommendationSerializer,
    NFCCardRegistrationSerializer,
    CustomerAssignmentSerializer
)
from registration.models import DeliveryAgent, AgentRecommendation, CreditEvent

# API Views
class NFCCardViewSet(viewsets.ModelViewSet):
    """
    API endpoint for NFC cards management
    """
    queryset = NFCCard.objects.all()
    serializer_class = NFCCardSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Admin users can see all cards, regular users only see their own
        user = self.request.user
        if user.is_staff or hasattr(user, 'admin_profile'):
            return NFCCard.objects.all()
        return NFCCard.objects.filter(user=user)
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register a new blank NFC card (admin only)"""
        if not request.user.is_staff and not hasattr(request.user, 'admin_profile'):
            return Response(
                {"detail": "You do not have permission to register new cards."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """Assign a card to a customer"""
        if not request.user.is_staff and not hasattr(request.user, 'delivery_agent'):
            return Response(
                {"detail": "You do not have permission to assign cards."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        card = self.get_object()
        if card.status != 'UNASSIGNED':
            return Response(
                {"detail": f"Card is already {card.get_status_display()}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use CustomerSerializer to handle assignment
        customer_serializer = CustomerSerializer(data=request.data)
        if customer_serializer.is_valid():
            customer = customer_serializer.save()
            return Response(
                {"detail": "Card assigned successfully", "customer_id": customer.id},
                status=status.HTTP_200_OK
            )
        return Response(customer_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TransactionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for payment transactions
    """
    queryset = CreditTransaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Filter transactions based on user role
        user = self.request.user
        if user.is_staff or hasattr(user, 'admin_profile'):
            return CreditTransaction.objects.all()
        elif hasattr(user, 'delivery_agent'):
            # Agents see transactions they processed
            return CreditTransaction.objects.filter(agent=user.delivery_agent)
        else:
            # Regular users see only their transactions
            return CreditTransaction.objects.filter(customer=user)
    
    @action(detail=False, methods=['post'])
    def authorize_payment(self, request):
        """Process a payment transaction with NFC card and PIN"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            transaction = serializer.save()
            return Response(
                {"detail": "Payment processed successfully", "transaction_id": transaction.id},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def customer_transactions(self, request):
        """Get transactions for a specific customer (for agents and admins)"""
        user = request.user
        if not (user.is_staff or hasattr(user, 'admin_profile') or hasattr(user, 'delivery_agent')):
            return Response(
                {"detail": "You do not have permission to view customer transactions."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return Response(
                {"detail": "customer_id parameter is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        transactions = CreditTransaction.objects.filter(customer_id=customer_id)
        serializer = self.get_serializer(transactions, many=True)
        return Response(serializer.data)

class PostpaidApplicationViewSet(viewsets.ModelViewSet):
    """
    API endpoint for Postpaid applications
    """
    queryset = CardApplication.objects.all()
    serializer_class = PostpaidApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or hasattr(user, 'admin_profile'):
            return CardApplication.objects.all()
        return CardApplication.objects.filter(customer=user)
    
    @action(detail=False, methods=['post'])
    def apply(self, request):
        """Submit a postpaid application"""
        # Set the customer to the current user
        data = request.data.copy()
        data['customer'] = request.user.id
        
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            application = serializer.save()
            return Response(
                {"detail": "Application submitted successfully", "application_id": application.id},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a postpaid application (admin only)"""
        if not request.user.is_staff and not hasattr(request.user, 'admin_profile'):
            return Response(
                {"detail": "You do not have permission to approve applications."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        application = self.get_object()
        if application.status != 'PENDING':
            return Response(
                {"detail": f"Cannot approve application with status: {application.get_status_display()}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        credit_limit = request.data.get('credit_limit', 25000)  # Default 25,000
        notes = request.data.get('notes', '')
        
        # Get admin user if available
        admin_user = None
        if hasattr(request.user, 'admin_profile'):
            admin_user = request.user.admin_profile
        
        # Approve the application
        try:
            card = application.approve(reviewed_by=request.user, credit_limit=credit_limit)
            application.notes = notes
            application.save()
            
            return Response(
                {"detail": "Application approved successfully", "card_id": card.id},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a postpaid application (admin only)"""
        if not request.user.is_staff and not hasattr(request.user, 'admin_profile'):
            return Response(
                {"detail": "You do not have permission to reject applications."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        application = self.get_object()
        if application.status != 'PENDING':
            return Response(
                {"detail": f"Cannot reject application with status: {application.get_status_display()}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', 'Application rejected')
        
        # Reject the application
        application.reject(reviewed_by=request.user, reason=reason)
        
        return Response(
            {"detail": "Application rejected successfully"},
            status=status.HTTP_200_OK
        )

class AgentRecommendationViewSet(viewsets.ModelViewSet):
    """
    API endpoint for agent recommendations
    """
    queryset = AgentRecommendation.objects.all()
    serializer_class = AgentRecommendationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or hasattr(user, 'admin_profile'):
            return AgentRecommendation.objects.all()
        elif hasattr(user, 'delivery_agent'):
            return AgentRecommendation.objects.filter(agent=user.delivery_agent)
        return AgentRecommendation.objects.filter(customer=user)
    
    @action(detail=False, methods=['post'])
    def recommend(self, request):
        """Create a recommendation for a customer"""
        if not hasattr(request.user, 'delivery_agent'):
            return Response(
                {"detail": "Only delivery agents can make recommendations."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Set the agent to the current user's agent profile
        data = request.data.copy()
        data['agent_id'] = request.user.delivery_agent.id
        
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            recommendation = serializer.save()
            return Response(
                {"detail": "Recommendation created successfully", "recommendation_id": recommendation.id},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CreditEventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for credit events (read-only)
    """
    queryset = CreditEvent.objects.all()
    serializer_class = CreditEventSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or hasattr(user, 'admin_profile'):
            return CreditEvent.objects.all()
        return CreditEvent.objects.filter(customer=user)

# Web Views for Credits System

@login_required
def dashboard(request):
    """
    Main dashboard for the credits system.
    Displays user's cards, balance, and recent transactions.
    """
    user = request.user
    context = {}
    
    # Get user's NFC cards
    cards = NFCCard.objects.filter(user=user).order_by('-issued_date')
    context['cards'] = cards
    
    # Get user's recent transactions
    transactions = CreditTransaction.objects.filter(
        customer=user
    ).order_by('-timestamp')[:10]
    context['transactions'] = transactions
    
    # Calculate total balance and credit statistics
    total_balance = sum(card.balance for card in cards if card.status == 'ACTIVE')
    context['total_balance'] = total_balance
    
    # Get recent credit events
    credit_events = CreditEvent.objects.filter(
        customer=user
    ).order_by('-timestamp')[:5]
    context['credit_events'] = credit_events
    
    # Get pending applications
    pending_applications = CardApplication.objects.filter(
        customer=user, 
        status='PENDING'
    ).order_by('-application_date')
    context['pending_applications'] = pending_applications
    
    return render(request, 'credits/dashboard.html', context)

@login_required
def topup_card(request):
    """
    View for topping up an NFC card.
    """
    user = request.user
    cards = NFCCard.objects.filter(user=user, status='ACTIVE')
    
    if request.method == 'POST':
        card_id = request.POST.get('card_id')
        amount = request.POST.get('amount')
        
        try:
            card = NFCCard.objects.get(id=card_id, user=user)
            amount = float(amount)
            
            if amount <= 0:
                messages.error(request, "Amount must be greater than zero.")
                return render(request, 'credits/topup.html', {'cards': cards})
            
            # Process the top-up
            card.balance += amount
            card.save()
            
            # Record the transaction
            CreditTransaction.objects.create(
                card=card,
                customer=user,
                amount=amount,
                transaction_type='TOPUP',
                description='Card top-up',
                status='COMPLETED'
            )
            
            messages.success(request, f"Successfully topped up {amount} to your card.")
            return redirect('credits:dashboard')
            
        except NFCCard.DoesNotExist:
            messages.error(request, "Invalid card selected.")
        except ValueError:
            messages.error(request, "Invalid amount entered.")
    
    return render(request, 'credits/topup.html', {'cards': cards})

@login_required
def recycle_submit(request):
    """
    View for submitting recycling activities.
    """
    if request.method == 'POST':
        recycle_type = request.POST.get('recycle_type')
        quantity = request.POST.get('quantity')
        
        try:
            quantity = float(quantity)
            
            if quantity <= 0:
                messages.error(request, "Quantity must be greater than zero.")
                return render(request, 'credits/recycle.html')
            
            # Calculate credits based on recycling type and quantity
            credits_earned = 0
            if recycle_type == 'plastic':
                credits_earned = quantity * 5  # 5 credits per kg of plastic
            elif recycle_type == 'paper':
                credits_earned = quantity * 2  # 2 credits per kg of paper
            elif recycle_type == 'glass':
                credits_earned = quantity * 3  # 3 credits per kg of glass
            else:
                credits_earned = quantity * 1  # Default 1 credit per kg
            
            # Create a recycling record
            CreditEvent.objects.create(
                customer=request.user,
                event_type='RECYCLE',
                points_earned=credits_earned,
                description=f"Recycled {quantity}kg of {recycle_type}",
                reference_id=f"REC-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            )
            
            messages.success(request, f"Thank you for recycling! You earned {credits_earned} credits.")
            return redirect('credits:dashboard')
            
        except ValueError:
            messages.error(request, "Invalid quantity entered.")
    
    return render(request, 'credits/recycle.html')

@login_required
def view_vendors(request):
    """
    View list of vendors where credits can be used.
    """
    # This would typically pull from a vendors/partners model
    # For now, we'll use a placeholder list
    vendors = [
        {
            'id': 1,
            'name': 'EcoMart',
            'description': 'Sustainable products store',
            'logo': 'vendor1.jpg',
            'discount_rate': '10%'
        },
        {
            'id': 2,
            'name': 'GreenGrocer',
            'description': 'Organic produce and groceries',
            'logo': 'vendor2.jpg',
            'discount_rate': '5%'
        },
        {
            'id': 3,
            'name': 'RecycleHub',
            'description': 'Recycled goods and upcycled products',
            'logo': 'vendor3.jpg',
            'discount_rate': '15%'
        }
    ]
    
    return render(request, 'credits/vendors.html', {'vendors': vendors})

@login_required
def vendor_products(request, vendor_id):
    """
    View products from a specific vendor.
    """
    # Placeholder products
    products = [
        {
            'id': 1,
            'name': 'Recycled Paper Notebook',
            'description': 'Notebook made from 100% recycled paper',
            'price': 500,
            'credit_price': 50,
            'image': 'product1.jpg'
        },
        {
            'id': 2,
            'name': 'Reusable Water Bottle',
            'description': 'Stainless steel water bottle',
            'price': 1500,
            'credit_price': 150,
            'image': 'product2.jpg'
        },
        {
            'id': 3,
            'name': 'Bamboo Toothbrush',
            'description': 'Eco-friendly bamboo toothbrush',
            'price': 300,
            'credit_price': 30,
            'image': 'product3.jpg'
        }
    ]
    
    vendor = {
        'id': vendor_id,
        'name': f'Vendor {vendor_id}',
        'description': 'Sustainable products vendor',
        'logo': f'vendor{vendor_id}.jpg',
        'discount_rate': '10%'
    }
    
    return render(request, 'credits/vendor_products.html', {
        'vendor': vendor,
        'products': products
    })

@login_required
def buy_product(request, product_id):
    """
    Handle product purchase with credits.
    """
    # In a real implementation, this would fetch the product from a database
    product = {
        'id': product_id,
        'name': f'Product {product_id}',
        'description': 'Eco-friendly product',
        'price': 1000,
        'credit_price': 100,
        'image': f'product{product_id}.jpg'
    }
    
    user = request.user
    cards = NFCCard.objects.filter(user=user, status='ACTIVE')
    
    if request.method == 'POST':
        card_id = request.POST.get('card_id')
        payment_type = request.POST.get('payment_type', 'credits')
        
        try:
            card = NFCCard.objects.get(id=card_id, user=user)
            
            if payment_type == 'credits':
                # Check if user has enough credits
                if card.balance < product['credit_price']:
                    messages.error(request, "Insufficient credits for this purchase.")
                    return render(request, 'credits/buy_product.html', {
                        'product': product,
                        'cards': cards
                    })
                
                # Process the purchase
                card.balance -= product['credit_price']
                card.save()
                
                # Record the transaction
                CreditTransaction.objects.create(
                    card=card,
                    customer=user,
                    amount=product['credit_price'],
                    transaction_type='PURCHASE',
                    description=f"Purchase of {product['name']}",
                    status='COMPLETED'
                )
                
                messages.success(request, f"Successfully purchased {product['name']} for {product['credit_price']} credits.")
            else:
                # This would typically integrate with a payment gateway
                # For now, just record it as a cash purchase
                CreditTransaction.objects.create(
                    card=card,
                    customer=user,
                    amount=product['price'],
                    transaction_type='CASH_PURCHASE',
                    description=f"Cash purchase of {product['name']}",
                    status='COMPLETED'
                )
                
                messages.success(request, f"Successfully purchased {product['name']} for {product['price']} TSh.")
            
            return redirect('credits:dashboard')
            
        except NFCCard.DoesNotExist:
            messages.error(request, "Invalid card selected.")
    
    return render(request, 'credits/buy_product.html', {
        'product': product,
        'cards': cards
    })

@login_required
def credit_history(request):
    """
    View credit transaction history.
    """
    user = request.user
    transactions = CreditTransaction.objects.filter(
        customer=user
    ).order_by('-timestamp')
    
    # Filter by date if specified
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date and end_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            end_date = end_date + timedelta(days=1)  # Include the end date
            
            transactions = transactions.filter(
                timestamp__gte=start_date,
                timestamp__lt=end_date
            )
        except ValueError:
            pass  # Invalid date format, ignore filter
    
    return render(request, 'credits/credit_history.html', {
        'transactions': transactions
    })

@login_required
def order_history(request):
    """
    View order history.
    """
    user = request.user
    orders = CreditTransaction.objects.filter(
        customer=user,
        transaction_type__in=['PURCHASE', 'CASH_PURCHASE']
    ).order_by('-timestamp')
    
    return render(request, 'credits/order_history.html', {
        'orders': orders
    })

@login_required
def recycling_history(request):
    """
    View recycling history.
    """
    user = request.user
    recycling_events = CreditEvent.objects.filter(
        customer=user,
        event_type='RECYCLE'
    ).order_by('-timestamp')
    
    # Calculate totals
    total_points = recycling_events.aggregate(Sum('points_earned'))['points_earned__sum'] or 0
    
    return render(request, 'credits/recycling_history.html', {
        'recycling_events': recycling_events,
        'total_points': total_points
    })

@login_required
def kikapu_card_home(request):
    """
    Home page for Kikapu Card system.
    """
    user = request.user
    cards = NFCCard.objects.filter(user=user).order_by('-issued_at')
    
    # Get any pending applications
    pending_applications = CardApplication.objects.filter(
        user=user,
        status='PENDING'
    ).order_by('-application_date')
    
    return render(request, 'credits/kikapu_card_home.html', {
        'cards': cards,
        'pending_applications': pending_applications
    })

@login_required
def check_eligibility(request):
    """
    Check eligibility for Kikapu Card.
    """
    user = request.user
    
    # Check for existing cards
    existing_cards = NFCCard.objects.filter(user=user).exists()
    
    # For simplicity, consider credit score based on recycling activity
    recycling_events = CreditEvent.objects.filter(
        customer=user,
        event_type='RECYCLE'
    )
    recycling_count = recycling_events.count()
    total_recycling_points = recycling_events.aggregate(Sum('points_change'))['points_change__sum'] or 0
    
    # Simple eligibility check
    is_eligible_prepaid = True  # Everyone is eligible for prepaid
    is_eligible_postpaid = recycling_count >= 3 and total_recycling_points >= 100
    
    eligibility_results = {
        'prepaid': {
            'eligible': is_eligible_prepaid,
            'message': 'You are eligible for a prepaid Kikapu Card.'
        },
        'postpaid': {
            'eligible': is_eligible_postpaid,
            'message': 'You are eligible for a postpaid Kikapu Card with credit.' if is_eligible_postpaid else
                      'You need more recycling activity to qualify for a postpaid card.'
        }
    }
    
    return render(request, 'credits/check_eligibility.html', {
        'existing_cards': existing_cards,
        'recycling_count': recycling_count,
        'total_recycling_points': total_recycling_points,
        'eligibility_results': eligibility_results
    })

@login_required
def apply_prepaid_card(request):
    """
    Apply for a prepaid card.
    """
    user = request.user
    
    if request.method == 'POST':
        # Create a prepaid card application
        application = CardApplication.objects.create(
            user=user,
            card_type='PREPAID',
            status='PENDING',
            application_date=timezone.now()
        )
        
        messages.success(request, "Your prepaid card application has been submitted successfully.")
        return redirect('credits:view_application', app_id=application.id)
    
    return render(request, 'credits/apply_prepaid_card.html')

@login_required
def apply_postpaid_card(request):
    """
    Apply for a postpaid card.
    """
    user = request.user
    
    # Check eligibility first
    recycling_events = CreditEvent.objects.filter(
        customer=user,  # CreditEvent uses 'customer' field, not 'user'
        event_type='RECYCLE'
    )
    recycling_count = recycling_events.count()
    total_recycling_points = recycling_events.aggregate(Sum('points_change'))['points_change__sum'] or 0
    
    is_eligible = recycling_count >= 3 and total_recycling_points >= 100
    
    if not is_eligible:
        messages.error(request, "You are not eligible for a postpaid card at this time.")
        return redirect('credits:check_eligibility')
    
    if request.method == 'POST':
        # Get form data
        occupation = request.POST.get('occupation')
        income = request.POST.get('income')
        id_number = request.POST.get('id_number')
        
        # Create a postpaid card application
        application = CardApplication.objects.create(
            user=user,
            card_type='POSTPAID',
            status='PENDING',
            application_date=timezone.now()
        )
        
        # Store additional information in the notes field
        notes = f"Occupation: {occupation}\nMonthly Income: {income}\nID Number: {id_number}"
        application.notes = notes
        application.save()
        
        messages.success(request, "Your postpaid card application has been submitted successfully.")
        return redirect('credits:view_application', app_id=application.id)
    
    return render(request, 'credits/apply_postpaid.html')

@login_required
def manage_card(request):
    """
    Manage existing cards.
    """
    user = request.user
    cards = NFCCard.objects.filter(user=user).order_by('-issued_date')
    
    if request.method == 'POST':
        card_id = request.POST.get('card_id')
        action = request.POST.get('action')
        
        try:
            card = NFCCard.objects.get(id=card_id, user=user)
            
            if action == 'freeze':
                card.status = 'FROZEN'
                card.save()
                messages.success(request, "Card has been frozen successfully.")
            elif action == 'unfreeze':
                card.status = 'ACTIVE'
                card.save()
                messages.success(request, "Card has been unfrozen successfully.")
            elif action == 'report_lost':
                card.status = 'LOST'
                card.save()
                messages.success(request, "Card has been reported as lost.")
            
            return redirect('credits:manage_card')
            
        except NFCCard.DoesNotExist:
            messages.error(request, "Invalid card selected.")
    
    return render(request, 'credits/manage_card.html', {
        'cards': cards
    })

@login_required
def view_application(request, app_id):
    """
    View details of a card application.
    """
    user = request.user
    
    try:
        application = CardApplication.objects.get(id=app_id, user=user)
        
        return render(request, 'credits/view_application.html', {
            'application': application
        })
        
    except CardApplication.DoesNotExist:
        messages.error(request, "Application not found.")
        return redirect('credits:kikapu_card_home')

@login_required
def confirm_card_payment(request, app_id):
    """
    Confirm payment for a card application.
    """
    user = request.user
    
    try:
        application = CardApplication.objects.get(id=app_id, user=user)
        
        if application.status != 'APPROVED':
            messages.error(request, "This application is not approved for payment.")
            return redirect('credits:view_application', app_id=application.id)
        
        if request.method == 'POST':
            payment_method = request.POST.get('payment_method')
            
            # Process the payment (in a real implementation, this would integrate with a payment gateway)
            application.payment_status = 'PAID'
            application.save()
            
            # Activate the card
            try:
                card = NFCCard.objects.get(application=application)
                card.status = 'ACTIVE'
                card.save()
                
                messages.success(request, "Payment confirmed and card activated successfully.")
                return redirect('credits:kikapu_card_home')
                
            except NFCCard.DoesNotExist:
                messages.error(request, "Card not found for this application.")
        
        return render(request, 'credits/confirm_payment.html', {
            'application': application
        })
        
    except CardApplication.DoesNotExist:
        messages.error(request, "Application not found.")
        return redirect('credits:kikapu_card_home')

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def register_blank_card(request):
    """
    Endpoint for agents to register new blank NFC cards
    
    This is the first step in the professional card lifecycle:
    1. Register blank card (unassigned)
    2. Register customer and assign card (assigned)
    3. Activate card via physical NFC tap (active)
    """
    # DEBUG INFORMATION
    print(f"DEBUG - Request data: {request.data}")
    print(f"DEBUG - User: {request.user}, Is staff: {request.user.is_staff}")
    print(f"DEBUG - Has delivery agent: {hasattr(request.user, 'delivery_agent')}")
    print(f"DEBUG - Request headers: {request.headers}")
    print(f"DEBUG - Expected: A POST request with 'uid' field and proper authentication")
    
    # Check if user is a delivery agent
    if not hasattr(request.user, 'delivery_agent'):
        return Response(
            {"error": "Only authorized delivery agents can register NFC cards"}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Add registered_by information from request if provided
    data = request.data.copy()
    
    # Handle field name mismatch: map cardId to uid if needed
    if 'cardId' in data and 'uid' not in data:
        print(f"DEBUG - Mapping cardId to uid: {data['cardId']}")
        data['uid'] = data['cardId']
        
    # Check if we need to overwrite an existing card
    # Only allow overwriting for unassigned cards to prevent accidental overwrite of active cards
    from credits.models import NFCCard
    if data.get('uid'):
        try:
            existing_card = NFCCard.objects.get(uid=data['uid'])
            if existing_card.status == 'unassigned':
                print(f"DEBUG - Unassigned card with UID {data['uid']} already exists. Adding overwrite=True")
                data['overwrite'] = True
            else:
                print(f"DEBUG - Card with UID {data['uid']} exists but has status '{existing_card.status}', cannot overwrite.")
                return Response({
                    "error": f"Card with UID {data['uid']} is already in use (status: {existing_card.status}). Only unassigned cards can be overwritten."
                }, status=status.HTTP_400_BAD_REQUEST)
        except NFCCard.DoesNotExist:
            # Card doesn't exist, continue with normal registration
            pass
    
    if not data.get('registered_by') and hasattr(request.user, 'delivery_agent'):
        data['registered_by'] = request.user.delivery_agent.agent_id
    
    print(f"DEBUG - Processed data for serializer: {data}")
    serializer = NFCCardRegistrationSerializer(data=data)
    if serializer.is_valid():
        card = serializer.save()
        
        # Return the response with the auto-generated KP number and card details
        return Response({
            "kp_number": card.card_number,
            "status": card.status,
            "issued_at": card.issued_at.isoformat(),
            "message": "Card registered successfully. Status: unassigned."
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def register_customer_with_card(request):
    """
    Endpoint for agents to register a customer and assign a card
    
    This is the second step in the professional card lifecycle:
    1. Register blank card (unassigned)
    2. Register customer and assign card (assigned)
    3. Activate card via physical NFC tap (active)
    """
    # Check if user is a delivery agent
    if not hasattr(request.user, 'delivery_agent'):
        return Response(
            {"error": "Only authorized delivery agents can register customers"}, 
            status=status.HTTP_403_FORBIDDEN
        )
    
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Card assignment request data: {request.data}")
    
    serializer = CustomerAssignmentSerializer(data=request.data)
    if serializer.is_valid():
        result = serializer.save()
        card = result['card']
        user = result['user']
        profile = result['profile']
        
        # Get current balance directly from profile
        current_balance = profile.balance
        logger.warning(f"Current balance from profile: {current_balance}")
        
        # Return the response with customer and card details
        response_data = {
            "message": "Customer registered and card assigned (pending activation)",
            "customer": {
                "id": user.id,
                "name": user.get_full_name(),
                "phoneNumber": user.phoneNumber
            },
            "card": {
                "kp_number": card.card_number,
                "status": card.status,
                "card_type": card.card_type,
                "balance": current_balance
            }
        }
        
        # No transaction info needed since we're using the balance field directly
            
        return Response(response_data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def activate_card(request):
    """
    Endpoint for physically activating a card via NFC tap
    
    This is the final step in the professional card lifecycle:
    1. Register blank card (unassigned)
    2. Register customer and assign card (assigned)
    3. Activate card via physical NFC tap (active)
    """
    serializer = CardActivationSerializer(data=request.data)
    if serializer.is_valid():
        card = serializer.save()
        
        # Return the response with the activated card details
        return Response({
            "success": True,
            "message": "Card activated successfully",
            "kp_number": card.card_number,
            "status": card.status,
            "activated_at": card.activated_at.isoformat(),
            "customer": card.user.get_full_name() if card.user else None,
            "balance": float(card.balance)
        }, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def scan_card(request):
    """
    Endpoint for scanning cards for payment or top-up operations
    
    This endpoint requires cards to be either 'assigned' or 'active' to be valid.
    Unassigned cards will be rejected with a 400 error.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Get card identifier from request
    card_uid = request.data.get('card_uid')
    if not card_uid:
        return Response({
            "success": False,
            "status": "MISSING_CARD_ID",
            "message": "Card UID is required"
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Look up the card
        card = NFCCard.objects.get(uid=card_uid)
        
        # Log card details
        logger.warning(f"Found card: {card.card_number}, status: {card.status}, balance: {card.balance:.2f}")
        
        # Check if card is unassigned - if so, return error
        if card.status == 'unassigned':
            return Response({
                "success": False,
                "status": "UNASSIGNED_CARD",
                "message": "This card cannot be used for payment or adding credit because it is not assigned to any user",
                "card": {
                    "kp_number": card.card_number,
                    "status": card.status
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # For assigned or active cards, return success
        return Response({
            "success": True,
            "message": "Card scanned successfully",
            "kp_number": card.card_number,
            "status": card.status,
            "balance": float(card.balance),
            "customer": card.user.get_full_name() if card.user else None
        }, status=status.HTTP_200_OK)
        
    except NFCCard.DoesNotExist:
        return Response({
            "success": False,
            "status": "CARD_NOT_FOUND",
            "message": "No card found with the provided identifier"
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST', 'GET'])  # Allow GET for debugging
@permission_classes([permissions.AllowAny])  # Allow any user for debugging
def authorize_payment(request):
    """
    Endpoint to check if a card password/PIN matches for authorization
    
    Accepts:
    - card_id or nfc_uid: The card identifier
    - pin: The PIN to verify
    
    Returns success if PIN matches, error otherwise
    """
    import logging
    import traceback
    from registration.models import CustomerProfile
    logger = logging.getLogger(__name__)
    
    # Log detailed information about the request
    logger.warning(f"==== CARD AUTHORIZATION REQUEST ====")
    logger.warning(f"Request path: {request.path}")
    logger.warning(f"Request method: {request.method}")
    logger.warning(f"Request headers: {dict(request.headers)}")
    logger.warning(f"Request data: {request.data}")
    logger.warning(f"Authenticated user: {request.user}")
    logger.warning(f"================================")
    
    # Get card identifier (support both card_id, nfc_uid, and other field name conventions)
    card_id = request.data.get('card_id') or request.data.get('cardId') or request.data.get('card_uid')
    nfc_uid = request.data.get('nfc_uid') or request.data.get('uid')
    pin = request.data.get('pin') or request.data.get('passcode') or request.data.get('password')
    
    # Log all available data fields for debugging
    logger.warning(f"Available fields in request: {list(request.data.keys())}")
    logger.warning(f"Using card_id: {card_id}, nfc_uid: {nfc_uid}, pin: {'*' * len(pin) if pin else None}")
    
    # Additional details for transaction if needed later
    amount = request.data.get('amount', 0)
    agent_id = request.data.get('agent_id')
    
    # Always return a 200 OK response, but with appropriate status indicators
    if not pin:
        return Response({
            "success": False,
            "status": "MISSING_PIN",
            "message": "PIN is required"
        }, status=status.HTTP_200_OK)
        
    if not (card_id or nfc_uid):
        return Response({
            "success": False,
            "status": "MISSING_CARD_ID",
            "message": "Card identifier (card_id or nfc_uid) is required"
        }, status=status.HTTP_200_OK)
    
    try:
        # Try to find the card with more flexible lookup
        if nfc_uid:
            card = NFCCard.objects.get(uid=nfc_uid)
        else:
            # Try various ways to lookup the card
            try:
                # First try by card_number (KP number)
                card = NFCCard.objects.get(card_number=card_id)
            except NFCCard.DoesNotExist:
                # If that fails, try by UID
                logger.warning(f"Card not found by card_number, trying UID lookup: {card_id}")
                card = NFCCard.objects.get(uid=card_id)
            
        # Check if card is assigned to a user
        if not card.user:
            logger.warning(f"Card {card.card_number} is not assigned to any user")
            return Response({
                "success": False,
                "status": "UNASSIGNED_CARD",
                "message": "Card is not assigned to any user", 
                "card": {
                    "kp_number": card.card_number,
                    "status": card.status
                }
            }, status=status.HTTP_200_OK)
                           
        # Get the customer profile
        try:
            profile = CustomerProfile.objects.get(user=card.user)
            
            # First, check if the card has a passcode directly
            if card.passcode and pin == card.passcode:
                logger.warning(f"Card passcode verified successfully for card {card.card_number}")
                return Response({
                    "success": True,
                    "message": "Card passcode verified successfully",
                    "card": {
                        "kp_number": card.card_number,
                        "status": card.status,
                        "balance": card.balance
                    },
                    "customer": {
                        "name": card.user.get_full_name(),
                        "phone": card.user.phoneNumber
                    }
                }, status=status.HTTP_200_OK)
                
            # If no card passcode or it didn't match, try the profile PIN
            # Verify PIN - verify_pin returns a tuple (success, message)
            success, message = profile.verify_pin(pin)
            
            if success:
                logger.warning(f"Profile PIN verified successfully for card {card.card_number}")
                return Response({
                    "success": True,
                    "message": "PIN verified successfully",
                    "card": {
                        "kp_number": card.card_number,
                        "status": card.status,
                        "balance": card.balance
                    },
                    "customer": {
                        "name": card.user.get_full_name(),
                        "phone": card.user.phoneNumber
                    }
                }, status=status.HTTP_200_OK)
            else:
                # Handle the specific case where PIN is not set
                if message == "PIN not set":
                    logger.warning(f"PIN not set for card {card.card_number}")
                    return Response({
                        "success": False,
                        "status": "PIN_NOT_SET",
                        "message": "This card requires PIN initialization before use. Please contact an agent to set up your PIN.",
                        "card": {
                            "kp_number": card.card_number,
                            "status": card.status
                        }
                    }, status=status.HTTP_200_OK)  # Using 200 OK with status indicator
                else:
                    # Handle standard invalid PIN case
                    logger.warning(f"Invalid PIN for card {card.card_number}: {message}")
                    return Response({
                        "success": False,
                        "status": "INVALID_PIN", 
                        "message": "The PIN you entered is incorrect. Please try again.",
                        "card": {
                            "kp_number": card.card_number,
                            "status": card.status
                        }
                    }, status=status.HTTP_200_OK)  # Using 200 OK with status indicator
                
        except CustomerProfile.DoesNotExist:
            logger.warning(f"No customer profile found for user {card.user.id}")
            return Response({
                "success": False,
                "status": "PROFILE_NOT_FOUND",
                "message": "Customer profile not found. Please contact support.",
                "card": {
                    "kp_number": card.card_number,
                    "status": card.status
                }
            }, status=status.HTTP_200_OK)
    
    except NFCCard.DoesNotExist:
        # Log more details about the error
        logger.warning(f"Card not found with identifier: {card_id or nfc_uid}")
        
        # Query existing cards to help with debugging
        all_cards = NFCCard.objects.all().values('uid', 'card_number')[:5]
        logger.warning(f"Sample of existing cards: {list(all_cards)}")
        
        return Response({
            "success": False,
            "status": "CARD_NOT_FOUND",
            "message": f"No card found with identifier: {card_id or nfc_uid}"
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error during payment authorization: {str(e)}")
        # Add traceback for debugging
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        return Response({
            "success": False,
            "status": "SERVER_ERROR",
            "message": "An error occurred while processing your request. Please try again later.",
            "debug_info": str(e) if settings.DEBUG else None
        }, status=status.HTTP_200_OK)


@api_view(['POST', 'GET'])  # Allow GET for debugging
@permission_classes([permissions.AllowAny])  # Allow any user for debugging
def process_payment(request):
    """
    Process a payment transaction after successful PIN/passcode verification
    
    Accepts:
    - card_id or nfc_uid: The card identifier
    - amount: The amount to charge (positive value)
    - description: Optional description of the transaction
    - merchant_id: Optional ID of the merchant/vendor
    
    Returns transaction details and updated balance
    """
    import logging
    import traceback
    from decimal import Decimal
    from credits.models import NFCCard, CreditTransaction
    logger = logging.getLogger(__name__)
    
    # Log detailed information about the request
    logger.warning(f"==== PAYMENT PROCESSING REQUEST ====")
    logger.warning(f"Request path: {request.path}")
    logger.warning(f"Request method: {request.method}")
    logger.warning(f"Request headers: {dict(request.headers)}")
    logger.warning(f"Request data: {request.data}")
    logger.warning(f"Authenticated user: {request.user}")
    logger.warning(f"================================")
    
    # Get payment details (supporting multiple field name conventions)
    card_id = request.data.get('card_id') or request.data.get('cardId') or request.data.get('card_uid')
    nfc_uid = request.data.get('nfc_uid') or request.data.get('uid')
    amount_str = request.data.get('amount') or '0'
    description = request.data.get('description') or 'Card payment'
    merchant_id = request.data.get('merchant_id') or request.data.get('vendorId')
    
    # Convert amount to Decimal
    try:
        amount = Decimal(str(amount_str))
    except:
        logger.warning(f"Invalid amount format: {amount_str}")
        return Response({
            "success": False,
            "status": "INVALID_AMOUNT",
            "message": "Invalid amount format. Please provide a valid number."
        }, status=status.HTTP_200_OK)
    
    # Validate inputs
    if amount <= 0:
        return Response({
            "success": False,
            "status": "INVALID_AMOUNT",
            "message": "Amount must be greater than zero."
        }, status=status.HTTP_200_OK)
        
    if not (card_id or nfc_uid):
        return Response({
            "success": False,
            "status": "MISSING_CARD_ID",
            "message": "Card identifier (card_id or nfc_uid) is required."
        }, status=status.HTTP_200_OK)
    
    try:
        # Try to find the card with flexible lookup
        if nfc_uid:
            card = NFCCard.objects.get(uid=nfc_uid)
        else:
            # Try various ways to lookup the card
            try:
                # First try by card_number (KP number)
                card = NFCCard.objects.get(card_number=card_id)
            except NFCCard.DoesNotExist:
                # If that fails, try by UID
                logger.warning(f"Card not found by card_number, trying UID lookup: {card_id}")
                card = NFCCard.objects.get(uid=card_id)
        
        # Check if card is active
        if card.status != 'active':
            logger.warning(f"Card {card.card_number} is not active. Current status: {card.status}")
            return Response({
                "success": False,
                "status": "INACTIVE_CARD",
                "message": f"This card cannot be used for payments. Current status: {card.get_status_display()}.",
                "card": {
                    "kp_number": card.card_number,
                    "status": card.status
                }
            }, status=status.HTTP_200_OK)
        
        # Check if card is locked
        if card.is_locked:
            logger.warning(f"Card {card.card_number} is locked")
            return Response({
                "success": False,
                "status": "LOCKED_CARD",
                "message": "This card is locked. Please contact support to unlock it.",
                "card": {
                    "kp_number": card.card_number,
                    "status": card.status
                }
            }, status=status.HTTP_200_OK)
            
        # Check if card is expired
        if card.is_expired():
            logger.warning(f"Card {card.card_number} is expired")
            return Response({
                "success": False,
                "status": "EXPIRED_CARD",
                "message": "This card has expired. Please renew or replace it.",
                "card": {
                    "kp_number": card.card_number,
                    "status": card.status,
                    "expire_date": card.expire_date.isoformat() if card.expire_date else None
                }
            }, status=status.HTTP_200_OK)
        
        # Check for sufficient balance (for prepaid cards)
        if card.card_type == 'PREPAID' and card.balance < amount:
            logger.warning(f"Insufficient balance on card {card.card_number}. Balance: {card.balance}, Amount: {amount}")
            return Response({
                "success": False,
                "status": "INSUFFICIENT_BALANCE",
                "message": "Insufficient balance on card.",
                "card": {
                    "kp_number": card.card_number,
                    "balance": float(card.balance),
                    "amount": float(amount),
                    "shortfall": float(amount - card.balance)
                }
            }, status=status.HTTP_200_OK)
            
        # Check for available credit (for postpaid cards)
        if card.card_type == 'POSTPAID':
            available_credit = card.get_available_credit()
            if available_credit < amount:
                logger.warning(f"Insufficient credit on postpaid card {card.card_number}. Available: {available_credit}, Amount: {amount}")
                return Response({
                    "success": False,
                    "status": "CREDIT_LIMIT_EXCEEDED",
                    "message": "This transaction would exceed your available credit limit.",
                    "card": {
                        "kp_number": card.card_number,
                        "credit_limit": float(card.credit_limit),
                        "available": float(available_credit),
                        "amount": float(amount)
                    }
                }, status=status.HTTP_200_OK)
        
        # Process the payment
        try:
            # Create transaction record first
            transaction = CreditTransaction.objects.create(
                card=card,
                amount=-amount,  # Negative because it's a deduction
                type='PURCHASE',
                description=description
            )
            
            # Update card balance
            card.balance -= amount
            card.last_used_at = timezone.now()
            card.save()
            
            # Record merchant information if provided
            if merchant_id:
                # This assumes you have a way to track merchant-specific transactions
                # You might want to add a MerchantTransaction model or similar
                logger.warning(f"Payment processed for merchant ID: {merchant_id}")
            
            # Log success
            logger.warning(f"Payment of {amount} successfully processed for card {card.card_number}. New balance: {card.balance}")
            
            # Return successful response
            return Response({
                "success": True,
                "status": "PAYMENT_SUCCESSFUL",
                "message": "Payment processed successfully.",
                "transaction": {
                    "id": transaction.id,
                    "amount": float(amount),
                    "timestamp": transaction.timestamp.isoformat(),
                    "description": transaction.description
                },
                "card": {
                    "kp_number": card.card_number,
                    "new_balance": float(card.balance),
                    "previous_balance": float(card.balance + amount)
                },
                "customer": {
                    "name": card.user.get_full_name() if card.user else "Unknown",
                    "phone": card.user.phoneNumber if card.user else None
                }
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error processing payment: {str(e)}")
            logger.error(traceback.format_exc())
            return Response({
                "success": False,
                "status": "TRANSACTION_ERROR",
                "message": "An error occurred while processing the payment.",
                "debug_info": str(e) if settings.DEBUG else None
            }, status=status.HTTP_200_OK)
    
    except NFCCard.DoesNotExist:
        # Card not found
        logger.warning(f"Card not found with identifier: {card_id or nfc_uid}")
        return Response({
            "success": False,
            "status": "CARD_NOT_FOUND",
            "message": f"No card found with the provided identifier."
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        # General error
        logger.error(f"Error in payment processing: {str(e)}")
        logger.error(traceback.format_exc())
        return Response({
            "success": False,
            "status": "SERVER_ERROR",
            "message": "An error occurred while processing your request.",
            "debug_info": str(e) if settings.DEBUG else None
        }, status=status.HTTP_200_OK)
