from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager, Group, Permission
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

class UserManager(BaseUserManager):
    def create_user(self, phoneNumber, email=None, password=None, **extra_fields):
        if not phoneNumber:
            raise ValueError('The Phone Number field must be set')
        
        # Email is optional, but normalize it if provided
        if email:
            email = self.normalize_email(email)
        
        # Set username equal to phoneNumber to avoid unique constraint issues
        # Django's AbstractUser still requires a unique username field
        user = self.model(
            phoneNumber=phoneNumber,
            email=email,
            username=phoneNumber,  # Set username equal to phoneNumber
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phoneNumber, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_type', 'ADMIN')
        
        # Email is optional for superusers too
        # Just like regular users, normalize if provided
        
        return self.create_user(phoneNumber, email, password, **extra_fields)

class User(AbstractUser):
    USER_TYPE_CHOICES = (
        ('ADMIN', 'Admin'),
        ('BUSINESS', 'Business'),
        ('CUSTOMER', 'Customer'),
        ('AGENT', 'Agent'),
    )
    
    # Add related_name to avoid clashes with auth.User
    groups = models.ManyToManyField(
        Group,
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        related_name='custom_user_set',
        related_query_name='user',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='custom_user_set',
        related_query_name='user',
    )
    
    # Add firstName and lastName fields to match with code expectations
    firstName = models.CharField(max_length=30, blank=True)
    lastName = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True, null=True)
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES, default='CUSTOMER')
    phoneNumber = models.CharField(max_length=15, unique=True)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    
    USERNAME_FIELD = 'phoneNumber'
    REQUIRED_FIELDS = ['firstName', 'lastName']
    
    objects = UserManager()
    
    def __str__(self):
        if self.email:
            return f"{self.firstName} {self.lastName} ({self.phoneNumber})"
        return self.phoneNumber
        
    def save(self, *args, **kwargs):
        # Synchronize firstName/lastName with first_name/last_name for compatibility
        # First, check if the attributes exist to prevent AttributeError
        try:
            # Check if we can access first_name and last_name
            # If access fails, we'll handle it in the except block
            
            # Only sync if both attributes exist
            if hasattr(self, 'firstName') and hasattr(self, 'first_name'):
                if self.firstName and not self.first_name:
                    self.first_name = self.firstName
                elif self.first_name and not self.firstName:
                    self.firstName = self.first_name
                    
            if hasattr(self, 'lastName') and hasattr(self, 'last_name'):
                if self.lastName and not self.last_name:
                    self.last_name = self.lastName
                elif self.last_name and not self.lastName:
                    self.lastName = self.last_name
                    
        except AttributeError:
            # If first_name/last_name aren't available, we'll skip the synchronization
            pass
            
        # Call the parent class's save method
        super().save(*args, **kwargs)
    
    @property
    def is_agent(self):
        """
        Check if this user is registered as a delivery agent.
        Used in market_research/views.py to authorize market price submission.
        """
        return self.user_type == 'AGENT' and hasattr(self, 'delivery_agent')

class BusinessProfile(models.Model):
    BUSINESS_TYPE_CHOICES = [
        ('farmer', 'Farmer / Producer'),
        ('processor', 'Food Processor'),
        ('wholesaler', 'Wholesaler'),
        ('retailer', 'Retailer / Shop'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='business_profile')
    business_name = models.CharField(max_length=100)
    business_address = models.TextField()
    business_description = models.TextField(blank=True, null=True)
    registration_number = models.CharField(max_length=50, blank=True, null=True)
    business_type = models.CharField(max_length=20, choices=BUSINESS_TYPE_CHOICES, default='retailer')
    business_logo = models.ImageField(upload_to='business_logos/', blank=True, null=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    
    # Additional fields for business operations
    business_phone = models.CharField(max_length=15, blank=True, null=True)
    business_email = models.EmailField(blank=True, null=True)
    business_hours = models.CharField(max_length=255, blank=True, null=True, help_text="e.g., 'Mon-Fri: 9AM-5PM, Sat: 10AM-3PM'")
    business_categories = models.ManyToManyField('marketplace.Category', related_name='businesses', blank=True)
    is_verified = models.BooleanField(default=False)  # Admin verification
    is_phone_verified = models.BooleanField(default=False)  # OTP verification
    is_active = models.BooleanField(default=False)  # Set to false until phone is verified
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    
    def __str__(self):
        return self.business_name
    
    def get_products(self):
        """Get all products for this business"""
        return self.products.all()
    
    def get_active_products(self):
        """Get all available products for this business"""
        return self.products.filter(is_available=True)
    
    def get_product_count(self):
        """Get total number of products"""
        return self.products.count()
    
    def get_orders(self):
        """Get all orders containing products from this business"""
        # Import here to avoid circular imports
        from marketplace.models import OrderItem, Order
        # Find all orders that contain items from this business
        order_ids = OrderItem.objects.filter(
            product__business=self
        ).values_list('order__id', flat=True).distinct()
        return Order.objects.filter(id__in=order_ids)
    
    def activate(self):
        """Activate business profile"""
        self.is_active = True
        self.save()
    
    def deactivate(self):
        """Deactivate business profile"""
        self.is_active = False
        self.save()

class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    address = models.TextField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    loyalty_points = models.IntegerField(default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    credit_score = models.IntegerField(default=500)  # Range: 0-1000
    card_type = models.CharField(max_length=10, choices=[('PREPAID', 'Prepaid'), ('POSTPAID', 'Postpaid')], default='PREPAID')
    pin_hash = models.CharField(max_length=128, null=True, blank=True)  # Hashed PIN for NFC card
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    postpaid_status = models.CharField(max_length=20, choices=[
        ('NONE', 'Not Applied'),
        ('PENDING', 'Application Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected')
    ], default='NONE')
    joined_date = models.DateTimeField(default=timezone.now)  # Changed from auto_now_add to default
    
    def __str__(self):
        return f"{self.user.firstName} {self.user.lastName}'s Profile"
    
    def add_points(self, points):
        """Add loyalty points to customer profile"""
        self.loyalty_points += points
        self.save()
    
    def use_points(self, points):
        """Use loyalty points if available"""
        if self.loyalty_points >= points:
            self.loyalty_points -= points
            self.save()
            return True
        return False
        
    def set_pin(self, raw_pin):
        """Set customer PIN for NFC card (4-digit)"""
        if not raw_pin.isdigit() or len(raw_pin) != 4:
            return False, "PIN must be exactly 4 digits"
            
        from django.contrib.auth.hashers import make_password
        self.pin_hash = make_password(raw_pin)
        self.save(update_fields=['pin_hash'])
        return True, "PIN set successfully"
        
    def verify_pin(self, entered_pin):
        """Verify the customer's PIN"""
        if not self.pin_hash:
            return False, "PIN not set"
            
        from django.contrib.auth.hashers import check_password
        if check_password(entered_pin, self.pin_hash):
            return True, "PIN verified"
        return False, "Invalid PIN"
        
    def is_eligible_for_postpaid(self):
        """Check if customer is eligible for postpaid upgrade"""
        from datetime import timedelta
        from django.utils import timezone
        
        # Must have spent at least 25,000 TZS
        if self.total_spent < 25000:
            return False, "Must spend at least 25,000 TZS on marketplace"
            
        # Must have been registered for at least 30 days
        min_days = 30
        if timezone.now() - self.joined_date < timedelta(days=min_days):
            return False, f"Must be registered for at least {min_days} days"
            
        # Must not be blacklisted
        if self.credit_score < 300:
            return False, "Credit score too low for postpaid eligibility"
            
        return True, "Eligible for postpaid upgrade"
        
    def update_credit_score(self, points_change, reason=None):
        """Update customer's credit score"""
        self.credit_score = max(0, min(1000, self.credit_score + points_change))
        self.save(update_fields=['credit_score'])
        
        # Create credit event record
        CreditEvent.objects.create(
            customer=self.user,
            event_type=reason or ('INCREASE' if points_change > 0 else 'DECREASE'),
            points_change=points_change
        )
        
        return self.credit_score

class LoyaltyCard(models.Model):
    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('LOST', 'Lost/Stolen'),
        ('EXPIRED', 'Expired'),
    )
    
    TIER_CHOICES = (
        ('STANDARD', 'Standard'),
        ('SILVER', 'Silver'),
        ('GOLD', 'Gold'),
        ('PLATINUM', 'Platinum'),
    )
    
    customer = models.OneToOneField(CustomerProfile, on_delete=models.CASCADE, related_name='loyalty_card')
    card_number = models.CharField(max_length=20, unique=True)
    nfc_tag_id = models.CharField(max_length=100, unique=True, help_text="Unique identifier for the NFC tag")
    issue_date = models.DateField(auto_now_add=True)
    expiry_date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE')
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, default='STANDARD')
    last_used = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return f"Card {self.card_number} - {self.customer.user.phoneNumber}"
    
    def activate(self):
        self.status = 'ACTIVE'
        self.save()
    
    def deactivate(self):
        self.status = 'INACTIVE'
        self.save()
    
    def report_lost(self):
        self.status = 'LOST'
        self.save()
    
    def is_valid(self):
        import datetime
        return (self.status == 'ACTIVE' and 
                self.expiry_date >= datetime.date.today())
    
    def update_tier(self):
        """Update tier based on loyalty points"""
        points = self.customer.loyalty_points
        
        if points >= 5000:
            self.tier = 'PLATINUM'
        elif points >= 2000:
            self.tier = 'GOLD'
        elif points >= 500:
            self.tier = 'SILVER'
        else:
            self.tier = 'STANDARD'
        
        self.save()
    
    def use_card(self):
        """Record card usage"""
        import datetime
        self.last_used = datetime.datetime.now()
        self.save()

class CardTransaction(models.Model):
    TYPE_CHOICES = (
        ('EARN', 'Earn Points'),
        ('REDEEM', 'Redeem Points'),
        ('BONUS', 'Bonus Points'),
        ('ADJUSTMENT', 'Points Adjustment'),
    )
    
    loyalty_card = models.ForeignKey(LoyaltyCard, on_delete=models.CASCADE, related_name='transactions')
    transaction_date = models.DateTimeField(auto_now_add=True)
    points = models.IntegerField()
    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    description = models.CharField(max_length=255)
    location = models.CharField(max_length=100, blank=True, null=True)
    order = models.ForeignKey('marketplace.Order', on_delete=models.SET_NULL, null=True, blank=True, related_name='loyalty_transactions')
    staff_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_transactions')
    
    def __str__(self):
        return f"{self.transaction_type}: {self.points} points - {self.loyalty_card}"


class OTPCredit(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    business = models.ForeignKey('BusinessProfile', on_delete=models.CASCADE, null=True, blank=True)
    otp_timestamp = models.DateTimeField(auto_now_add=True)
    otp_expiry = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.pk:
            # Only set otp_expiry if it's a new object
            self.otp_expiry = timezone.now() + timedelta(minutes=5)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"User: {self.user.phoneNumber} - OTP: {self.otp} - Business: {self.business.business_name if self.business else 'None'}"


class BenefitedPhoneNumber(models.Model):
    phoneNumber = models.CharField(max_length=15, unique=True)
    benefited_timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.phoneNumber


class DeliveryAgent(models.Model):
    """
    Delivery Agents who can recommend customers for Postpaid accounts
    
    Important field distinctions:
    - is_active: Set to True when an agent verifies their phone number via OTP.
                This allows them to log in to the system.
    - is_verified: Set by operations staff to mark an agent as trusted.
                  This allows them to make postpaid recommendations.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='delivery_agent')
    agent_id = models.CharField(max_length=20, unique=True)
    phoneNumber = models.CharField(max_length=15)
    is_active = models.BooleanField(default=False)  # Set to True when agent verifies OTP
    is_verified = models.BooleanField(default=False)  # Set to True by operations staff
    password_hash = models.CharField(max_length=128, null=True, blank=True)
    join_date = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)
    assigned_area = models.CharField(max_length=100, blank=True, null=True)
    total_recommendations = models.PositiveIntegerField(default=0)
    successful_recommendations = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Agent {self.agent_id} - {self.user.get_full_name()}"
    
    def save(self, *args, **kwargs):
        if not self.agent_id:
            # Generate unique agent ID: AG + 6 random characters
            import uuid
            self.agent_id = f"AG{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)
    
    def set_password(self, raw_password):
        """Set agent password"""
        from django.contrib.auth.hashers import make_password
        self.password_hash = make_password(raw_password)
        self.save(update_fields=['password_hash'])
    
    def check_password(self, raw_password):
        """Verify agent password"""
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password_hash)
    
    def recommend_customer(self, customer):
        """Recommend a customer for postpaid upgrade"""
        if not self.is_active:
            return False, "Agent is not active"
        
        # Create a recommendation
        recommendation = AgentRecommendation.objects.create(
            agent=self,
            customer=customer,
            status='PENDING'
        )
        
        # Update agent stats
        self.total_recommendations += 1
        self.save(update_fields=['total_recommendations'])
        
        return True, recommendation

class AdminUser(models.Model):
    """Admin users who can approve/reject Postpaid applications"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='admin_profile')
    admin_id = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100, choices=[
        ('CARDS', 'Card Management'),
        ('FINANCE', 'Finance'),
        ('CUSTOMER', 'Customer Service'),
        ('TECH', 'Technical Support'),
        ('SUPER', 'Super Admin')
    ])
    access_level = models.PositiveSmallIntegerField(default=1)  # 1=Basic, 2=Manager, 3=Super Admin
    is_active = models.BooleanField(default=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.admin_id} - {self.user.get_full_name()} ({self.get_department_display()})"
    
    def save(self, *args, **kwargs):
        if not self.admin_id:
            # Generate unique admin ID: AD + 6 random characters
            import uuid
            self.admin_id = f"AD{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)
    
    def can_approve_postpaid(self):
        """Check if admin can approve postpaid applications"""
        return self.is_active and (
            self.department in ['CARDS', 'FINANCE', 'SUPER'] or 
            self.access_level >= 2
        )

class AgentRecommendation(models.Model):
    """Track agent recommendations for customers"""
    agent = models.ForeignKey(DeliveryAgent, on_delete=models.CASCADE, related_name='recommendations')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='agent_recommendations')
    recommendation_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired')
    ], default='PENDING')
    notes = models.TextField(blank=True, null=True)
    approved_by = models.ForeignKey(AdminUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_recommendations')
    processed_date = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Recommendation by {self.agent.agent_id} for {self.customer.get_full_name()}"
    
    def approve(self, admin_user, notes=None):
        """Approve a recommendation"""
        if self.status != 'PENDING':
            return False, f"Cannot approve recommendation with status: {self.get_status_display()}"
        
        if not admin_user.can_approve_postpaid():
            return False, "Admin does not have permission to approve recommendations"
        
        self.status = 'APPROVED'
        self.approved_by = admin_user
        self.processed_date = timezone.now()
        
        if notes:
            self.notes = notes
            
        self.save()
        
        # Update agent successful recommendations count
        self.agent.successful_recommendations += 1
        self.agent.save(update_fields=['successful_recommendations'])
        
        # Add credit score points for customer (50 points for recommendation)
        try:
            customer_profile = CustomerProfile.objects.get(user=self.customer)
            customer_profile.update_credit_score(50, 'AGENT_RECOMMENDATION')
        except CustomerProfile.DoesNotExist:
            pass
            
        return True, "Recommendation approved successfully"
    
    def reject(self, admin_user, reason):
        """Reject a recommendation"""
        if self.status != 'PENDING':
            return False, f"Cannot reject recommendation with status: {self.get_status_display()}"
            
        self.status = 'REJECTED'
        self.approved_by = admin_user
        self.processed_date = timezone.now()
        self.notes = reason
        self.save()
        
        return True, "Recommendation rejected"

class CreditEvent(models.Model):
    """Track credit score changes based on activities"""
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='credit_events')
    event_type = models.CharField(max_length=30, choices=[
        ('PURCHASE', 'Purchase'),
        ('REPAYMENT', 'Successful Repayment'),
        ('LATE_PAYMENT', 'Late Payment'),
        ('MISSED_PAYMENT', 'Missed Payment'),
        ('AGENT_RECOMMENDATION', 'Agent Recommendation'),
        ('RECYCLING', 'Recycling Activity'),
        ('ADJUSTMENT', 'Manual Adjustment')
    ])
    points_change = models.IntegerField()  # Can be positive or negative
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.customer.username} - {self.event_type}: {self.points_change} points"

class AgentProfile(models.Model):
    """
    Profile for Market Research Agents who collect commodity price data
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='agent_profile')
    agent_id = models.CharField(max_length=20, unique=True)
    national_id = models.CharField(max_length=50, blank=True, null=True)
    region = models.CharField(max_length=100, blank=True, null=True)
    assigned_markets = models.ManyToManyField('market_research.Market', related_name='assigned_agents', blank=True)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True)
    
    # Performance metrics
    total_submissions = models.PositiveIntegerField(default=0)
    approved_submissions = models.PositiveIntegerField(default=0)
    rejected_submissions = models.PositiveIntegerField(default=0)
    submission_quality_score = models.DecimalField(max_digits=3, decimal_places=2, default=5.0)  # Scale: 0-5
    
    # Payment details
    payment_method = models.CharField(max_length=50, choices=[
        ('MOBILE_MONEY', 'Mobile Money'),
        ('BANK', 'Bank Transfer'),
        ('CASH', 'Cash')
    ], default='MOBILE_MONEY')
    mobile_money_number = models.CharField(max_length=15, blank=True, null=True)
    payment_account_details = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Agent {self.agent_id} - {self.user.get_full_name()}"
    
    def save(self, *args, **kwargs):
        if not self.agent_id:
            # Generate unique agent ID: MRA + 6 random characters
            import uuid
            self.agent_id = f"MRA{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)
    
    def update_submission_stats(self, is_approved=True):
        """Update agent statistics after a submission is reviewed"""
        self.total_submissions += 1
        if is_approved:
            self.approved_submissions += 1
        else:
            self.rejected_submissions += 1
        
        # Update quality score - simple calculation based on approval rate
        if self.total_submissions > 0:
            approval_rate = self.approved_submissions / self.total_submissions
            # Scale from 0 to 5 based on approval rate
            self.submission_quality_score = 5.0 * approval_rate
        
        self.save(update_fields=['total_submissions', 'approved_submissions', 
                                'rejected_submissions', 'submission_quality_score'])
    
    @property
    def approval_rate(self):
        """Calculate percentage of approved submissions"""
        if self.total_submissions > 0:
            return (self.approved_submissions / self.total_submissions) * 100
        return 0
