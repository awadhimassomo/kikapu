from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.utils.text import slugify
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db import transaction
from django.urls import reverse
from datetime import datetime, timedelta
from decimal import Decimal
import json
import uuid
import random
import logging
import time

from rest_framework.decorators import api_view
from rest_framework.response import Response
from .serializers import ProductDetailSerializer
from django.core.serializers.json import DjangoJSONEncoder

from .models import (
    Purchase, Product, Cart, CartItem, Category, Order, OrderItem, ProductImage, 
    ProductProcessingMethod, RelatedProduct, DeliveryAddress, DeliveryGroup, GroupOrder, ProductAssociation,
    ScheduledDelivery
)

from .group_delivery_utils import (
    create_delivery_group, get_group_summary, add_order_to_group,
    remove_order_from_group, recalculate_group_delivery_fees
)

from .cart_utils import get_or_create_cart, get_guest_cart_from_session
from .delivery_utils import calculate_order_delivery_fee

# Create your views here.

logger = logging.getLogger(__name__)

def marketplace(request):
    # Get products with availability flag
    products = Product.objects.filter(is_available=True).select_related('category')
    
    # Get featured products (just the most recent ones since we don't have a featured flag)
    featured_products = products.order_by('-created_at')[:8]
    
    # Get products categorized by category for easy display
    categories = Category.objects.all()
    
    # Fetch processing types for the product popup
    processing_types = []
    try:
        # Get the processing choices from the Product model
        processing_types = list(dict(Product.PROCESSING_CHOICES).items())
    except Exception as e:
        # Fallback to a default if there's an error
        processing_types = [('NONE', 'None/Raw'), ('CLEANED', 'Cleaned'), ('PROCESSED', 'Processed')]
    
    # Fetch comprehensive market research data
    market_data = {
        'price_data': [],
        'commodities': [],
        'regions': [],
        'latest_prices': {},
        'price_trends': {},
        'has_data': False,
    }
    
    try:
        # Import here to avoid circular imports
        from market_research.models import MarketPriceResearch, Commodity, Market
        from django.db.models import Avg, Max, Min, Count, F
        from django.db.models.functions import TruncMonth, TruncWeek
        from collections import defaultdict
        import datetime
        
        # Get commodities data
        commodities = Commodity.objects.all().order_by('name')
        for commodity in commodities:
            market_data['commodities'].append({
                'id': commodity.id,
                'name': commodity.name,
                'category': commodity.category,
                'unit': commodity.default_unit,
                'image_url': commodity.image_url if hasattr(commodity, 'image_url') else None,
            })
        
        # Get regions data (markets)
        markets = Market.objects.filter(is_active=True).order_by('name')
        for market in markets:
            market_data['regions'].append({
                'id': market.id,
                'name': market.name,
                'region': market.region if hasattr(market, 'region') else '',
                'latitude': market.latitude if hasattr(market, 'latitude') else None,
                'longitude': market.longitude if hasattr(market, 'longitude') else None,
            })
        
        # Get the latest market price entries (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        market_prices = MarketPriceResearch.objects.filter(
            date_observed__gte=thirty_days_ago
        ).order_by('-date_observed')
        
        # Process price data for different views
        product_price_map = defaultdict(list)  # For tracking price trends by product
        
        # Format individual price data entries
        for price in market_prices[:20]:  # Only process the most recent 20 entries for the list view
            # Look for a matching product in our marketplace by name similarity
            product_name = price.product_name.lower()
            matching_products = products.filter(name__icontains=product_name)
            
            # Convert price to TSh (using 2500 TSh per USD as per memory)
            price_in_tsh = int(float(price.price) * 2500)
            
            # For all prices, track in the product_price_map for trend analysis
            product_price_map[price.product_name].append({
                'price': price_in_tsh,
                'date': price.date_observed,
            })
            
            # Only include in the main list if there's a matching product
            if matching_products.exists():
                market_data['price_data'].append({
                    'product_name': price.product_name,
                    'source_name': price.source_name,
                    'price': f"TSh {price_in_tsh:,}",  # Format with commas for thousands
                    'unit': price.unit,
                    'date': price.date_observed.strftime('%d %b %Y'),
                    'region': price.region if hasattr(price, 'region') else '',
                    'matching_product_id': matching_products.first().id,
                })
                
                # Track the latest price for each product
                if price.product_name not in market_data['latest_prices']:
                    market_data['latest_prices'][price.product_name] = {
                        'price': f"TSh {price_in_tsh:,}",
                        'raw_price': price_in_tsh,
                        'unit': price.unit,
                        'source': price.source_name,
                        'date': price.date_observed.strftime('%d %b %Y'),
                    }
        
        # Calculate price trends (are prices rising or falling?)
        for product_name, prices in product_price_map.items():
            if len(prices) >= 2:
                # Sort by date
                sorted_prices = sorted(prices, key=lambda x: x['date'])
                
                # Calculate trend
                earliest_price = sorted_prices[0]['price']
                latest_price = sorted_prices[-1]['price']
                
                price_diff = latest_price - earliest_price
                percent_change = (price_diff / earliest_price) * 100 if earliest_price > 0 else 0
                
                # Get average of last 7 days if we have enough data
                recent_prices = [p['price'] for p in sorted_prices if p['date'] > timezone.now() - timedelta(days=7)]
                avg_recent_price = sum(recent_prices) / len(recent_prices) if recent_prices else latest_price
                
                # Store the trend data
                market_data['price_trends'][product_name] = {
                    'trend': 'up' if price_diff > 0 else 'down' if price_diff < 0 else 'stable',
                    'percent_change': round(percent_change, 1),
                    'avg_price': f"TSh {int(avg_recent_price):,}",
                }
        
        # Set the has_data flag if we have any data
        market_data['has_data'] = len(market_data['price_data']) > 0 or len(market_data['commodities']) > 0
        
    except Exception as e:
        logger.exception(f"Error fetching market research data: {str(e)}")
    
    context = {
        'products': products[:12],  # Limit to 12 products for the main listing
        'featured_products': featured_products,
        'categories': categories,
        'processing_types': processing_types,
        # Market research data
        'market_price_data': market_data['price_data'],
        'market_commodities': market_data['commodities'],
        'market_regions': market_data['regions'],
        'market_latest_prices': market_data['latest_prices'],
        'market_price_trends': market_data['price_trends'],
        'has_market_data': market_data['has_data'],
        'title': 'Fresh Farm Products - KIKAPU Marketplace',
        'description': 'Shop for fresh, local, and sustainable farm products including vegetables, fruits, grains and more.',
    }
    
    return render(request, 'marketplace/marketplace.html', context)

@login_required
def view_cart(request):
    """
    View the current user's shopping cart.
    """
    # Get or create the user's cart
    cart = get_or_create_cart(request.user)
    
    # Get all cart items with their product details
    cart_items = cart.items.select_related('product').all()
    
    # Check for tourism bookings in session
    tourism_bookings = request.session.get('tourism_bookings', [])
    
    # Calculate cart totals including tourism bookings
    cart_total = sum(item.product.price * item.quantity for item in cart_items)
    tourism_total = Decimal('0.00')
    if tourism_bookings:
        tourism_total = sum(Decimal(str(booking['total_price'])) for booking in tourism_bookings)
    
    # Calculate combined total
    subtotal = cart_total + tourism_total
    delivery_fee = Decimal('5000.00')  # Default delivery fee
    final_total = subtotal + delivery_fee
    
    # Get recommended products
    recommended_products = []
    if cart_items:
        # Try to get product recommendations based on cart items
        product_ids = [item.product.id for item in cart_items]
        
        # Check for associations from Apriori algorithm
        associations = ProductAssociation.objects.filter(
            product__id__in=product_ids
        ).select_related('recommendation').order_by('-confidence')[:4]
        
        # If we have associations, use them
        if associations:
            recommended_products = [assoc.recommendation for assoc in associations]
        else:
            # Fallback to same category products
            categories = [item.product.category_id for item in cart_items]
            recommended_products = Product.objects.filter(
                category__id__in=categories
            ).exclude(
                id__in=product_ids
            ).order_by('?')[:4]
    
    context = {
        'cart_items': cart_items,
        'tourism_bookings': tourism_bookings,
        'cart_total': cart_total,
        'tourism_total': tourism_total,
        'subtotal': subtotal,
        'delivery_fee': delivery_fee,
        'final_total': final_total,
        'recommended_products': recommended_products,
        'title': 'Shopping Cart',
    }
    return render(request, 'marketplace/cart.html', context)

@login_required
@require_POST
def add_to_cart(request, product_id):
    """
    Add a product to the cart.
    """
    product = get_object_or_404(Product, id=product_id)
    quantity = int(request.POST.get('quantity', 1))
    processing_method = request.POST.get('processing_method', 'NONE')
    
    # Enhanced logging for cart debugging with request metadata
    client_ip = request.META.get('REMOTE_ADDR', 'unknown')
    user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
    referer = request.META.get('HTTP_REFERER', 'unknown')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    logger.info(
        f"CART ADD REQUEST: user={request.user.id}, product={product_id}, "
        f"quantity={quantity}, ip={client_ip}, ajax={is_ajax}, "
        f"user_agent={user_agent}, referer={referer}"
    )
    
    # Check if product is available
    if not product.is_available:
        messages.error(request, f"Sorry, {product.name} is currently not available.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('marketplace:marketplace')))
    
    # Check if we have enough stock
    if product.stock_quantity < quantity:
        messages.error(request, f"Sorry, only {product.stock_quantity} units of {product.name} are available.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('marketplace:marketplace')))
    
    # Get or create the user's cart
    cart = get_or_create_cart(request.user)
    
    # Debug: Log the cart state before adding
    cart_items_before = list(cart.items.values('product_id', 'quantity', 'processing_method'))
    logger.info(f"CART DEBUG: Cart before adding item - {cart_items_before}")
    
    # Check if the item is already in the cart
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={
            'quantity': quantity,
            'processing_method': processing_method
        }
    )
    
    if not created:
        # If the item already exists, update the quantity
        cart_item.quantity += quantity
        
        # Check if updated quantity exceeds stock
        if cart_item.quantity > product.stock_quantity:
            cart_item.quantity = product.stock_quantity
            messages.warning(request, f"Quantity adjusted to maximum available stock ({product.stock_quantity}).")
        
        try:
            # Try to update processing_method if the field exists
            cart_item.processing_method = processing_method
        except:
            # Field doesn't exist, just ignore
            pass
        
        cart_item.save()
        messages.success(request, f"Updated quantity of {product.name} in your cart.")
    else:
        # Item was newly created
        messages.success(request, f"Added {product.name} to your cart.")
    
    # Debug: Log the cart state after adding
    cart_items_after = list(cart.items.values('product_id', 'quantity', 'processing_method'))
    logger.info(f"CART DEBUG: Cart after adding item - {cart_items_after}")
    
    # Check for AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        cart_count = cart.items.aggregate(total_quantity=Sum('quantity'))['total_quantity'] or 0
        return JsonResponse({
            'success': True,
            'message': f"Added {product.name} to your cart.",
            'cart_count': cart_count
        })
    
    # Redirect back to the referring page or to the marketplace
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('marketplace:marketplace')))

@login_required
@require_POST
def update_cart_item(request, item_id):
    """
    Update the quantity of a cart item.
    """
    # Get the cart item
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    
    # Check if this is an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # Get the action and quantity
    action = request.POST.get('action')
    if action:
        # Handle increment/decrement actions
        if action == 'increase':
            cart_item.quantity += 1
        elif action == 'decrease':
            cart_item.quantity -= 1
    else:
        # Direct quantity update
        cart_item.quantity = int(request.POST.get('quantity', 1))
    
    # Check if quantity is zero or negative
    removed = False
    if cart_item.quantity <= 0:
        # Remove the item if quantity is zero or negative
        product_name = cart_item.product.name
        cart_item.delete()
        if not is_ajax:
            messages.success(request, f"Removed {product_name} from your cart.")
        removed = True
    else:
        # Update the quantity
        if cart_item.quantity > cart_item.product.stock_quantity:
            cart_item.quantity = cart_item.product.stock_quantity
            if not is_ajax:
                messages.warning(request, f"Quantity adjusted to maximum available stock ({cart_item.product.stock_quantity}).")
        
        cart_item.save()
        if not is_ajax:
            messages.success(request, f"Updated quantity of {cart_item.product.name}.")
    
    # If it's an AJAX request, return a JSON response
    if is_ajax:
        # Recalculate cart totals
        cart = cart_item.cart if not removed else get_or_create_cart(request.user)
        cart_items = cart.items.select_related('product').all()
        cart_total = sum(item.product.price * item.quantity for item in cart_items)
        delivery_fee = Decimal('5000.00')  # Default delivery fee
        final_total = cart_total + delivery_fee
        
        return JsonResponse({
            'success': True,
            'removed': removed,
            'quantity': 0 if removed else cart_item.quantity,
            'subtotal': 0 if removed else cart_item.product.price * cart_item.quantity,
            'cart_total': cart_total,
            'final_total': final_total,
            'cart_count': cart_items.count()
        })
    
    # For regular form submissions, redirect back to the cart page
    return redirect('marketplace:view_cart')

@login_required
@require_POST
def remove_from_cart(request, item_id):
    """
    Remove an item from the cart.
    """
    # Get the cart item
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    product_name = cart_item.product.name
    
    # Delete the cart item
    cart_item.delete()
    messages.success(request, f"Removed {product_name} from your cart.")
    
    return redirect('marketplace:view_cart')

@login_required
@require_POST
def clear_cart(request):
    """
    Clear all items from the cart.
    """
    # Get the user's cart
    cart = get_or_create_cart(request.user)
    
    # Delete all cart items
    cart.items.all().delete()
    messages.success(request, "Your cart has been cleared.")
    
    return redirect('marketplace:view_cart')

@login_required
def deep_clean_cart(request):
    """
    Special debug view to completely rebuild the cart from scratch
    with detailed tracing of the process.
    """
    from django.db import connection

    logger.info("=== STARTING DEEP CART CLEANING ===")
    logger.info(f"User: {request.user.id} ({request.user.username})")
    
    # Step 1: Get info about any existing carts
    existing_carts = Cart.objects.filter(user=request.user)
    cart_count = existing_carts.count()
    logger.info(f"Found {cart_count} existing carts")
    
    for i, cart in enumerate(existing_carts):
        logger.info(f"Cart #{i+1} (ID: {cart.id}) has {cart.items.count()} items:")
        for item in cart.items.all():
            logger.info(f"  - {item.id}: {item.quantity}x {item.product.name}")
    
    # Step 2: Manually delete all carts using raw SQL to avoid signals
    with connection.cursor() as cursor:
        # First delete all cart items
        cursor.execute(
            "DELETE FROM marketplace_cartitem WHERE cart_id IN (SELECT id FROM marketplace_cart WHERE user_id = %s)",
            [request.user.id]
        )
        deleted_items = cursor.rowcount
        
        # Then delete the carts
        cursor.execute(
            "DELETE FROM marketplace_cart WHERE user_id = %s",
            [request.user.id]
        )
        deleted_carts = cursor.rowcount
    
    logger.info(f"Deleted {deleted_items} cart items and {deleted_carts} carts using direct SQL")
    
    # Step 3: Create a new cart directly with SQL to avoid any signal processing
    with connection.cursor() as cursor:
        from django.utils import timezone
        now = timezone.now().isoformat()
        
        cursor.execute(
            """
            INSERT INTO marketplace_cart (user_id, created_at, updated_at)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            [request.user.id, now, now]
        )
        
        new_cart_id = cursor.fetchone()[0]
    
    logger.info(f"Created new cart with ID {new_cart_id} using direct SQL")
    
    # Step 4: Verify the new cart state
    new_cart = Cart.objects.get(id=new_cart_id)
    logger.info(f"New cart verified: ID={new_cart.id}, Items={new_cart.items.count()}")
    
    for item in new_cart.items.all():
        logger.warning(f"UNEXPECTED ITEM FOUND: {item.id}: {item.quantity}x {item.product.name}")
    
    # Update session if needed
    if 'cart_items' in request.session:
        old_count = request.session['cart_items'] 
        request.session['cart_items'] = 0
        logger.info(f"Updated session cart count from {old_count} to 0")
        request.session.save()
    
    logger.info("=== DEEP CART CLEANING COMPLETE ===")
    
    messages.success(request, f"Deep cleaned cart. Old carts ({cart_count}) and their items completely removed. New cart created with ID {new_cart_id}.")
    return redirect('marketplace:debug_cart')

@login_required
def monitor_cart_creation(request):
    """
    Special diagnostic view to monitor new cart creation and detect automatic additions.
    This view creates a fresh cart and checks if any items were automatically added.
    """
    from django.db import connection
    from django.utils import timezone
    
    logger.info("=== CART CREATION MONITORING ===")
    logger.info(f"User: {request.user.id} ({request.user.username})")
    
    # Delete existing cart to start fresh
    existing_carts = Cart.objects.filter(user=request.user)
    cart_count = existing_carts.count()
    logger.info(f"Found {cart_count} existing carts to be deleted")
    
    for i, cart in enumerate(existing_carts):
        logger.info(f"Cart #{i+1} (ID: {cart.id}) has {cart.items.count()} items:")
        for item in cart.items.all():
            logger.info(f"  - {item.id}: {item.quantity}x {item.product.name}")
    
    existing_carts.delete()
    logger.info(f"Deleted {cart_count} existing carts")
    
    # Create a new cart using direct SQL to bypass all signal handlers
    with connection.cursor() as cursor:
        now = timezone.now().isoformat()
        cursor.execute(
            """
            INSERT INTO marketplace_cart (user_id, created_at, updated_at)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            [request.user.id, now, now]
        )
        new_cart_id = cursor.fetchone()[0]
    
    logger.info(f"Created fresh cart with ID {new_cart_id} using direct SQL")
    
    # Give a moment for any signal handlers to possibly add items
    import time
    time.sleep(1)
    
    # Check if any items were automatically added
    new_cart = Cart.objects.get(id=new_cart_id)
    items = list(new_cart.items.all())
    
    if items:
        logger.error(f"DETECTED AUTO-ADDITION: {len(items)} items were automatically added to new cart!")
        for item in items:
            logger.error(f"AUTO-ADDED ITEM: {item.id}: {item.quantity}x {item.product.name}")
            
        # Clean these items
        new_cart.items.all().delete()
        logger.info("Auto-added items have been removed")
        
        # Check for signals or post_save hooks on Cart model that might be adding items
        logger.info("Potential issues: Check for signals in apps.py or models.py files")
    else:
        logger.info("SUCCESS: No items were automatically added to the new cart")
    
    # Update session if needed
    if 'cart_items' in request.session:
        old_count = request.session['cart_items'] 
        request.session['cart_items'] = 0
        logger.info(f"Updated session cart count from {old_count} to 0")
        request.session.save()
    
    logger.info("=== CART CREATION MONITORING COMPLETE ===")
    
    messages.success(request, f"Fresh cart created with ID {new_cart_id}. Check the logs for detailed diagnostic information.")
    return redirect('marketplace:view_cart')

@login_required
def checkout(request):
    """
    Checkout process for placing an order.
    """
    # Get the user's cart
    cart = get_or_create_cart(request.user)
    
    # Get all cart items with their product details
    cart_items = cart.items.select_related('product').all()
    
    # Check if cart is empty - Return JSON response for AJAX requests
    if not cart_items:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'Your cart is empty. Please add some products before checkout.',
                'redirect': reverse('marketplace:marketplace')
            })
        messages.warning(request, "Your cart is empty. Please add some products before checkout.")
        return redirect('marketplace:marketplace')
    
    # Check if user has a customer profile, if not create one
    try:
        customer = request.user.customer_profile
    except:
        # Create a basic customer profile for the user
        from registration.models import CustomerProfile
        customer = CustomerProfile.objects.create(
            user=request.user,
            card_type='PREPAID'  # Default to prepaid
        )
        messages.info(request, "A customer profile has been created for you. Please complete your profile details later.")
    
    # Get customer's delivery addresses
    delivery_addresses = DeliveryAddress.objects.filter(customer=customer)
    default_address = delivery_addresses.filter(is_default=True).first()
    
    # Get any tourism bookings from session
    tourism_bookings = request.session.get('tourism_bookings', [])
    
    # Calculate cart totals
    cart_total = sum(item.product.price * item.quantity for item in cart_items)
    tourism_total = Decimal('0.00')
    if tourism_bookings:
        tourism_total = sum(Decimal(str(booking['total_price'])) for booking in tourism_bookings)
    
    subtotal = cart_total + tourism_total
    delivery_fee = Decimal('5000.00')  # Default delivery fee
    final_total = subtotal + delivery_fee
    
    # Calculate minimum date for scheduled delivery (tomorrow)
    min_delivery_date = (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Check if this is an AJAX request asking for validation
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.GET.get('validate'):
        step = request.GET.get('step', '2')
        
        # For step 2, validate if address is selected
        if step == '2' and request.GET.get('check_address'):
            if not default_address and not delivery_addresses.exists():
                return JsonResponse({
                    'success': False, 
                    'error': 'Please add a delivery address to continue.',
                    'show_address_modal': True,
                    'current_step': 2
                })
            return JsonResponse({'success': True})
        
        return JsonResponse({'success': True})
    
    context = {
        'cart_items': cart_items,
        'cart_total': cart_total,
        'delivery_fee': delivery_fee,
        'final_total': final_total,
        'addresses': delivery_addresses,
        'default_address': default_address,
        'min_delivery_date': min_delivery_date,  # Add minimum date for the date picker
        'title': 'Checkout',
        # Add a flag to check if an address exists for front-end validation
        'has_address': default_address is not None or delivery_addresses.exists(),
    }
    
    return render(request, 'marketplace/checkout.html', context)

@login_required
def debug_cart(request):
    """
    Debug view to diagnose cart issues
    """
    # Check if we need to reset the cart
    if request.GET.get('reset', ''):
        # Delete all carts for this user
        user_carts = Cart.objects.filter(user=request.user)
        cart_count = user_carts.count()
        user_carts.delete()
        logger.warning(f"CART DEBUG: Deleted {cart_count} carts for user {request.user.id}")
        messages.success(request, f"Deleted {cart_count} carts")
        
        # Create a fresh cart
        new_cart = Cart.objects.create(user=request.user)
        logger.info(f"CART DEBUG: Created fresh cart {new_cart.id} for user {request.user.id}")
        messages.success(request, f"Created fresh cart (ID: {new_cart.id})")
        return redirect('marketplace:debug_cart')
    
    # Get all carts for this user
    carts = Cart.objects.filter(user=request.user)
    carts_data = []
    
    # Collect cart data
    for cart in carts:
        items = cart.items.select_related('product').all()
        cart_data = {
            'id': cart.id,
            'created_at': cart.created_at,
            'updated_at': cart.updated_at,
            'item_count': cart.item_count(),
            'items': [
                {
                    'id': item.id,
                    'product': item.product.name,
                    'quantity': item.quantity,
                    'processing_method': item.processing_method,
                    'created_at': item.created_at
                } for item in items
            ]
        }
        carts_data.append(cart_data)
    
    # Also log the data for analysis
    logger.info(f"CART DEBUG: User {request.user.id} has {len(carts_data)} carts")
    for i, cart_data in enumerate(carts_data):
        logger.info(f"CART DEBUG: Cart #{i+1} (ID: {cart_data['id']}) has {len(cart_data['items'])} items:")
        for item in cart_data['items']:
            logger.info(f"  - {item['quantity']}x {item['product']}")
    
    context = {
        'carts_data': carts_data,
        'title': 'Cart Diagnostics',
        'active_cart_count': len(carts_data)
    }
    
    return render(request, 'marketplace/debug_cart.html', context)

@login_required
def api_cart_summary(request):
    """
    API endpoint to get the current cart summary.
    Used for auto-initializing cart data in the frontend.
    """
    try:
        # Get user's cart or create a new one if it doesn't exist
        cart = get_or_create_cart(request.user)
        
        # Count items in the cart
        cart_count = cart.item_count()
        
        # Calculate subtotal
        subtotal = sum(item.product.price * item.quantity for item in cart.items.all())
        
        # Return JSON response with cart data
        return JsonResponse({
            'success': True,
            'cart_count': cart_count,
            'subtotal': float(subtotal),
            'cart_id': cart.id
        })
    except Exception as e:
        logger.error(f"Error fetching cart summary: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e),
            'cart_count': 0
        }, status=500)

@api_view(['GET'])
def refresh_cart_summary(request):
    """
    API endpoint to get the current cart summary with fresh data.
    This is used to update the order summary on the delivery step
    and solves the issue of stale cart data, especially for guest users.
    
    For guest users, this endpoint also synchronizes the session data between
    guest_cart_items (used in cart updates) and guest_info['cart_items'] (used in checkout) 
    to ensure consistent data across checkout steps.
    """
    try:
        # Set a timestamp to help track cart updates
        current_time = int(time.time())
        request.session['cart_timestamp'] = current_time
        
        if request.user.is_authenticated:
            # Get authenticated user's cart
            cart = get_or_create_cart(request.user)
            cart_items = list(cart.items.select_related('product').all())
            
            # Format cart items for the response
            items_data = []
            for item in cart_items:
                image_url = None
                if item.product.images.exists():
                    image = item.product.images.first()
                    if image and hasattr(image, 'image') and image.image:
                        image_url = image.image.url
                
                items_data.append({
                    'id': item.id,
                    'product_id': item.product.id,
                    'name': item.product.name,
                    'quantity': item.quantity,
                    'price': float(item.product.price),
                    'subtotal': float(item.product.price * item.quantity),
                    'image_url': image_url
                })
            
            # Calculate totals
            subtotal = sum(item.product.price * item.quantity for item in cart_items)
            
        else:
            # For guest users, get cart from session
            guest_cart = get_guest_cart_from_session(request)
            
            # Directly query GuestCartItem if it exists (check if the model exists first)
            try:
                from django.apps import apps
                GuestCartItem = apps.get_model('marketplace', 'GuestCartItem')
                if GuestCartItem:
                    # Check if we have a guest cart ID in the session
                    guest_cart_id = request.session.get('guest_cart_id')
                    if guest_cart_id:
                        # Get fresh cart items directly from the database
                        fresh_items = GuestCartItem.objects.filter(cart_id=guest_cart_id)
                        if fresh_items.exists():
                            logger.info(f"Using fresh GuestCartItem data for cart {guest_cart_id}")
                            # Replace session cart data with fresh database data
                            guest_cart = {}
                            for item in fresh_items:
                                guest_cart[str(item.product_id)] = {
                                    'quantity': item.quantity,
                                    'price': str(item.product.price),
                                    'name': item.product.name
                                }
                            # Update session with fresh data
                            request.session['guest_cart_items'] = guest_cart
                            request.session.modified = True
                            logger.info(f"Updated session with fresh cart data: {len(guest_cart)} items")
            except Exception as e:
                logger.warning(f"Error trying to get fresh GuestCartItems: {e}")
            
            # Format cart items for the response
            items_data = []
            for product_id, item_data in guest_cart.items():
                price = Decimal(item_data.get('price', '0'))
                quantity = item_data.get('quantity', 0)
                
                items_data.append({
                    'id': product_id,
                    'product_id': product_id,
                    'name': item_data.get('name', 'Product'),
                    'quantity': quantity,
                    'price': float(price),
                    'subtotal': float(price * quantity),
                    'image_url': None  # Guest cart doesn't store image URLs
                })
            
            # Calculate subtotal
            subtotal = sum(
                Decimal(item_data.get('price', '0')) * item_data.get('quantity', 0)
                for item_data in guest_cart.values()
            )
            
            # CRITICAL: Update the guest checkout info data structure if it exists
            # This ensures the delivery step gets fresh cart data
            if 'guest_info' in request.session:
                logger.info("Updating guest_info with fresh cart data")
                guest_info = request.session['guest_info']
                guest_info['cart_items'] = guest_cart
                request.session['guest_info'] = guest_info
                request.session.modified = True
        
        # Set default delivery fee
        delivery_fee = Decimal('5000.00')
        vat_amount = subtotal * Decimal('0.18')
        final_total = subtotal + delivery_fee + vat_amount
        
        return JsonResponse({
            'success': True,
            'cart_items': items_data,
            'subtotal': float(subtotal),
            'delivery_fee': float(delivery_fee),
            'vat_amount': float(vat_amount),
            'final_total': float(final_total),
            'timestamp': current_time
        })
        
    except Exception as e:
        logger.exception(f"Error in refresh_cart_summary: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def refresh_order_summary(request):
    """
    View that returns just the order summary HTML for AJAX requests.
    This is used to refresh the order summary without reloading the entire page.
    """
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request'}, status=400)
    
    try:
        # Get cart data based on user authentication status
        if request.user.is_authenticated:
            # Get authenticated user's cart
            cart = get_or_create_cart(request.user)
            cart_items = cart.items.select_related('product').all()
            cart_total = sum(item.product.price * item.quantity for item in cart_items)
        else:
            # Get guest cart from session
            guest_cart = get_guest_cart_from_session(request)
            
            # If guest_info has more up-to-date cart data, use it
            if 'guest_info' in request.session and 'cart_items' in request.session['guest_info']:
                guest_info_cart = request.session['guest_info']['cart_items']
                if guest_info_cart and len(guest_info_cart) > 0:
                    logger.info("Using cart items from guest_info for order summary")
                    guest_cart = guest_info_cart
            
            # Convert guest cart to a list that template can iterate through
            cart_items = []
            cart_total = Decimal('0')
            
            for product_id, item_data in guest_cart.items():
                try:
                    product = Product.objects.get(id=product_id)
                    quantity = item_data.get('quantity', 0)
                    price = Decimal(item_data.get('price', '0'))
                    subtotal = price * quantity
                    
                    cart_items.append({
                        'id': product_id,
                        'product': product,
                        'quantity': quantity,
                        'subtotal': subtotal
                    })
                    
                    cart_total += subtotal
                except Product.DoesNotExist:
                    logger.warning(f"Product ID {product_id} not found for order summary")
        
        # Set default delivery fee and calculate totals
        delivery_fee = Decimal('2000.00')  # Default delivery fee
        vat_amount = (cart_total + delivery_fee) * Decimal('0.18')
        final_total = cart_total + delivery_fee + vat_amount
        
        # Render just the order summary template with necessary context
        context = {
            'cart_items': cart_items,
            'cart_total': cart_total,
            'delivery_fee': delivery_fee,
            'vat_amount': vat_amount,
            'final_total': final_total
        }
        
        html_content = render(request, 'marketplace/partials/checkout/order_summary.html', context).content.decode('utf-8')
        return JsonResponse({'success': True, 'html': html_content})
        
    except Exception as e:
        logger.exception(f"Error refreshing order summary: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@require_POST
def place_order(request):
    """
    Place an order with items from the user's cart.
    """
    # Check if this is an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # Get the user's cart
    cart = get_or_create_cart(request.user)
    
    # Get all cart items with their product details
    cart_items = cart.items.select_related('product').all()
    
    # Check if cart is empty
    if not cart_items:
        if is_ajax:
            return JsonResponse({
                'success': False,
                'error': 'Your cart is empty. Please add some products before checkout.',
                'redirect': reverse('marketplace:marketplace')
            })
        messages.warning(request, "Your cart is empty. Please add some products before checkout.")
        return redirect('marketplace:marketplace')
    
    # Get customer profile
    customer = request.user.customer_profile
    
    # Get delivery address
    address_id = request.POST.get('address_id')
    if not address_id:
        if is_ajax:
            return JsonResponse({
                'success': False,
                'error': 'Please select a delivery address to complete your order.',
                'show_address_modal': True,
                'current_step': 2  # Stay on delivery step
            })
        messages.error(request, "Please select a delivery address to complete your order.")
        return redirect('marketplace:checkout')
    
    try:
        # Use a transaction to ensure atomicity - either complete order creation and cart clearing or neither
        with transaction.atomic():
            delivery_address = get_object_or_404(DeliveryAddress, id=address_id, customer=customer)
            
            # Get delivery method
            delivery_method = request.POST.get('delivery_method', 'STANDARD')
            
            # Get schedule type if applicable
            schedule_type = request.POST.get('schedule_type', 'ONE_TIME')
            
            # Set delivery fee based on method and schedule type
            if delivery_method == 'EXPRESS':
                delivery_fee = Decimal('10000.00')  # Express delivery fee
            elif delivery_method == 'SCHEDULED':
                # Check if this is a subscription box (which has FREE delivery)
                if schedule_type == 'SUBSCRIPTION':
                    delivery_fee = Decimal('0.00')  # Free delivery for subscription boxes
                else:
                    delivery_fee = Decimal('7000.00')  # Regular scheduled delivery fee
            else:
                delivery_fee = Decimal('5000.00')  # Standard delivery fee
            
            # Get any tourism bookings from session
            tourism_bookings = request.session.get('tourism_bookings', [])
            
            # Calculate cart totals
            cart_total = sum(item.product.price * item.quantity for item in cart_items)
            tourism_total = Decimal('0.00')
            if tourism_bookings:
                tourism_total = sum(Decimal(str(booking['total_price'])) for booking in tourism_bookings)
            
            subtotal = cart_total + tourism_total
            
            # Create order number
            order_number = f"ORD{timezone.now().strftime('%Y%m%d')}{random.randint(1000,9999)}"
            
            # First check if this is a group order
            join_group_code = request.POST.get('join_group_code')
            is_group_order = join_group_code and len(join_group_code.strip()) > 0
            
            # Create the order with basic information
            order = Order.objects.create(
                customer=customer,
                order_number=order_number,
                shipping_address=f"{delivery_address.address_line_1}, {delivery_address.city}, {delivery_address.region}",
                delivery_address=delivery_address,
                delivery_fee=delivery_fee,
                subtotal=subtotal,
                total_amount=subtotal + delivery_fee,
                latitude=delivery_address.latitude,
                longitude=delivery_address.longitude,
                delivery_option=delivery_method,
                estimated_delivery_time=timezone.now() + timedelta(days=1),  # Default to next day delivery
            )
            
            # Handle scheduled delivery if selected
            if delivery_method == 'SCHEDULED':
                # ... existing scheduled delivery code ...
                pass
            
            # Create order items from cart items
            for cart_item in cart_items:
                try:
                    OrderItem.objects.create(
                        order=order,
                        product=cart_item.product,
                        quantity=cart_item.quantity,
                        price=cart_item.product.price,
                        processing_method=getattr(cart_item, 'processing_method', 'NONE')
                    )
                except Exception:
                    # Fallback in case processing_method doesn't exist
                    OrderItem.objects.create(
                        order=order,
                        product=cart_item.product,
                        quantity=cart_item.quantity,
                        price=cart_item.product.price,
                        processing_method='NONE'  # Default to no processing
                    )
                
                # Update product stock
                product = cart_item.product
                product.stock_quantity -= cart_item.quantity
                product.save(update_fields=['stock_quantity'])
            
            # Clear the cart immediately after order creation
            cart_items.delete()
            cart.delete()  # Delete the cart entirely to clear cart history
            
            # Only process group delivery if join_group_code is provided
            if is_group_order:
                try:
                    group = DeliveryGroup.objects.get(code=join_group_code, is_active=True)
                    # Add order to the group
                    add_order_to_group(order, group)
                    if is_ajax:
                        success_message = f"Your order has been added to group {join_group_code}!"
                    else:
                        messages.success(request, f"Your order has been added to group {join_group_code}!")
                except DeliveryGroup.DoesNotExist:
                    if is_ajax:
                        error_message = f"Group with code {join_group_code} not found or is no longer active."
                    else:
                        messages.error(request, f"Group with code {join_group_code} not found or is no longer active.")
        
        # Order successfully created
        if is_ajax:
            return JsonResponse({
                'success': True,
                'message': 'Your order has been placed successfully!',
                'redirect': reverse('marketplace:order_success', kwargs={'order_id': order.id})
            })
            
        # Non-Ajax response
        messages.success(request, "Your order has been placed successfully!")
        return redirect('marketplace:order_success', order_id=order.id)
    
    except Exception as e:
        # Log the error for debugging
        logger.error(f"Error placing order: {str(e)}")
        
        if is_ajax:
            return JsonResponse({
                'success': False,
                'error': f"An error occurred while processing your order: {str(e)}",
                'current_step': 2  # Stay on delivery step
            })
            
        messages.error(request, f"An error occurred while processing your order. Please try again.")
        return redirect('marketplace:checkout')

def _update_estimated_delivery_time(order, delivery_date, time_slot):
    """Helper function to update the estimated delivery time based on date and time slot"""
    # Map time slots to hours
    time_slot_hours = {
        'MORNING': 10,    # 10 AM
        'AFTERNOON': 14,  # 2 PM
        'EVENING': 18     # 6 PM
    }
    
    delivery_hour = time_slot_hours.get(time_slot, 12)
    
    # Combine date and time
    order.estimated_delivery_time = datetime.combine(
        delivery_date, 
        datetime.min.time(),
        timezone.get_current_timezone()
    ).replace(hour=delivery_hour)
    
    order.save(update_fields=['estimated_delivery_time'])

# Temporary view to handle order_success URL without parameters
def order_success_redirect(request):
    """
    Temporary view to handle direct access to order_success without an order_id.
    This redirects users back to the marketplace instead of showing an error.
    """
    messages.info(request, "Please complete your order first to access the order success page.")
    return redirect('marketplace:marketplace')

@login_required
def order_success(request, order_id):
    """
    Display order success page.
    """
    # Get the order
    order = get_object_or_404(Order, id=order_id, customer=request.user.customer_profile)
    
    # Check if order belongs to a delivery group
    in_group = order.delivery_group is not None
    
    context = {
        'order': order,
        'in_group': in_group,
        'order_items': order.items.all(),
        'title': 'Order Confirmation',
    }
    
    return render(request, 'marketplace/order_success.html', context)

@login_required
def create_group_view(request):
    """View for creating a new delivery group"""
    if request.method == 'POST':
        # Get form data
        delivery_date_str = request.POST.get('delivery_date')
        time_slot = request.POST.get('time_slot')
        
        # Validate data
        try:
            delivery_date = datetime.strptime(delivery_date_str, '%Y-%m-%d').date()
            
            # Check if date is not in the past
            if delivery_date < timezone.now().date():
                messages.error(request, "Delivery date cannot be in the past.")
                return redirect('marketplace:create_group')
                
            # Check if time slot is valid
            if time_slot not in dict(DeliveryGroup.TIME_SLOT_CHOICES):
                messages.error(request, "Invalid time slot selected.")
                return redirect('marketplace:create_group')
                
            # Create the group
            group = create_delivery_group(
                leader=request.user.customerprofile,
                delivery_date=delivery_date,
                time_slot=time_slot
            )
            
            messages.success(
                request, 
                f"Group created successfully! Your group code is {group.code}."
            )
            return redirect('marketplace:group_detail', code=group.code)
            
        except ValueError:
            messages.error(request, "Invalid date format. Please use YYYY-MM-DD.")
            return redirect('marketplace:create_group')
            
    # GET request - show form
    tomorrow = (timezone.now() + timedelta(days=1)).date()
    context = {
        'min_date': tomorrow.strftime('%Y-%m-%d'),
        'time_slots': DeliveryGroup.TIME_SLOT_CHOICES
    }
    return render(request, 'marketplace/create_group.html', context)


@login_required
def group_detail_view(request, code):
    """View details of a delivery group"""
    group = get_object_or_404(DeliveryGroup, code=code)
    
    # Get group summary
    summary = get_group_summary(group)
    
    # Check if user is the leader or a member
    user_profile = request.user.customerprofile
    is_leader = (group.leader == user_profile)
    
    # Check if user has an order in this group
    user_order = None
    for member in summary['members']:
        if member.get('is_leader') and is_leader:
            user_order = member
            break
    
    context = {
        'group': group,
        'summary': summary,
        'is_leader': is_leader,
        'user_order': user_order,
        'whatsapp_share_link': group.get_whatsapp_share_link()
    }
    
    return render(request, 'marketplace/group_detail.html', context)


@login_required
def join_group_view(request, code):
    """View for joining an existing delivery group"""
    group = get_object_or_404(DeliveryGroup, code=code)
    
    # Check if group is still active
    if not group.is_active or group.is_expired():
        messages.error(request, "This group is no longer active.")
        return redirect('marketplace:marketplace')
    
    # Check if user already has an order in this group
    user_profile = request.user.customerprofile
    if GroupOrder.objects.filter(group=group, member=user_profile).exists():
        messages.info(request, "You're already a member of this group.")
        return redirect('marketplace:group_detail', code=group.code)
    
    if request.method == 'POST':
        # Process joining the group with the current cart
        try:
            with transaction.atomic():
                # Get user's cart
                cart = get_object_or_404(Cart, user=request.user)
                
                # Check if cart has items
                if not cart.items.exists():
                    messages.error(request, "Your cart is empty. Add some products first.")
                    return redirect('marketplace:view_cart')
                
                # Create an order from the cart
                order = Order.objects.create(
                    customer=user_profile,
                    order_number=f"ORD-{uuid.uuid4().hex[:8].upper()}",
                    shipping_address=request.POST.get('shipping_address', ''),
                    delivery_option='GROUP',
                    delivery_date=group.delivery_date,
                    time_slot=group.time_slot,
                    subtotal=cart.total(),
                    total_amount=cart.total()  # Will be updated when adding to group
                )
                
                # Create order items from cart items
                for cart_item in cart.items.all():
                    OrderItem.objects.create(
                        order=order,
                        product=cart_item.product,
                        quantity=cart_item.quantity,
                        price=cart_item.product.price,
                        processing_method=cart_item.processing_method
                    )
                
                # Add order to the group
                group_order = add_order_to_group(order, group)
                
                # Clear the cart
                cart.items.all().delete()
                
                messages.success(request, "You've successfully joined the group delivery!")
                return redirect('marketplace:group_detail', code=group.code)
                
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('marketplace:join_group', code=code)
    
    # GET request - show form
    context = {
        'group': group,
        'delivery_addresses': DeliveryAddress.objects.filter(customer=user_profile)
    }
    return render(request, 'marketplace/join_group.html', context)


@login_required
def add_member_to_group_view(request, code):
    """View for group leader to add a member to their group"""
    group = get_object_or_404(DeliveryGroup, code=code)
    
    # Verify user is the group leader
    if request.user.customerprofile != group.leader:
        messages.error(request, "Only the group leader can add members.")
        return redirect('marketplace:group_detail', code=code)
    
    if request.method == 'POST':
        # Get form data
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        
        # Validate data
        if not all([name, phone, address]):
            messages.error(request, "All fields are required.")
            return redirect('marketplace:add_member_to_group', code=code)
        
        try:
            with transaction.atomic():
                # Create a new order (will be linked to group leader temporarily)
                order = Order.objects.create(
                    customer=request.user.customerprofile,  # Leader's profile
                    order_number=f"ORD-{uuid.uuid4().hex[:8].upper()}",
                    shipping_address=address,
                    delivery_option='GROUP',
                    delivery_date=group.delivery_date,
                    time_slot=group.time_slot,
                    subtotal=0,  # Will be updated as products are added
                    total_amount=0  # Will be updated as products are added
                )
                
                # Add order to the group as an order added by leader
                group_order = add_order_to_group(
                    order=order,
                    delivery_group=group,
                    added_by_leader=True,
                    name=name,
                    phone=phone
                )
                
                messages.success(
                    request, 
                    f"Added {name} to your group. Now add some products to their order."
                )
                return redirect('marketplace:add_products_to_member_order', group_code=code, order_id=order.id)
        
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('marketplace:add_member_to_group', code=code)
    
    # GET request - show form
    context = {
        'group': group
    }
    return render(request, 'marketplace/add_member_to_group.html', context)


@login_required
def add_products_to_member_order_view(request, group_code, order_id):
    """View for adding products to an order the leader created for a member"""
    group = get_object_or_404(DeliveryGroup, code=group_code)
    order = get_object_or_404(Order, id=order_id)
    
    # Verify user is the group leader
    if request.user.customerprofile != group.leader:
        messages.error(request, "Only the group leader can add products to member orders.")
        return redirect('marketplace:group_detail', code=group_code)
    
    # Verify order belongs to this group
    try:
        group_order = GroupOrder.objects.get(group=group, order=order, added_by_leader=True)
    except GroupOrder.DoesNotExist:
        messages.error(request, "Invalid order for this group.")
        return redirect('marketplace:group_detail', code=group_code)
    
    if request.method == 'POST':
        # Process the selected products
        product_data = json.loads(request.POST.get('product_data', '[]'))
        
        if not product_data:
            messages.error(request, "No products selected.")
            return redirect('marketplace:add_products_to_member_order', group_code=group_code, order_id=order_id)
        
        try:
            with transaction.atomic():
                subtotal = 0
                
                for item in product_data:
                    product_id = item.get('product_id')
                    quantity = item.get('quantity', 1)
                    processing_method = item.get('processing_method', 'NONE')
                    
                    # Get the product
                    product = get_object_or_404(Product, id=product_id)
                    
                    # Create the order item
                    order_item = OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=quantity,
                        price=product.price,
                        processing_method=processing_method
                    )
                    
                    # Add to subtotal
                    subtotal += order_item.subtotal
                
                # Update order subtotal and total
                order.subtotal = subtotal
                order.save()
                
                # Recalculate group delivery fees
                recalculate_group_delivery_fees(group)
                
                messages.success(
                    request,
                    f"Products added to {group_order.name}'s order successfully."
                )
                return redirect('marketplace:group_detail', code=group_code)
                
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('marketplace:add_products_to_member_order', group_code=group_code, order_id=order_id)
    
    # GET request - show product selection form
    context = {
        'group': group,
        'order': order,
        'group_order': GroupOrder.objects.get(group=group, order=order),
        'categories': Category.objects.all(),
        'products': Product.objects.filter(is_available=True)
    }
    return render(request, 'marketplace/add_products_to_member_order.html', context)


@login_required
def my_groups_view(request):
    """View for listing a user's groups (led and joined)"""
    user_profile = request.user.customerprofile
    
    # Get groups where user is leader
    led_groups = DeliveryGroup.objects.filter(leader=user_profile).order_by('-created_at')
    
    # Get groups where user is a member
    joined_group_orders = GroupOrder.objects.filter(
        member=user_profile,
        added_by_leader=False
    ).select_related('group').order_by('-created_at')
    
    context = {
        'led_groups': led_groups,
        'joined_group_orders': joined_group_orders
    }
    return render(request, 'marketplace/my_groups.html', context)


@login_required
@require_POST
def close_group_view(request, code):
    """View for closing a group delivery"""
    group = get_object_or_404(DeliveryGroup, code=code)
    
    # Verify user is the group leader
    if request.user.customerprofile != group.leader:
        messages.error(request, "Only the group leader can close this group.")
        return redirect('marketplace:group_detail', code=code)
    
    group.is_active = False
    group.save(update_fields=['is_active'])
    
    messages.success(request, "Group has been closed successfully.")
    return redirect('marketplace:group_detail', code=code)


@login_required
@require_POST
def remove_group_order_view(request, group_code, order_id):
    """View for removing an order from a group"""
    group = get_object_or_404(DeliveryGroup, code=group_code)
    order = get_object_or_404(Order, id=order_id)
    
    # Get the group order
    group_order = get_object_or_404(GroupOrder, group=group, order=order)
    
    # Verify user is authorized (either the leader or the order owner)
    is_leader = (request.user.customerprofile == group.leader)
    is_member = (not group_order.added_by_leader and request.user.customerprofile == group_order.member)
    
    if not (is_leader or is_member):
        messages.error(request, "You are not authorized to remove this order.")
        return redirect('marketplace:group_detail', code=group_code)
    
    # Remove the order from the group
    remove_order_from_group(group_order)
    
    messages.success(request, "Order removed from the group successfully.")
    return redirect('marketplace:group_detail', code=group_code)

@login_required
def order_history(request):
    """
    Display the order history for the authenticated user.
    """
    # Get the customer profile for the current user
    customer = request.user.customer_profile
    
    # Get all orders for this customer, ordered by most recent first
    orders = Order.objects.filter(customer=customer).order_by('-created_at')
    
    # Group orders by status for easier display
    processing_orders = orders.filter(status__in=['PENDING', 'PROCESSING', 'PACKED'])
    shipped_orders = orders.filter(status='SHIPPED')
    delivered_orders = orders.filter(status='DELIVERED')
    cancelled_orders = orders.filter(status='CANCELLED')
    
    context = {
        'orders': orders,
        'processing_orders': processing_orders,
        'shipped_orders': shipped_orders,
        'delivered_orders': delivered_orders,
        'cancelled_orders': cancelled_orders,
        'title': 'Order History',
    }
    
    return render(request, 'marketplace/order_history.html', context)

@login_required
def business_product_list(request):
    """
    Display a list of products for a business user to manage.
    """
    # Check if user has a business profile
    if not hasattr(request.user, 'business_profile'):
        messages.error(request, "You need a business profile to access this page.")
        return redirect('marketplace:marketplace')
    
    # Get the business profile
    business = request.user.business_profile
    
    # Get all products for this business
    products = Product.objects.filter(seller=business).order_by('-created_at')
    
    # Get product stats (could be expanded later)
    product_stats = {}
    for product in products:
        # Get number of times this product has been ordered
        order_count = OrderItem.objects.filter(product=product).count()
        
        # Get total quantity sold
        total_sold = OrderItem.objects.filter(product=product).aggregate(
            total=Sum('quantity')
        )['total'] or 0
        
        product_stats[product.id] = {
            'order_count': order_count,
            'total_sold': total_sold
        }
    
    context = {
        'products': products,
        'product_stats': product_stats,
        'title': 'Manage Products',
    }
    
    return render(request, 'marketplace/business/product_list.html', context)

@login_required
def business_product_add(request):
    """
    Add a new product for a business user.
    """
    # Check if user has a business profile
    if not hasattr(request.user, 'business_profile'):
        messages.error(request, "You need a business profile to access this page.")
        return redirect('marketplace:marketplace')
    
    # Get the business profile
    business = request.user.business_profile
    
    if request.method == 'POST':
        # Process form data
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = request.POST.get('price')
        stock_quantity = request.POST.get('stock_quantity')
        category_id = request.POST.get('category')
        is_available = 'is_available' in request.POST
        unit_measurement = request.POST.get('unit_measurement', 'KG')
        
        # Validate required fields
        if not all([name, price, stock_quantity, category_id]):
            messages.error(request, "Please fill all required fields.")
            return redirect('marketplace:business_product_add')
        
        try:
            # Get the category
            category = Category.objects.get(id=category_id)
            
            # Create the product
            product = Product.objects.create(
                seller=business,
                name=name,
                description=description,
                price=Decimal(price),
                stock_quantity=int(stock_quantity),
                category=category,
                is_available=is_available,
                unit_measurement=unit_measurement,
                slug=slugify(name)
            )
            
            # Handle product images
            for img in request.FILES.getlist('images'):
                ProductImage.objects.create(
                    product=product,
                    image=img
                )
            
            messages.success(request, f"Product '{name}' has been added successfully.")
            return redirect('marketplace:business_product_list')
            
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return redirect('marketplace:business_product_add')
    
    # GET request - show form
    context = {
        'categories': Category.objects.all(),
        'title': 'Add New Product',
    }
    
    return render(request, 'marketplace/business/product_add.html', context)

@login_required
def category_add(request):
    """
    View to add a new product category
    """
    # Get parent categories for dropdown
    parent_categories = Category.objects.filter(parent__isnull=True)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        parent_id = request.POST.get('parent')
        
        # Basic validation
        if not name:
            messages.error(request, 'Category name is required')
            return render(request, 'marketplace/category_add.html', {
                'parent_categories': parent_categories
            })
        
        # Create a slug from the name
        slug = slugify(name)
        
        # Check if slug already exists
        if Category.objects.filter(slug=slug).exists():
            messages.error(request, 'A category with this name already exists')
            return render(request, 'marketplace/category_add.html', {
                'parent_categories': parent_categories
            })
        
        # Create the category
        category = Category(
            name=name,
            slug=slug,
            description=description
        )
        
        # Add parent if selected
        if parent_id:
            try:
                parent = Category.objects.get(id=parent_id)
                category.parent = parent
            except Category.DoesNotExist:
                pass
        
        category.save()
        
        messages.success(request, f'Category "{name}" has been created successfully')
        return redirect('marketplace:business_product_list')
    
    return render(request, 'marketplace/category_add.html', {
        'parent_categories': parent_categories,
        'title': 'Add New Category'
    })

@login_required
def manage_related_products(request):
    """
    View for managing manually defined related product relationships.
    Allows business users to create, view, and delete related product connections.
    """
    # Check if user has a business profile
    if not hasattr(request.user, 'business_profile'):
        messages.error(request, "You need a business profile to access this feature.")
        return redirect('marketplace:marketplace')
    
    business = request.user.business_profile
    business_products = Product.objects.filter(business=business)
    
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        related_product_id = request.POST.get('related_product_id')
        relationship_type = request.POST.get('relationship_type', 'complementary')
        relevance_score = request.POST.get('relevance_score', 10)
        notes = request.POST.get('notes', '')
        
        # Handle delete request
        if 'delete_relation' in request.POST:
            relation_id = request.POST.get('relation_id')
            try:
                relation = RelatedProduct.objects.get(
                    id=relation_id, 
                    product__business=business
                )
                relation.delete()
                messages.success(request, "Related product connection removed successfully.")
            except RelatedProduct.DoesNotExist:
                messages.error(request, "Related product connection not found.")
            
            return redirect('marketplace:manage_related_products')
        
        # Validate form data
        try:
            product = business_products.get(id=product_id)
            related_product = Product.objects.get(id=related_product_id)
            
            # Prevent self-relations
            if product.id == related_product.id:
                messages.error(request, "A product cannot be related to itself.")
                return redirect('marketplace:manage_related_products')
            
            # Create new relation or update if exists
            relation, created = RelatedProduct.objects.update_or_create(
                product=product,
                related_product=related_product,
                defaults={
                    'relationship_type': relationship_type,
                    'relevance_score': relevance_score,
                    'notes': notes
                }
            )
            
            if created:
                messages.success(request, f"Related product {related_product.name} added to {product.name}.")
            else:
                messages.success(request, f"Related product relationship updated.")
                
        except Product.DoesNotExist:
            messages.error(request, "Invalid product selection.")
        except Exception as e:
            messages.error(request, f"Error adding related product: {str(e)}")
    
    # Get all related product relationships for this business's products
    related_products = RelatedProduct.objects.filter(
        product__business=business
    ).select_related('product', 'related_product')
    
    # Get all products that could be related (including from other businesses)
    all_products = Product.objects.filter(is_available=True).order_by('category__name', 'name')
    
    context = {
        'business_products': business_products,
        'all_products': all_products,
        'related_products': related_products,
        'title': 'Manage Related Products'
    }
    
    return render(request, 'marketplace/manage_related_products.html', context)

def get_processing_types():
    """Fetches all processing types from the database."""
    return ProductProcessingMethod.objects.values_list('method', flat=True).distinct()

@api_view(['GET'])
def product_detail_api(request, product_id):
    """
    API endpoint to fetch product details including processing methods
    """
    logger.info(f"API request received for product_id={product_id} from user={request.user.id if request.user.is_authenticated else 'anonymous'}")
    
    try:
        # Get the product with its related data
        product = Product.objects.select_related('category').prefetch_related(
            'processing_methods', 'images').get(id=product_id)
        
        # Log successful product retrieval
        logger.info(f"Successfully retrieved product: {product.name} (id={product_id})")
        
        # Serialize the product data
        serializer = ProductDetailSerializer(product)
        
        return Response(serializer.data)
    except Product.DoesNotExist:
        logger.error(f"Product not found with id={product_id}")
        return Response(
            {"error": "Product not found"}, 
            status=404
        )
    except Exception as e:
        # Log any unexpected errors in detail
        logger.exception(f"Error fetching product_id={product_id}: {str(e)}")
        return Response(
            {"error": "An error occurred while fetching product details"}, 
            status=500
        )


def cart_count(request):
    """Return just the cart count as JSON for updating cart badges.
    
    This is a lightweight endpoint specifically for cart badge updates.
    """
    try:
        # For authenticated users
        if request.user.is_authenticated:
            try:
                cart = Cart.objects.get(user=request.user)
                count = cart.items.count()
            except Cart.DoesNotExist:
                count = 0
        # For guest users
        else:
            # Try to get from DB first if we have a UUID
            guest_cart_uuid = request.session.get('guest_cart_uuid')
            if guest_cart_uuid:
                try:
                    guest_cart = GuestCart.objects.get(cart_uuid=guest_cart_uuid)
                    count = guest_cart.items.count()
                except GuestCart.DoesNotExist:
                    count = 0
            else:
                # Fall back to session data
                guest_cart_data = request.session.get('guest_cart_items', [])
                count = len(guest_cart_data)
        
        # Return the count as JSON
        return JsonResponse({
            'count': count,
            'success': True
        })
    except Exception as e:
        logger.exception(f"Error in cart_count: {str(e)}")
        return JsonResponse({
            'error': str(e),
            'count': 0,
            'success': False
        }, status=400)
