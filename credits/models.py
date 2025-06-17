from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import uuid
import random
from datetime import date, timedelta

class NFCCard(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="nfc_card", null=True, blank=True)
    card_number = models.CharField(max_length=32, unique=True)
    card_type = models.CharField(max_length=10, choices=[('PREPAID', 'Prepaid'), ('POSTPAID', 'Postpaid')], null=True, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    issued_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=False)  # Changed default to False as per card lifecycle
    annual_fee_paid = models.BooleanField(default=False)
    last_annual_fee_date = models.DateField(null=True, blank=True)
    expire_date = models.DateField(null=True, blank=True)
    is_primary = models.BooleanField(default=True)  # Indicates if this is a primary card
    passcode = models.CharField(max_length=4, null=True, blank=True)  # 4-digit passcode for security
    failed_passcode_attempts = models.PositiveSmallIntegerField(default=0)  # Track failed attempts
    is_locked = models.BooleanField(default=False)  # Lock card after too many failed attempts
    status = models.CharField(max_length=20, default="unassigned", choices=[
        ('unassigned', 'Unassigned'),  # Fresh card, just registered
        ('assigned', 'Assigned'),      # Reserved for a customer, not active yet
        ('active', 'Active'),          # Physically activated by NFC tap
        ('expired', 'Expired'),
        ('blocked', 'Blocked'),
        ('lost', 'Lost'),
        ('disabled', 'Disabled')
    ])
    uid = models.CharField(max_length=32, unique=True, null=True, blank=True)  # NFC card UID
    last_used_at = models.DateTimeField(null=True, blank=True)
    registered_by = models.CharField(max_length=20, null=True, blank=True)  # Agent ID who registered the card
    activated_at = models.DateTimeField(null=True, blank=True)  # When the card was activated
    
    def __str__(self):
        if self.user:
            return f"{self.card_number} ({self.user.get_full_name()})"
        return f"{self.card_number} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        # Generate card number if not provided
        if not self.card_number:
            self.card_number = f"KP{uuid.uuid4().hex[:16].upper()}"
            
        # Set expiry date for prepaid cards (6 months from now)
        if self.card_type == 'PREPAID' and not self.expire_date:
            self.expire_date = date.today() + timedelta(days=180)
            
        # For new postpaid cards, set annual fee date
        if self.card_type == 'POSTPAID' and not self.last_annual_fee_date:
            self.last_annual_fee_date = date.today()
            self.annual_fee_paid = True
            
        # Sync is_active with status for backward compatibility
        if self.status == 'active':
            self.is_active = True
        else:
            self.is_active = False
            
        super().save(*args, **kwargs)
    
    def assign_to_customer(self, customer):
        """
        Assign card to a customer but keep it inactive until physical activation
        """
        if self.status != 'unassigned':
            return False, f"Card is already {self.get_status_display()} and cannot be assigned."
            
        self.user = customer
        self.status = 'assigned'  # Only assigned, not active yet
        self.save()
        
        return True, "Card assigned successfully (pending physical activation)."
    
    def activate(self):
        """
        Activate the card after physical NFC tap
        """
        if self.status != 'assigned':
            return False, f"Card with status '{self.get_status_display()}' cannot be activated."
            
        self.status = 'active'
        self.is_locked = True  # Lock for security
        self.last_used_at = timezone.now()
        self.activated_at = timezone.now()
        self.save()
        
        return True, "Card activated successfully."
    
    def deactivate(self, reason='blocked'):
        """
        Deactivate a card
        """
        if self.status not in ['active', 'assigned']:
            return False, f"Card with status '{self.get_status_display()}' cannot be deactivated."
            
        valid_statuses = ['blocked', 'lost', 'disabled']
        if reason not in valid_statuses:
            reason = 'blocked'
            
        self.status = reason
        self.is_locked = True
        self.save()
        
        return True, f"Card has been {reason}."
        
    def is_expired(self):
        if not self.expire_date:
            return False
        return date.today() > self.expire_date
    
    def get_available_credit(self):
        """For postpaid cards, returns available credit"""
        if self.card_type != 'POSTPAID':
            return 0
        return self.credit_limit + self.balance  # Balance may be negative
    
    def is_annual_fee_due(self):
        """Check if annual fee is due for postpaid cards"""
        if self.card_type != 'POSTPAID' or not self.last_annual_fee_date:
            return False
        next_fee_date = self.last_annual_fee_date + timedelta(days=365)
        return date.today() >= next_fee_date and not self.annual_fee_paid
        
    def verify_passcode(self, entered_passcode):
        """Verify the entered passcode and handle security measures"""
        if self.is_locked:
            return False, "Card is locked due to too many failed attempts. Please contact support."
            
        if not self.passcode:
            return True, "No passcode set on this card."
            
        if self.passcode == entered_passcode:
            # Reset failed attempts on successful verification
            self.failed_passcode_attempts = 0
            self.save(update_fields=['failed_passcode_attempts'])
            return True, "Passcode verified successfully."
        else:
            # Increment failed attempts
            self.failed_passcode_attempts += 1
            
            # Lock the card after 3 failed attempts
            if self.failed_passcode_attempts >= 3:
                self.is_locked = True
                self.save(update_fields=['failed_passcode_attempts', 'is_locked'])
                return False, "Card locked due to too many failed attempts. Please contact support."
            
            self.save(update_fields=['failed_passcode_attempts'])
            return False, f"Invalid passcode. {3 - self.failed_passcode_attempts} attempts remaining."
    
    def reset_passcode(self):
        """Reset passcode and unlock card"""
        self.passcode = None
        self.failed_passcode_attempts = 0
        self.is_locked = False
        self.save(update_fields=['passcode', 'failed_passcode_attempts', 'is_locked'])
        
    def set_passcode(self, new_passcode):
        """Set a new passcode for the card"""
        if len(new_passcode) != 4 or not new_passcode.isdigit():
            return False, "Passcode must be exactly 4 digits."
            
        self.passcode = new_passcode
        self.failed_passcode_attempts = 0
        self.is_locked = False
        self.save(update_fields=['passcode', 'failed_passcode_attempts', 'is_locked'])
        return True, "Passcode set successfully."
        
    @staticmethod
    def generate_random_passcode():
        """Generate a random 4-digit passcode"""
        return ''.join(random.choices('0123456789', k=4))


class CreditTransaction(models.Model):
    card = models.ForeignKey(NFCCard, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    type = models.CharField(max_length=20, choices=[

        ('TOPUP', 'Top-Up'),
        ('PURCHASE', 'Purchase'),
        ('RECYCLE_REWARD', 'Recycle Reward')
    ])
    description = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_type_display()} of {self.amount} for {self.card.card_number}"


class VendorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='vendor_profile')
    business_name = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    vendor_type = models.CharField(max_length=10, choices=[
        ('SHOP', 'Shop'),
        ('MOBILE', 'Mobile'),
        ('STALL', 'Stall')
    ])

    def __str__(self):
        return self.business_name


class Product(models.Model):
    vendor = models.ForeignKey(VendorProfile, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.price} credits"


class RecyclingDeposit(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='recycling_deposits')
    material_type = models.CharField(max_length=20, choices=[
        ('PLASTIC', 'Plastic'), 
        ('PAPER', 'Paper'), 
        ('METAL', 'Metal')
    ])
    weight_grams = models.PositiveIntegerField()
    credits_earned = models.DecimalField(max_digits=10, decimal_places=2)
    location = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        # Calculate credits: 1 credit per 250g
        self.credits_earned = Decimal(self.weight_grams) / Decimal(250)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.weight_grams}g of {self.get_material_type_display()}"


class Order(models.Model):
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    paid_with_credits = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - {self.product.name if self.product else 'Unknown'}"


class TransactionLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=[
        ('TOPUP', 'Top-Up'),
        ('PURCHASE', 'Purchase'),
        ('REDEEM', 'Redeem'),
        ('RECYCLE', 'Recycle'),
        ('FEE', 'Fee'),
        ('DISCOUNT', 'Discount'),
        ('CREDIT_LIMIT', 'Credit Limit Adjustment')
    ])
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    result = models.CharField(max_length=10, choices=[
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed')
    ])
    metadata = models.JSONField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_action_display()} by {self.actor.get_full_name()} - {self.get_result_display()}"


class CreditScore(models.Model):
    """Credit score for users to determine eligibility for postpaid cards and discounts"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='credit_score')
    score = models.IntegerField(default=500)  # Range: 0-1000
    last_updated = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.get_full_name()} - Score: {self.score}"
    
    def update_score(self, action, amount=None):
        """Update credit score based on user actions"""
        # Initialize change value
        change = 0
        
        # Positive actions
        if action == 'ON_TIME_PAYMENT':
            change = min(20, int(amount / 5000)) if amount else 10  # Larger payments increase score more
        elif action == 'RECYCLE':
            change = 5  # Reward sustainable behavior
        elif action == 'LONG_TERM_USER':
            change = 15  # Loyalty bonus
            
        # Negative actions
        elif action == 'LATE_PAYMENT':
            change = -15
        elif action == 'MISSED_PAYMENT':
            change = -30
        elif action == 'OVERDRAFT':
            change = -20
            
        # Apply change with bounds checking
        self.score = max(0, min(1000, self.score + change))
        self.save()
        
    def get_score_category(self):
        """Get the category of credit score"""
        if self.score >= 800:
            return "Excellent"
        elif self.score >= 650:
            return "Good"
        elif self.score >= 500:
            return "Fair"
        elif self.score >= 350:
            return "Poor"
        else:
            return "Very Poor"
    
    def is_eligible_for_postpaid(self):
        """Check if user is eligible for postpaid card based on score"""
        return self.score >= 500
    
    def is_eligible_for_discount(self):
        """Check if user is eligible for holiday discounts"""
        return self.score >= 650  # Good or excellent score


class LinkedCard(models.Model):
    """Secondary cards linked to a primary card"""
    primary_card = models.ForeignKey(NFCCard, on_delete=models.CASCADE, related_name='linked_cards')
    card_number = models.CharField(max_length=32, unique=True)
    issued_to = models.CharField(max_length=100, help_text="Name of the person this card is issued to")
    relationship = models.CharField(max_length=50, help_text="Relationship to primary cardholder (e.g., Spouse, Child)")
    issued_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    expire_date = models.DateField(null=True, blank=True)
    spending_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0, 
                                       help_text="Monthly spending limit for this linked card")
    
    def __str__(self):
        return f"{self.card_number} - Linked to {self.primary_card.user.get_full_name()}"
    
    def save(self, *args, **kwargs):
        # Generate card number if not provided
        if not self.card_number:
            self.card_number = f"KP-L{uuid.uuid4().hex[:14].upper()}"
            
        # Set expiry date same as primary card if not specified
        if not self.expire_date and self.primary_card.expire_date:
            self.expire_date = self.primary_card.expire_date
            
        super().save(*args, **kwargs)


class CardApplication(models.Model):
    """Track applications for new cards"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='card_applications')
    card_type = models.CharField(max_length=10, choices=[('PREPAID', 'Prepaid'), ('POSTPAID', 'Postpaid')])
    application_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    linked_cards_requested = models.PositiveSmallIntegerField(default=0, help_text="Number of additional linked cards requested")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_applications')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    initial_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_confirmed = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_card_type_display()} Card Application"
    
    def approve(self, reviewed_by, credit_limit=0, passcode=None):
        """Approve the application and create the card"""
        with models.transaction.atomic():
            self.status = 'APPROVED'
            self.reviewed_by = reviewed_by
            self.reviewed_at = timezone.now()
            self.save()
            
            # Check if this application has a passcode stored in notes
            card_passcode = None
            if self.notes and "Passcode set for card:" in self.notes:
                try:
                    # Extract passcode from notes (stored temporarily during application)
                    card_passcode = self.notes.split("Passcode set for card:")[1].strip()
                except:
                    pass
            
            # Use provided passcode parameter if available, otherwise use the one from notes
            if passcode:
                card_passcode = passcode
            
            # Generate random passcode if none provided
            if not card_passcode and self.card_type == 'POSTPAID':
                card_passcode = NFCCard.generate_random_passcode()
            
            # Create the card
            card = NFCCard.objects.create(
                user=self.user,
                card_type=self.card_type,
                balance=self.initial_deposit if self.card_type == 'PREPAID' else 0,
                credit_limit=credit_limit if self.card_type == 'POSTPAID' else 0,
                is_active=True,
                passcode=card_passcode
            )
            
            # Create transaction record for initial deposit if prepaid
            if self.card_type == 'PREPAID' and self.initial_deposit > 0:
                CreditTransaction.objects.create(
                    card=card,
                    amount=self.initial_deposit,
                    type='TOPUP',
                    description=f"Initial deposit for new {self.get_card_type_display()} card"
                )
                
            # Create transaction record for annual fee if postpaid
            if self.card_type == 'POSTPAID':
                CreditTransaction.objects.create(
                    card=card,
                    amount=-2000,  # 2,000 TSh annual fee
                    type='FEE',
                    description="Annual maintenance fee"
                )
                
            # Send notification about card creation with passcode info if applicable
            if card_passcode and self.card_type == 'POSTPAID':
                from .views import send_card_notification
                try:
                    message = f"Your Kikapu {self.get_card_type_display()} Card has been approved! Card number: {card.card_number[-4:]}. Your 4-digit passcode will be required for transactions."
                    send_card_notification(self.user.phoneNumber, message)
                except:
                    # Log error but don't interrupt the process
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to send card notification for new card {card.card_number}")
            
            return card
    
    def reject(self, reviewed_by, reason):
        """Reject the application"""
        self.status = 'REJECTED'
        self.reviewed_by = reviewed_by
        self.reviewed_at = timezone.now()
        self.notes = reason
        self.save()


class HolidayDiscountCampaign(models.Model):
    """Manage holiday discount campaigns"""
    name = models.CharField(max_length=100)
    discount_percentage = models.PositiveIntegerField(default=20)  # Default 20%
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)
    min_credit_score = models.PositiveIntegerField(default=650)  # Minimum score to qualify
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.discount_percentage}% off)"
    
    def is_campaign_active(self):
        """Check if campaign is currently active"""
        today = date.today()
        return self.is_active and self.start_date <= today <= self.end_date
    
    def user_qualifies(self, user):
        """Check if a user qualifies for this discount"""
        if not self.is_campaign_active():
            return False
            
        try:
            # Check if user has an active card
            card = user.nfc_card
            if not card.is_active or card.is_expired():
                return False
                
            # Check if user has required credit score
            try:
                credit_score = user.credit_score
                return credit_score.score >= self.min_credit_score
            except CreditScore.DoesNotExist:
                return False
                
        except NFCCard.DoesNotExist:
            return False
