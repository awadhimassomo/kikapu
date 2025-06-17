from datetime import timezone, timedelta
from django.db import models
from django.conf import settings
import uuid
import random
import string
from decimal import Decimal
from django.urls import reverse
from django.utils import timezone
from .delivery_utils import calculate_order_delivery_fee, get_delivery_eta
import urllib.parse
from django.db.models import Q

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='category_images/', blank=True, null=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children')
    
    class Meta:
        verbose_name_plural = 'Categories'
    
    def __str__(self):
        return self.name

class Product(models.Model):
    PROCESSING_CHOICES = (
        ('NONE', 'None/Raw'),
        ('PEELED', 'Peeled'),
        ('CHOPPED', 'Chopped'),
        ('BLENDED', 'Blended'),
        ('BOILED', 'Boiled'),
        ('FRIED', 'Fried'),
        ('DEEP_FRIED', 'Deep Fried'),
        ('ROASTED', 'Roasted'),
        ('STEAMED', 'Steamed'),
        ('BAKED', 'Baked'),
        ('GRILLED', 'Grilled'),
        ('SMOKED', 'Smoked'),
        ('MARINATED', 'Marinated'),
        ('PICKLED', 'Pickled'),
        ('FERMENTED', 'Fermented'),
        ('DRIED', 'Dried'),
        ('GROUND', 'Ground'),
        ('MIXED', 'Mixed'),
        ('OTHER', 'Other (specify in description)'),
    )
    
    UNIT_CHOICES = (
        ('KG', 'Kilograms (kg)'),
        ('G', 'Grams (g)'),
        ('L', 'Liters (L)'),
        ('ML', 'Milliliters (ml)'),
        ('PIECE', 'Piece'),
        ('DOZEN', 'Dozen'),
        ('BUNDLE', 'Bundle'),
        ('CRATE', 'Crate'),
        ('BAG', 'Bag'),
        ('BOX', 'Box'),
        ('PACKET', 'Packet'),
        ('OTHER', 'Other (specify in description)')
    )
    
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    business = models.ForeignKey('registration.BusinessProfile', on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='KG', 
                         help_text='Unit of measurement for this product')
    stock_quantity = models.PositiveIntegerField(default=0)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def default_processing_method(self):
        """Returns the default processing method for this product, or None/Raw if not defined"""
        default = self.processing_methods.filter(is_default=True).first()
        if default:
            return default.method
        return 'NONE'  # Default to None/Raw if no default is set
    
    @property
    def default_processing_method_display(self):
        """Returns the display name of the default processing method"""
        method = self.default_processing_method
        return dict(self.PROCESSING_CHOICES).get(method, 'None/Raw')
    
    def __str__(self):
        return self.name

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='product_images/')
    is_primary = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Image for {self.product.name}"

class ProductProcessingMethod(models.Model):
    """Model to manage multiple processing methods for a product"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='processing_methods')
    method = models.CharField(
        max_length=20, 
        choices=Product.PROCESSING_CHOICES, 
        help_text="Processing method offered for this product"
    )
    is_default = models.BooleanField(default=False, help_text="This is the default processing method shown to customers")
    
    class Meta:
        unique_together = ('product', 'method')
        verbose_name = "Product Processing Method"
        verbose_name_plural = "Product Processing Methods"
    
    @property
    def method_display(self):
        """Returns the display name of the processing method"""
        return dict(Product.PROCESSING_CHOICES).get(self.method, 'None/Raw')
    
    def __str__(self):
        return f"{self.product.name} - {self.method_display}"


DELIVERY_OPTIONS = (
    ('STANDARD', 'Standard Delivery'),
    ('EXPRESS', 'Express Delivery'),
    ('SCHEDULED', 'Scheduled Delivery'),
    ('GROUP', 'Group Delivery'),
    ('SUBSCRIPTION', 'Subscription Delivery'),
)

class Order(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    )

    customer = models.ForeignKey('registration.CustomerProfile', on_delete=models.CASCADE, related_name='orders')
    order_number = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='PENDING')

    # Address
    shipping_address = models.TextField()
    delivery_location = models.TextField(null=True, blank=True)
    delivery_address = models.ForeignKey('DeliveryAddress', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')

    # Delivery
    delivery_option = models.CharField(max_length=20, choices=DELIVERY_OPTIONS, default='STANDARD')
    delivery_method = models.CharField(max_length=20, null=True, blank=True)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    distance_km = models.FloatField(null=True, blank=True)
    scheduled_delivery = models.ForeignKey('ScheduledDelivery', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    
    # Scheduled delivery fields
    scheduled_delivery_date = models.DateField(null=True, blank=True, 
                                            help_text="Date for a one-time scheduled delivery")
    scheduled_delivery_time = models.CharField(
        max_length=20, 
        choices=[
            ('MORNING', 'Morning (8AM - 11AM)'),
            ('AFTERNOON', 'Afternoon (12PM - 3PM)'),
            ('EVENING', 'Evening (4PM - 7PM)')
        ],
        null=True, 
        blank=True,
        help_text="Time slot for a one-time scheduled delivery"
    )
    
    # Link to subscription or delivery schedule
    subscription = models.ForeignKey('Subscription', on_delete=models.SET_NULL, null=True, blank=True, 
                                  related_name='orders')
    delivery_schedule = models.ForeignKey('DeliverySchedule', on_delete=models.SET_NULL, null=True, blank=True, 
                                      related_name='orders')

    # Totals
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    leader_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Timestamps
    estimated_delivery_time = models.DateTimeField(null=True, blank=True)
    actual_delivery_time = models.DateTimeField(null=True, blank=True)
    order_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Relations
    delivery_group = models.ForeignKey('DeliveryGroup', null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"Order #{self.order_number}"
    
    
class DeliveryGroup(models.Model):
    """
    Group delivery model allowing multiple customers to share a delivery and its cost.
    """
    TIME_SLOT_CHOICES = [
        ('MORNING', 'Morning (8AM - 11AM)'),
        ('AFTERNOON', 'Afternoon (12PM - 3PM)'),
        ('EVENING', 'Evening (4PM - 7PM)')
    ]
    
    code = models.CharField(max_length=10, unique=True)
    leader = models.ForeignKey('registration.CustomerProfile', on_delete=models.CASCADE, related_name='led_groups')
    delivery_date = models.DateField()
    time_slot = models.CharField(max_length=20, choices=TIME_SLOT_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    shared_link = models.URLField(blank=True, null=True)
    
    # Fixed group delivery fee in TSh
    GROUP_DELIVERY_FEE = Decimal('2000.00')
    
    # Leader discount percentage
    LEADER_DISCOUNT_PERCENTAGE = Decimal('0.10')  # 10%
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['delivery_date']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"Group {self.code} (Leader: {self.leader.user.username})"
    
    def save(self, *args, **kwargs):
        # Generate a unique code if not provided
        if not self.code:
            self.code = self._generate_unique_code()
        
        # Set expiration time if not provided (24 hours from creation by default)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
            
        # Generate shared link if not provided
        if not self.shared_link:
            # This will be populated after save with the actual URL
            pass
            
        super().save(*args, **kwargs)
        
        # Update the shared link with the actual URL
        if not self.shared_link:
            self.shared_link = self._get_share_url()
            # Save again but skip the save method's custom logic
            super().save(update_fields=['shared_link'])
    
    def _generate_unique_code(self):
        """Generate a unique code for this group (e.g., KIK1234)"""
        prefix = 'KIK'
        while True:
            # Generate a random 4-digit number
            random_digits = ''.join(random.choices(string.digits, k=4))
            code = f"{prefix}{random_digits}"
            
            # Check if this code already exists
            if not DeliveryGroup.objects.filter(code=code).exists():
                return code
    
    def _get_share_url(self):
        """Generate a shareable URL for this group"""
        base_url = settings.BASE_URL if hasattr(settings, 'BASE_URL') else 'https://kikapu.tz'
        path = reverse('join_group', args=[self.code])
        return f"{base_url}{path}"
    
    def get_whatsapp_share_text(self):
        """Generate text for WhatsApp sharing"""
        return (
            f"🧺 Join our Kikapu Group Delivery!\n"
            f"We're combining grocery orders to save on delivery. "
            f"I get 10% off as the group leader 😎\n"
            f"Click to join: {self.shared_link}\n"
            f"Group Code: {self.code}\n"
            f"Delivery Date: {self.delivery_date}\n"
            f"Time Slot: {self.get_time_slot_display()}"
        )
    
    def get_whatsapp_share_link(self):
        """Generate a WhatsApp sharing link with pre-populated text"""
        join_url = self._get_share_url()
        message = f"Join my KIKAPU delivery group! We'll split the delivery fee. Group code: {self.code}. Join here: {join_url}"
        encoded_message = urllib.parse.quote(message)
        return f"https://wa.me/?text={encoded_message}"
    
    def get_member_count(self):
        """Get the number of members in this group"""
        return self.group_orders.count()
    
    def get_split_delivery_fee(self):
        """Calculate the split delivery fee per member"""
        member_count = max(self.get_member_count(), 1)  # Avoid division by zero
        return self.GROUP_DELIVERY_FEE / member_count
    
    def is_expired(self):
        """Check if this group has expired"""
        return timezone.now() > self.expires_at if self.expires_at else False
    
    def close_group(self):
        """Mark this group as inactive"""
        self.is_active = False
        self.save(update_fields=['is_active'])


class ScheduledDelivery(models.Model):
    """
    Model for scheduled deliveries, allowing customers to select a specific 
    date and time slot for their delivery.
    """
    REPEAT_CHOICES = (
        ('NONE', 'One-time'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly')
    )
    
    TIME_SLOT_CHOICES = [
        ('MORNING', 'Morning (8AM - 11AM)'),
        ('AFTERNOON', 'Afternoon (12PM - 3PM)'),
        ('EVENING', 'Evening (4PM - 7PM)')
    ]
    
    delivery_date = models.DateField()
    time_slot = models.CharField(max_length=20, choices=TIME_SLOT_CHOICES)
    delivery_notes = models.TextField(blank=True, null=True)
    recurrence_type = models.CharField(max_length=10, choices=REPEAT_CHOICES, default='NONE')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['delivery_date', 'time_slot']
        verbose_name = 'Scheduled Delivery'
        verbose_name_plural = 'Scheduled Deliveries'
        
    def __str__(self):
        return f"Scheduled for {self.delivery_date} - {self.get_time_slot_display()} - {self.recurrence_type}"
    
    @property
    def formatted_delivery_window(self):
        """Returns a formatted string of the delivery window"""
        date_str = self.delivery_date.strftime("%B %d, %Y")
        return f"{date_str}, {self.get_time_slot_display()}"


class GroupOrder(models.Model):
    """
    Represents an order within a delivery group. 
    Links the Order model to a DeliveryGroup and tracks group-specific information.
    """
    group = models.ForeignKey(DeliveryGroup, on_delete=models.CASCADE, related_name='group_orders')
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='group_order')
    member = models.ForeignKey('registration.CustomerProfile', 
                              null=True, blank=True, 
                              on_delete=models.SET_NULL, 
                              related_name='group_orders')
    added_by_leader = models.BooleanField(default=False)
    name = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    
    leader_discount_applied = models.BooleanField(default=False)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['added_by_leader']),
        ]
        unique_together = [('group', 'order')]
    
    def __str__(self):
        member_info = f"{self.name}" if self.name and self.added_by_leader else f"{self.member}"
        return f"Order #{self.order.order_number} in Group {self.group.code} by {member_info}"
    
    def save(self, *args, **kwargs):
        # Apply leader discount if this is the leader's order
        if self.member == self.group.leader and not self.leader_discount_applied:
            self._apply_leader_discount()
        
        super().save(*args, **kwargs)
    
    def _apply_leader_discount(self):
        """Apply leader discount to the order and save the discount amount"""
        # Calculate discount (10% of subtotal)
        discount = self.order.subtotal * self.group.LEADER_DISCOUNT_PERCENTAGE
        
        # Update order total
        self.order.leader_discount = discount
        self.order.total_amount = self.order.total_amount - discount
        self.order.save(update_fields=['leader_discount', 'total_amount'])
        
        # Record the discount
        self.discount_amount = discount
        self.leader_discount_applied = True


class DeliveryAddress(models.Model):
    customer = models.ForeignKey('registration.CustomerProfile', on_delete=models.CASCADE, related_name='delivery_addresses')
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    region = models.CharField(max_length=100)
    landmark = models.CharField(max_length=255, blank=True, null=True)
    phoneNumber = models.CharField(max_length=15, blank=True, null=True)
    is_default = models.BooleanField(default=False)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.address_line_1}, {self.city}, {self.region}"
    
    def save(self, *args, **kwargs):
        # If this is the first address or is being set as default
        if self.is_default:
            # Set all other addresses of this customer to non-default
            DeliveryAddress.objects.filter(customer=self.customer, is_default=True).update(is_default=False)
        
        # If this is the customer's first address, make it default
        if not self.pk and not DeliveryAddress.objects.filter(customer=self.customer).exists():
            self.is_default = True
            
        super().save(*args, **kwargs)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Price at time of purchase
    processing_method = models.CharField(
        max_length=20, 
        choices=Product.PROCESSING_CHOICES,
        default='NONE',
        help_text="Processing method requested by customer"
    )
    
    @property
    def processing_method_display(self):
        """Returns the display name of the selected processing method"""
        return dict(Product.PROCESSING_CHOICES).get(self.processing_method, 'None/Raw')
    
    @property
    def subtotal(self):
        return self.price * self.quantity
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name}"




class BusinessNotification(models.Model):
    """Notifications for business users about orders and other important events"""
    NOTIFICATION_TYPES = (
        ('NEW_ORDER', 'New Order'),
        ('ORDER_STATUS', 'Order Status Change'),
        ('LOW_STOCK', 'Low Stock Alert'),
        ('SYSTEM', 'System Notification'),
    )
    
    business = models.ForeignKey('registration.BusinessProfile', on_delete=models.CASCADE, related_name='notifications')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True, related_name='business_notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=100)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', 'is_read']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_notification_type_display()} for {self.business.business_name}"



class Cart(models.Model):
    """Cart model for authenticated users only.
    Each user can have only one active cart at a time.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def total(self):
        """Calculate cart subtotal based on items"""
        return sum(item.subtotal() for item in self.items.all())
    
    def item_count(self):
        """Count the total number of items in the cart"""
        return self.items.aggregate(models.Sum('quantity'))['quantity__sum'] or 0
    
    def __str__(self):
        return f"Cart for {self.user.username}"


class CartItem(models.Model):
    """Items within a user's cart.
    Each cart can have multiple items, but only one item per product.
    """
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    processing_method = models.CharField(
        max_length=20, 
        choices=Product.PROCESSING_CHOICES, 
        default='NONE',
        help_text="Processing method requested by customer"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('cart', 'product')
        ordering = ['-updated_at']
    
    def clean(self):
        """Validate that quantity doesn't exceed available stock"""
        from django.core.exceptions import ValidationError
        
        if self.quantity < 1:
            raise ValidationError('Quantity must be at least 1')
            
        if self.product.stock_quantity < self.quantity:
            raise ValidationError(f'Not enough stock available. Only {self.product.stock_quantity} units available.')
    
    def subtotal(self):
        """Calculate subtotal for this item"""
        return self.product.price * self.quantity
    
    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


class Purchase(models.Model):
    """
    Model to record products bought together for generating product suggestions
    using the Apriori algorithm (Market Basket Analysis)
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    order_id = models.CharField(max_length=36, help_text="Unique ID to group purchases in a single order")
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['order_id']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        user_str = self.user.username if self.user else "Anonymous"
        return f"Purchase of {self.product.name} by {user_str} ({self.order_id})"

class ProductAssociation(models.Model):
    """
    Stores product association rules generated by the Apriori algorithm
    for quick lookup of product recommendations
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='associations')
    recommendation = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='recommended_for')
    confidence = models.FloatField(help_text="Probability that recommendation is purchased when product is purchased")
    lift = models.FloatField(help_text="How much more likely recommendation is purchased with product vs. on its own")
    support = models.FloatField(help_text="Percentage of orders containing both products")
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('product', 'recommendation')
        indexes = [
            models.Index(fields=['product']),
            models.Index(fields=['lift']),  # For sorting by strongest associations
        ]
    
    def __str__(self):
        return f"If customer buys {self.product.name}, they might also like {self.recommendation.name}"

class RelatedProduct(models.Model):
    """
    Manually defined product relationships for recommendation fallback.
    Used when Apriori algorithm doesn't have enough purchase data.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='manual_related_products')
    related_product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='manual_related_to')
    relationship_type = models.CharField(max_length=50, default='complementary', 
                                        help_text="Describes how these products are related")
    relevance_score = models.PositiveSmallIntegerField(default=10, 
                                                    help_text="1-10 score indicating how relevant this relationship is")
    notes = models.TextField(blank=True, null=True,
                           help_text="Optional notes about why these products are related")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('product', 'related_product')
        ordering = ['-relevance_score', 'product__name']
        indexes = [
            models.Index(fields=['product', 'relevance_score']),
        ]
    
    def __str__(self):
        return f"{self.product.name} → {self.related_product.name} ({self.relationship_type})"


class Subscription(models.Model):
    """Model for subscription-based recurring deliveries"""
    customer = models.ForeignKey('registration.CustomerProfile', on_delete=models.CASCADE, related_name='subscriptions')
    
    DURATION_CHOICES = (
        ('TWO_WEEKS', 'Two Weeks'),
        ('ONE_MONTH', 'One Month'),
        ('THREE_MONTHS', 'Three Months'),
        ('SIX_MONTHS', 'Six Months'),
        ('CUSTOM', 'Custom Duration')
    )
    
    FREQUENCY_CHOICES = (
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('BIWEEKLY', 'Bi-weekly'),
        ('MONTHLY', 'Monthly'),
    )
    
    TIME_SLOT_CHOICES = (
        ('MORNING', 'Morning (8AM - 11AM)'),
        ('AFTERNOON', 'Afternoon (12PM - 3PM)'),
        ('EVENING', 'Evening (4PM - 7PM)')
    )
    
    name = models.CharField(max_length=100, blank=True, help_text="Optional name for this subscription")
    duration = models.CharField(max_length=20, choices=DURATION_CHOICES)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    delivery_days = models.CharField(max_length=100, blank=True, null=True,
                                  help_text="Comma-separated days for weekly deliveries (mon,tue,wed,etc.)")
    time_slot = models.CharField(max_length=20, choices=TIME_SLOT_CHOICES)
    
    # Duration tracking
    start_date = models.DateField()
    end_date = models.DateField()
    next_delivery_date = models.DateField()
    
    # Fixed discount for subscription
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Status fields
    is_active = models.BooleanField(default=True)
    cancellation_date = models.DateField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True, null=True)
    
    # Address for all deliveries in this subscription
    delivery_address = models.ForeignKey(
        'DeliveryAddress', 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='subscriptions'
    )
    
    # Statistics and tracking
    total_deliveries = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Payment tracking
    payment_method = models.CharField(max_length=50, default='CASH')
    auto_renew = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'is_active']),
            models.Index(fields=['next_delivery_date']),
        ]
    
    def __str__(self):
        return f"{self.customer.user.email} - {self.get_duration_display()} {self.get_frequency_display()}"
    
    def calculate_next_delivery_date(self):
        """Calculate the next delivery date based on frequency and current date"""
        from datetime import datetime, timedelta
        today = timezone.now().date()
        
        if self.frequency == 'DAILY':
            next_date = today + timedelta(days=1)
        elif self.frequency == 'WEEKLY':
            next_date = today + timedelta(weeks=1)
        elif self.frequency == 'BIWEEKLY':
            next_date = today + timedelta(weeks=2)
        elif self.frequency == 'MONTHLY':
            # Approximate a month as 30 days
            next_date = today + timedelta(days=30)
        else:
            next_date = today + timedelta(weeks=1)  # Default to weekly
            
        # Don't schedule past the end date
        if next_date > self.end_date:
            return None
            
        return next_date
    
    def update_after_delivery(self):
        """Update subscription stats after a delivery is made"""
        self.total_deliveries += 1
        self.next_delivery_date = self.calculate_next_delivery_date()
        
        # If we've reached the end, mark as inactive
        if not self.next_delivery_date:
            self.is_active = False
            
        self.save()
    
    def cancel(self, reason=None):
        """Cancel this subscription"""
        self.is_active = False
        self.cancellation_date = timezone.now().date()
        if reason:
            self.cancellation_reason = reason
        self.save()

class DeliverySchedule(models.Model):
    """Enhanced model for all types of scheduled deliveries including one-time and recurring"""
    customer = models.ForeignKey('registration.CustomerProfile', on_delete=models.CASCADE, related_name='delivery_schedules')
    
    SCHEDULE_TYPE_CHOICES = (
        ('ONETIME', 'One-time Delivery'),
        ('WEEKLY', 'Weekly Scheduled Delivery'),
        ('SUBSCRIPTION', 'Subscription')
    )
    
    TIME_SLOT_CHOICES = (
        ('MORNING', 'Morning (8AM - 11AM)'),
        ('AFTERNOON', 'Afternoon (12PM - 3PM)'),
        ('EVENING', 'Evening (4PM - 7PM)')
    )
    
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPE_CHOICES, default='ONETIME')
    
    # One-time delivery fields
    delivery_date = models.DateField(null=True, blank=True)
    time_slot = models.CharField(max_length=20, choices=TIME_SLOT_CHOICES)

    # Weekly scheduled delivery fields
    is_recurring = models.BooleanField(default=False)
    recurrence_type = models.CharField(
        max_length=10,
        choices=[('WEEKLY', 'Weekly'), ('MONTHLY', 'Monthly')],
        blank=True,
        null=True
    )
    delivery_days = models.CharField(max_length=100, blank=True, null=True, 
                                  help_text="Comma-separated days for weekly deliveries (mon,tue,wed,etc.)")

    # Link to the customer's address
    delivery_address = models.ForeignKey(
        'DeliveryAddress', 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='scheduled_deliveries'
    )
    
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Analytics fields
    times_fulfilled = models.IntegerField(default=0)
    times_skipped = models.IntegerField(default=0)
    times_modified = models.IntegerField(default=0)
    
    # Link to subscription if this is part of a subscription
    subscription = models.ForeignKey('Subscription', on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='delivery_schedules')
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['schedule_type']),
            models.Index(fields=['delivery_date']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        if self.schedule_type == 'ONETIME':
            return f"One-time delivery for {self.customer.user.email} on {self.delivery_date}"
        elif self.schedule_type == 'WEEKLY':
            return f"Weekly delivery for {self.customer.user.email} ({self.delivery_days})"
        else:
            return f"Subscription delivery for {self.customer.user.email}"
    
    def get_items_total(self):
        """Calculate the total cost of all items in this schedule"""
        total = 0
        for item in self.scheduleditems.all():
            total += item.product.price * item.quantity
        return total
    
    @staticmethod
    def get_schedules_for_today():
        """Return all active schedules that need to be processed today"""
        today = timezone.now().date()
        day_name = today.strftime("%a").lower()  # Get lowercase day abbreviation (mon, tue, etc.)

        # Get all active schedules for today
        return DeliverySchedule.objects.filter(
            is_active=True
        ).filter(
            # One-time deliveries for today
            Q(schedule_type='ONETIME', delivery_date=today) |
            # Weekly deliveries that match today's day of the week
            Q(schedule_type='WEEKLY', delivery_days__contains=day_name) |
            # Subscription deliveries (these will be handled by the Subscription model's logic)
            Q(schedule_type='SUBSCRIPTION', subscription__is_active=True, 
              subscription__next_delivery_date=today)
        )


class ScheduledItem(models.Model):
    schedule = models.ForeignKey(DeliverySchedule, on_delete=models.CASCADE, related_name='scheduleditems')
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    processing_method = models.CharField(max_length=20, default='NONE')

    def __str__(self):
        return f"{self.product.name} x{self.quantity}"


class Offer(models.Model):
    """Model for special offers and promotions that can be applied to products or categories
    and made available to users."""
    
    OFFER_TYPE_CHOICES = (
        ('PERCENTAGE', 'Percentage Discount'),
        ('FIXED', 'Fixed Amount Discount'),
        ('BOGO', 'Buy One Get One Free'),
        ('BUNDLE', 'Bundle Discount'),
        ('FREESHIP', 'Free Shipping'),
        ('LOYALTY', 'Loyalty Points Bonus'),
        ('FLASH', 'Flash Sale'),
    )
    
    TARGET_TYPE_CHOICES = (
        ('ALL', 'All Users'),
        ('NEW', 'New Users Only'),
        ('RETURNING', 'Returning Users'),
        ('PREMIUM', 'Premium Users'),
        ('INACTIVE', 'Inactive Users'),
        ('SPECIFIC', 'Specific Users'),
    )
    
    title = models.CharField(max_length=100)
    description = models.TextField()
    code = models.CharField(max_length=20, unique=True, blank=True, null=True,
                          help_text="Promo code for this offer. Leave blank for automatic offers.")
    offer_type = models.CharField(max_length=20, choices=OFFER_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,
                                      help_text="Discount value (percentage or fixed amount)")
    
    # Targeting
    target_type = models.CharField(max_length=20, choices=TARGET_TYPE_CHOICES, default='ALL')
    
    # Validity
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    # Usage limits
    max_uses = models.PositiveIntegerField(default=0, 
                                        help_text="Maximum number of times this offer can be used (0 for unlimited)")
    max_uses_per_user = models.PositiveIntegerField(default=1,
                                                help_text="Maximum number of times a user can use this offer")
    
    # Conditions
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,
                                       help_text="Minimum order value for the offer to apply")
    
    # What this offer applies to
    applies_to_products = models.ManyToManyField('Product', blank=True, related_name='offers')
    applies_to_categories = models.ManyToManyField('Category', blank=True, related_name='offers')
    
    # Display settings
    highlight_color = models.CharField(max_length=20, default='#FFC107',
                                    help_text="Color for highlighting this offer in the UI")
    image = models.ImageField(upload_to='offer_images/', blank=True, null=True)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                 null=True, related_name='created_offers')
    total_uses = models.PositiveIntegerField(default=0, 
                                          help_text="Number of times this offer has been used")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['is_active']),
            models.Index(fields=['offer_type']),
        ]
    
    def __str__(self):
        return self.title
    
    def is_valid(self):
        """Check if this offer is currently valid"""
        now = timezone.now()
        if not self.is_active:
            return False
        if now < self.start_date or now > self.end_date:
            return False
        if self.max_uses > 0 and self.total_uses >= self.max_uses:
            return False
        return True
    
    def can_be_used_by_user(self, user):
        """Check if this offer can be used by the given user"""
        # Check if user has reached their personal limit
        if self.max_uses_per_user > 0:
            user_uses = UserOffer.objects.filter(user=user, offer=self, used=True).count()
            if user_uses >= self.max_uses_per_user:
                return False
        
        # Check target type restrictions
        if self.target_type == 'NEW':
            # New users = registered within last 30 days
            thirty_days_ago = timezone.now() - timedelta(days=30)
            if user.date_joined < thirty_days_ago:
                return False
        elif self.target_type == 'RETURNING':
            # Must have at least one completed order
            if not Order.objects.filter(user=user, status='DELIVERED').exists():
                return False
        elif self.target_type == 'PREMIUM':
            # Check if user has premium status
            try:
                if not user.customerprofile.is_premium:
                    return False
            except:
                return False
        elif self.target_type == 'INACTIVE':
            # Inactive = no orders in last 60 days
            sixty_days_ago = timezone.now() - timedelta(days=60)
            if Order.objects.filter(user=user, created_at__gte=sixty_days_ago).exists():
                return False
        elif self.target_type == 'SPECIFIC':
            # Check if this user has been specifically assigned this offer
            if not UserOffer.objects.filter(user=user, offer=self).exists():
                return False
        
        return True
    
    def calculate_discount(self, order_value, items=None):
        """Calculate the discount amount for this offer"""
        if self.offer_type == 'PERCENTAGE':
            return (order_value * self.discount_value) / 100
        elif self.offer_type == 'FIXED':
            return min(self.discount_value, order_value)  # Don't exceed order value
        elif self.offer_type == 'FREESHIP':
            # Return shipping fee as discount
            return calculate_order_delivery_fee(items)
        # For other offer types, more complex logic would be implemented
        return Decimal('0.00')


class UserOffer(models.Model):
    """Links users to offers and tracks usage"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_offers')
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name='user_offers')
    date_added = models.DateTimeField(auto_now_add=True)
    date_used = models.DateTimeField(null=True, blank=True)
    used = models.BooleanField(default=False)
    order = models.ForeignKey('Order', on_delete=models.SET_NULL, null=True, blank=True, 
                            related_name='applied_offers')
    
    class Meta:
        unique_together = ('user', 'offer')
        ordering = ['-date_added']
        indexes = [
            models.Index(fields=['user', 'used']),
            models.Index(fields=['offer']),
        ]
    
    def __str__(self):
        status = "Used" if self.used else "Available"
        return f"{self.offer.title} - {self.user.username} ({status})"
    
    def mark_as_used(self, order=None):
        """Mark this offer as used by the user"""
        if not self.used:
            self.used = True
            self.date_used = timezone.now()
            if order:
                self.order = order
            self.save()
            
            # Update the offer's total uses count
            self.offer.total_uses += 1
            self.offer.save()
