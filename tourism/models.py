from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class FarmExperience(models.Model):
    EXPERIENCE_TYPES = (
        ('FARMHOUSE', 'Farmhouse Retreat'),
        ('RESTAURANT', 'Farm Restaurant'),
    )

    title = models.CharField(max_length=200)
    experience_type = models.CharField(max_length=20, choices=EXPERIENCE_TYPES)
    description = models.TextField()
    image = models.ImageField(upload_to='farm_experiences/')
    location = models.CharField(max_length=255)
    price_per_day = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    available = models.BooleanField(default=True)
    link_to_booking = models.URLField(blank=True, help_text="If hosted externally (optional)")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Booking(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    experience = models.ForeignKey(FarmExperience, on_delete=models.CASCADE, related_name='bookings')
    booking_number = models.CharField(max_length=20, unique=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)  # For farmhouse stays
    party_size = models.PositiveIntegerField(default=1)
    special_requests = models.TextField(blank=True)
    contact_phone = models.CharField(max_length=20)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    payment_method = models.CharField(max_length=50, default='MOBILE_MONEY')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Booking #{self.booking_number} - {self.experience.title}"
    
    def generate_booking_number(self):
        """Generate a unique booking number"""
        if not self.booking_number:
            # Format: TB-YYYYMMDD-XXXX (TB = Tourism Booking)
            import datetime
            import random
            import string
            
            date_str = timezone.now().strftime('%Y%m%d')
            random_str = ''.join(random.choices(string.digits, k=4))
            self.booking_number = f"TB-{date_str}-{random_str}"
        
        return self.booking_number
    
    def save(self, *args, **kwargs):
        if not self.booking_number:
            self.generate_booking_number()
        super().save(*args, **kwargs)
