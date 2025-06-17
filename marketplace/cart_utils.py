from django.contrib import messages
from .models import Cart, CartItem, Product
from .delivery_utils import calculate_delivery_fee, get_delivery_eta
from decimal import Decimal
import logging

# Set up logging
logger = logging.getLogger(__name__)

def get_or_create_cart(user):
    """
    Gets an existing cart for a user or creates a new one if none exists.
    
    Args:
        user: User object to get/create cart for
        
    Returns:
        Cart: The user's cart
    """
    if not user.is_authenticated:
        raise ValueError("Cannot create cart for unauthenticated user")
    
    # Debug: Check if multiple carts exist for this user
    all_carts = Cart.objects.filter(user=user)
    if all_carts.count() > 1:
        logger.warning(f"CART ISSUE: Multiple carts found for user {user.id}. Found {all_carts.count()} carts")
        # Delete all but the newest cart to fix the issue
        newest_cart = all_carts.order_by('-created_at').first()
        Cart.objects.filter(user=user).exclude(id=newest_cart.id).delete()
        logger.info(f"CART ISSUE: Removed duplicate carts, kept cart {newest_cart.id}")
        return newest_cart
    
    try:
        # First try to get existing cart
        return Cart.objects.get(user=user)
    except Cart.DoesNotExist:
        # If no cart exists, create one with direct SQL to bypass any signals
        from django.db import connection
        from django.utils import timezone
        
        # Create a new cart using direct SQL to avoid potential signal handlers
        with connection.cursor() as cursor:
            now = timezone.now().isoformat()
            cursor.execute(
                """
                INSERT INTO marketplace_cart (user_id, created_at, updated_at)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                [user.id, now, now]
            )
            new_cart_id = cursor.fetchone()[0]
        
        # Get the freshly created cart
        new_cart = Cart.objects.get(id=new_cart_id)
        logger.info(f"CART DEBUG: Created new cart for user {user.id} using direct SQL to prevent auto-additions")
        
        # Verify the cart is empty
        if new_cart.items.exists():
            logger.warning(f"CART DEBUG: Cart {new_cart.id} has items immediately after creation! Cleaning up...")
            new_cart.items.all().delete()
            
        return new_cart

def migrate_guest_cart_to_user(request):
    """
    Migrates items from a guest cart (stored in session) to a logged-in user's cart.
    This function is called during login to ensure users don't lose their cart items.
    
    Args:
        request: The HTTP request object containing session data and user info
        
    Returns:
        bool: True if migration was successful or attempted, False otherwise
    """
    if not request.user.is_authenticated:
        logger.warning("Attempted to migrate cart for unauthenticated user")
        return False
    
    # Check if there are items in the session cart
    session_cart_items = request.session.get('guest_cart_items', {})
    
    if not session_cart_items:
        # No guest cart items to migrate
        logger.debug(f"No guest cart items to migrate for user {request.user.id}")
        return False
    
    try:
        # Get or create user cart
        cart, created = Cart.objects.get_or_create(user=request.user)
        items_added = 0
        
        # Migrate each item from session to the user's cart
        for product_id_str, item_data in session_cart_items.items():
            try:
                product_id = int(product_id_str)
                quantity = item_data.get('quantity', 1)
                processing_method = item_data.get('processing_method', 'NONE')
                
                # Validate product exists and is available
                try:
                    product = Product.objects.get(id=product_id, is_available=True)
                    
                    # Check if product is already in user's cart
                    cart_item, created = CartItem.objects.get_or_create(
                        cart=cart,
                        product=product,
                        defaults={
                            'quantity': quantity,
                            'processing_method': processing_method
                        }
                    )
                    
                    # If product was already in cart, update quantity (if not created)
                    if not created:
                        # Add the guest cart quantity to the existing cart item
                        cart_item.quantity += quantity
                        # Make sure we don't exceed available stock
                        if cart_item.quantity > product.stock_quantity:
                            cart_item.quantity = product.stock_quantity
                        cart_item.save()
                    
                    items_added += 1
                    logger.info(f"Migrated product {product_id} to user {request.user.id}'s cart")
                
                except Product.DoesNotExist:
                    logger.warning(f"Attempted to migrate non-existent product {product_id}")
                    continue
                
            except (ValueError, KeyError) as e:
                logger.error(f"Error processing cart item {product_id_str}: {e}")
                continue
        
        # Clear the session cart after migration
        if 'guest_cart_items' in request.session:
            del request.session['guest_cart_items']
            request.session.modified = True
        
        # Update cart count in session
        cart_count = cart.item_count()
        request.session['cart_items'] = cart_count
        request.session.save()
        
        logger.info(f"Successfully migrated {items_added} items to user {request.user.id}'s cart")
        return items_added > 0
        
    except Exception as e:
        logger.exception(f"Error migrating cart for user {request.user.id}: {e}")
        return False


def get_guest_cart_from_session(request):
    """
    Retrieves the guest cart data from the session.
    This is used for anonymous users who haven't logged in yet.
    
    Args:
        request: The HTTP request object containing session data
        
    Returns:
        dict: Cart items data from session, or empty dict if none exists
    """
    return request.session.get('guest_cart_items', {})


def add_to_guest_cart(request, product_id, quantity=1, processing_method='NONE'):
    """
    Adds a product to the guest cart stored in session.
    This is used for anonymous users who haven't logged in yet.
    
    Args:
        request: The HTTP request object containing session data
        product_id: ID of the product to add
        quantity: Quantity to add (default: 1)
        processing_method: Product processing method (default: 'NONE')
        
    Returns:
        bool: True if product was added successfully, False otherwise
    """
    try:
        # Get the product to validate it exists and is available
        product = Product.objects.get(id=product_id, is_available=True)
        
        # Initialize guest cart if it doesn't exist
        if 'guest_cart_items' not in request.session:
            request.session['guest_cart_items'] = {}
        
        # Get current guest cart
        guest_cart = request.session['guest_cart_items']
        product_id_str = str(product_id)
        
        # Check if product is already in cart
        if product_id_str in guest_cart:
            # Increment quantity
            guest_cart[product_id_str]['quantity'] += quantity
        else:
            # Add new item
            guest_cart[product_id_str] = {
                'quantity': quantity,
                'processing_method': processing_method,
                'price': str(product.price),
                'name': product.name
            }
        
        # Save the updated cart back to session
        request.session['guest_cart_items'] = guest_cart
        request.session.modified = True
        
        # Calculate and update total item count in session
        total_items = sum(item.get('quantity', 0) for item in guest_cart.values())
        request.session['cart_items'] = total_items
        
        return True
        
    except Product.DoesNotExist:
        logger.warning(f"Attempted to add non-existent product {product_id} to guest cart")
        return False
    except Exception as e:
        logger.exception(f"Error adding product {product_id} to guest cart: {e}")
        return False


def remove_from_guest_cart(request, product_id):
    """
    Removes a product from the guest cart stored in session.
    
    Args:
        request: The HTTP request object containing session data
        product_id: ID of the product to remove
        
    Returns:
        bool: True if product was removed successfully, False otherwise
    """
    try:
        if 'guest_cart_items' not in request.session:
            return False
        
        guest_cart = request.session['guest_cart_items']
        product_id_str = str(product_id)
        
        # Check if product is in cart
        if product_id_str in guest_cart:
            # Remove the item
            del guest_cart[product_id_str]
            
            # Save the updated cart back to session
            request.session['guest_cart_items'] = guest_cart
            request.session.modified = True
            
            # Calculate and update total item count in session
            total_items = sum(item.get('quantity', 0) for item in guest_cart.values())
            request.session['cart_items'] = total_items
            
            return True
        
        return False
        
    except Exception as e:
        logger.exception(f"Error removing product {product_id} from guest cart: {e}")
        return False


def calculate_cart_delivery_fee(
    cart,
    delivery_option='STANDARD',
    delivery_address=None,
    distance_km=None,
    origin_coords=None,
    destination_coords=None
):
    """
    Calculate delivery fee for a cart based on its contents and delivery details.
    
    Args:
        cart: Cart object or dict of cart items (for guest cart)
        delivery_option: One of 'STANDARD', 'EXPRESS', or 'SCHEDULED'
        delivery_address: DeliveryAddress object (optional)
        distance_km: Known distance in kilometers (optional)
        origin_coords: Business location coordinates (optional)
        destination_coords: Delivery destination coordinates (optional)
        
    Returns:
        Decimal: Calculated delivery fee
    """
    # Determine if we're dealing with a user cart or guest cart
    is_model_cart = isinstance(cart, Cart)
    
    # Get total cart weight (estimating 0.5kg per item)
    if is_model_cart:
        # For user cart model
        total_weight = sum(0.5 * item.quantity for item in cart.items.all())
    else:
        # For guest cart dict
        total_weight = sum(0.5 * item_data.get('quantity', 1) for item_data in cart.values())
    
    # If delivery address provided, extract coordinates
    if delivery_address and not destination_coords:
        destination_coords = (delivery_address.latitude, delivery_address.longitude)
    
    # Calculate the delivery fee
    fee = calculate_delivery_fee(
        delivery_option=delivery_option,
        distance_km=distance_km,
        weight_kg=total_weight,
        origin_coords=origin_coords,
        destination_coords=destination_coords
    )
    
    return fee

def get_cart_checkout_summary(request, delivery_option='STANDARD', delivery_address=None):
    """
    Generate a checkout summary including subtotal, delivery fee, and total.
    Works for both authenticated users and guests.
    
    Args:
        request: The HTTP request object
        delivery_option: Selected delivery option
        delivery_address: Selected delivery address (optional)
        
    Returns:
        dict: Summary containing subtotal, delivery_fee, total, and ETA
    """
    if request.user.is_authenticated:
        # Get authenticated user's cart
        try:
            cart = Cart.objects.get(user=request.user)
            subtotal = sum(item.subtotal() for item in cart.items.all())
        except Cart.DoesNotExist:
            cart = None
            subtotal = Decimal('0.00')
    else:
        # Get guest cart from session
        cart_items = get_guest_cart_from_session(request)
        if cart_items:
            # Calculate subtotal from guest cart items
            subtotal = sum(
                Decimal(item_data.get('price', '0')) * item_data.get('quantity', 0)
                for item_data in cart_items.values()
            )
            cart = cart_items
        else:
            cart = None
            subtotal = Decimal('0.00')
    
    # Extract coordinates from delivery address if provided
    destination_coords = None
    if delivery_address and hasattr(delivery_address, 'latitude') and hasattr(delivery_address, 'longitude'):
        destination_coords = (delivery_address.latitude, delivery_address.longitude)
    
    # Calculate delivery fee
    if cart and subtotal > 0:
        delivery_fee = calculate_cart_delivery_fee(
            cart=cart,
            delivery_option=delivery_option,
            delivery_address=delivery_address,
            destination_coords=destination_coords
        )
    else:
        delivery_fee = Decimal('0.00')
    
    # Calculate total amount
    total = subtotal + delivery_fee
    
    # Get delivery ETA information
    eta_info = get_delivery_eta(delivery_option)
    
    return {
        'subtotal': subtotal,
        'delivery_fee': delivery_fee,
        'total': total,
        'eta': eta_info,
        'item_count': request.session.get('cart_items', 0)
    }