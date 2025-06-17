from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import uuid
import random
from datetime import date, timedelta
import json

# Import models from credits app instead of redefining them
from credits.models import (
    NFCCard, 
    CreditTransaction,
    VendorProfile,
    Product,
    RecyclingDeposit,
    Order,
    TransactionLog,
    CreditScore,
    LinkedCard,
    CardApplication,
    HolidayDiscountCampaign
)

# Market Research models
class Commodity(models.Model):
    CATEGORY_CHOICES = [
        ('grains', 'Grains'),
        ('vegetables', 'Vegetables'),
        ('fruits', 'Fruits'),
        ('meat', 'Meat'),
        ('dairy', 'Dairy'),
        ('other', 'Other'),
    ]
    
    UNIT_CHOICES = [
        ('kg', 'Kilogram (kg)'),
        ('g', 'Gram (g)'),
        ('piece', 'Piece'),
        ('bunch', 'Bunch'),
        ('liter', 'Liter'),
        ('ml', 'Milliliter'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='other')
    default_unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='kg')
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Commodities'
        ordering = ['name']
    
    def __str__(self):
        return self.name

class Market(models.Model):
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    region = models.CharField(max_length=100)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} - {self.location}"

class Source(models.Model):
    SOURCE_TYPE_CHOICES = [
        ('market', 'Market'),
        ('processor', 'Processor'),
        ('kiosk', 'Kiosk'),
        ('farm', 'Farm'),
        ('store', 'Retail Store'),
        ('distributor', 'Distributor'),
        ('other', 'Other'),
    ]
    name = models.CharField(max_length=200)
    source_type = models.CharField(max_length=50, choices=SOURCE_TYPE_CHOICES, default='market')
    location = models.CharField(max_length=200)
    region = models.CharField(max_length=100)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    transportation_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, 
                                            help_text="Cost to transport goods to/from this source")
    # Optional link to a Market (for backward compatibility with market source type)
    market = models.OneToOneField(Market, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='source_link')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_source_type_display()}) - {self.location}"

class MarketPriceResearch(models.Model):
    # Mandatory fields matching requirements document
    SOURCE_TYPE_CHOICES = [
        ('market', 'Market place'),
        ('processor', 'Processor'),
        ('kiosk', 'Kiosk'),
        ('farm', 'Farm'),
        ('store', 'Retail Store'),
        ('distributor', 'Distributor'),
        ('other', 'Other')
    ]
    # Primary relationships
    source = models.ForeignKey(Source, on_delete=models.SET_NULL, related_name='price_research', null=True, blank=True)
    commodity = models.ForeignKey(Commodity, on_delete=models.CASCADE, related_name='price_records', null=True, blank=True)
    
    # Keep product_name for backward compatibility
    product_name = models.CharField(max_length=200)
    
    # Keep source fields for backward compatibility
    source_type = models.CharField(max_length=50, choices=SOURCE_TYPE_CHOICES, default='market')
    source_name = models.CharField(max_length=200, default='Unknown Source')
    
    # Price information
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    UNIT_CHOICES = [
        ('kg', 'Kilogram (kg)'),
        ('bunch', 'Bunch'),
        ('piece', 'Piece'),
        ('crate', 'Crate'),
        ('kiroba', 'Kiroba'),
        ('sado', 'Sado'),
        ('fungu', 'Fungu'),
        ('g', 'Gram (g)'),
        ('liter', 'Liter'),
        ('ml', 'Milliliter'),
    ]
    unit = models.CharField(max_length=50, choices=UNIT_CHOICES)
    
    # Collection metadata
    date_observed = models.DateTimeField(default=timezone.now)  # When the data was collected
    collected_by = models.CharField(max_length=100, null=True, blank=True)  # Name or ID of the collector
    
    # Legacy/additional fields
    region = models.CharField(max_length=100, default='')
    country = models.CharField(max_length=100, default='Tanzania')
    submission_date = models.DateTimeField(null=True, blank=True)
    
    @property
    def unit_price(self):
        """Calculate price per unit (e.g., price per kg)"""
        if self.quantity and self.quantity > 0:
            return self.price / self.quantity
        return self.price
    
    # Optional fields - can be null
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='market_research', 
                              null=True, blank=True, limit_choices_to={'user_type': 'AGENT'})
    quality_rating = models.PositiveSmallIntegerField(
        choices=[(1, 'Poor'), (2, 'Fair'), (3, 'Good'), (4, 'Excellent')],
        null=True, blank=True
    )
    remarks = models.TextField(blank=True, null=True)  # Renamed from notes to remarks as per requirements
    
    # Weather data at time of observation
    temperature = models.FloatField(null=True, blank=True)
    rainfall = models.FloatField(null=True, blank=True)
    
    # Location data
    latitude = models.FloatField(null=True, blank=True)  # For specific pricing location
    longitude = models.FloatField(null=True, blank=True)
    
    def __str__(self):
        market_name = self.source_name
        product_name = self.commodity.name if self.commodity else self.product_name
        return f"{product_name} at {market_name} - {self.price}/{self.unit}"

# Offline sync models
class UnsyncedData(models.Model):
    """
    Stores data that was collected offline and needs to be synchronized with the server.
    Used to track sync status and manage retry attempts.
    """
    DATA_TYPE_CHOICES = [
        ('price', 'Price Research'),
        ('sale', 'Sales Data'),
        ('stock_update', 'Stock Update'),
    ]
    
    SYNC_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SYNCING', 'Syncing'),
        ('SYNCED', 'Synced'),
        ('FAILED', 'Failed'),
        ('CONFLICT', 'Conflict'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device_id = models.CharField(max_length=255, help_text="Unique identifier of the device that collected the data")
    data_type = models.CharField(max_length=20, choices=DATA_TYPE_CHOICES)
    payload = models.JSONField(help_text="The actual data to be synchronized")
    sync_status = models.CharField(max_length=20, choices=SYNC_STATUS_CHOICES, default='PENDING')
    timestamp = models.DateTimeField(default=timezone.now, help_text="When the data was initially created")
    last_attempt = models.DateTimeField(null=True, blank=True, help_text="Last sync attempt")
    retry_count = models.PositiveSmallIntegerField(default=0, help_text="Number of sync attempts")
    error_message = models.TextField(blank=True, null=True, help_text="Error details if sync fails")
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='unsynced_data', 
                              null=True, limit_choices_to={'user_type': 'AGENT'})
    
    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['sync_status']),
            models.Index(fields=['data_type']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['device_id']),
        ]
    
    def __str__(self):
        return f"{self.data_type} - {self.sync_status} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    
    def get_payload_object(self):
        """Returns the payload as a Python dictionary"""
        if isinstance(self.payload, str):
            return json.loads(self.payload)
        return self.payload
    
    def mark_as_syncing(self):
        """Mark this data as being synced now"""
        self.sync_status = 'SYNCING'
        self.last_attempt = timezone.now()
        self.retry_count += 1
        self.save(update_fields=['sync_status', 'last_attempt', 'retry_count'])
    
    def mark_as_synced(self):
        """Mark this data as successfully synced"""
        self.sync_status = 'SYNCED'
        self.save(update_fields=['sync_status'])
    
    def mark_as_failed(self, error_message=None):
        """Mark this data as failed to sync"""
        self.sync_status = 'FAILED'
        if error_message:
            self.error_message = error_message
        self.save(update_fields=['sync_status', 'error_message'])
    
    def mark_as_conflict(self, error_message=None):
        """Mark this data as having a conflict requiring resolution"""
        self.sync_status = 'CONFLICT'
        if error_message:
            self.error_message = error_message
        self.save(update_fields=['sync_status', 'error_message'])


class SyncLog(models.Model):
    """
    Logs all synchronization attempts, both successful and failed.
    Provides an audit trail for data synchronization.
    """
    STATUS_CHOICES = [
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('CONFLICT', 'Conflict'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    data = models.ForeignKey(UnsyncedData, on_delete=models.CASCADE, related_name='sync_logs')
    sync_time = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    response = models.JSONField(null=True, blank=True, help_text="Server response or error message")
    
    class Meta:
        ordering = ['-sync_time']
    
    def __str__(self):
        return f"{self.data.data_type} - {self.status} - {self.sync_time.strftime('%Y-%m-%d %H:%M')}"
