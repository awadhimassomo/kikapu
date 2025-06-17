from django.db import models
from django.utils import timezone
from registration.models import User

class ProductCategory(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, null=True)  # For FontAwesome icons
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = 'Product categories'

class Unit(models.Model):
    name = models.CharField(max_length=50)
    abbreviation = models.CharField(max_length=10)
    
    def __str__(self):
        return self.abbreviation

class Region(models.Model):
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name

class Listing(models.Model):
    TYPE_CHOICES = (
        ('buy', 'I want to buy'),
        ('sell', 'I want to sell'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='listings')
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, blank=True, null=True)
    type = models.CharField(max_length=4, choices=TYPE_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title

class ListingImage(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='tradepoint/listings/')
    order = models.PositiveSmallIntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"Image {self.order} for {self.listing.title}"

class ListingInterest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('contacted', 'Contacted'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='interests')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interested_listings')
    message = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ('listing', 'user')
        verbose_name_plural = 'Listing interests'
    
    def __str__(self):
        return f"{self.user.get_full_name()} interested in {self.listing.title}"
