from rest_framework import serializers
from .models import DeliverySchedule, ScheduledItem, Product, Order, ProductProcessingMethod, ProductImage

class ProductProcessingMethodSerializer(serializers.ModelSerializer):
    """Serializer for product processing methods"""
    name = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    additional_cost = serializers.DecimalField(max_digits=10, decimal_places=2, default=0, required=False)
    
    class Meta:
        model = ProductProcessingMethod
        fields = ['id', 'method', 'name', 'description', 'is_default', 'additional_cost']
    
    def get_name(self, obj):
        """Get the display name for the processing method"""
        return dict(Product.PROCESSING_CHOICES).get(obj.method, 'None/Raw')
        
    def get_description(self, obj):
        """Get a description for the processing method"""
        return f"Product with {self.get_name(obj)} processing"

class ProductImageSerializer(serializers.ModelSerializer):
    """Serializer for product images"""
    class Meta:
        model = ProductImage
        fields = ['id', 'image', 'is_primary']

class ProductDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for product information including processing methods"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    processing_methods = ProductProcessingMethodSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    
    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'stock_quantity', 
                 'category', 'category_name', 'processing_methods', 
                 'images', 'unit', 'is_available']

class ScheduledItemSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    product_price = serializers.SerializerMethodField()
    
    class Meta:
        model = ScheduledItem
        fields = ['id', 'product', 'product_name', 'product_price', 'quantity', 'processing_method']
        
    def get_product_name(self, obj):
        return obj.product.name
        
    def get_product_price(self, obj):
        return obj.product.price


class DeliveryScheduleSerializer(serializers.ModelSerializer):
    items = ScheduledItemSerializer(source='scheduleditems', many=True, read_only=True)
    customer_name = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = DeliverySchedule
        fields = [
            'id', 'customer', 'customer_name', 'is_recurring', 'recurrence_type', 
            'delivery_date', 'time_slot', 'delivery_address', 'items', 
            'notes', 'is_active', 'created_at', 'total_amount'
        ]
        read_only_fields = ['created_at', 'times_fulfilled', 'times_skipped', 'times_modified']
        
    def get_customer_name(self, obj):
        return f"{obj.customer.user.firstName} {obj.customer.user.lastName}"
        
    def get_total_amount(self, obj):
        return obj.get_items_total()


class CreateDeliveryScheduleSerializer(serializers.ModelSerializer):
    items = serializers.ListField(write_only=True)
    
    class Meta:
        model = DeliverySchedule
        fields = [
            'customer', 'is_recurring', 'recurrence_type', 'delivery_date', 
            'time_slot', 'delivery_address', 'items', 'notes'
        ]
        
    def validate(self, data):
        if data.get('is_recurring') and not data.get('recurrence_type'):
            raise serializers.ValidationError("Recurrence type must be specified for recurring schedules")
            
        if not data.get('is_recurring') and not data.get('delivery_date'):
            raise serializers.ValidationError("Delivery date must be specified for one-time schedules")
            
        # Validate items
        items = data.get('items', [])
        if not items:
            raise serializers.ValidationError("At least one product must be specified")
            
        return data
        
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        schedule = DeliverySchedule.objects.create(**validated_data)
        
        # Create scheduled items
        for item_data in items_data:
            product_id = item_data.get('product')
            quantity = item_data.get('quantity', 1)
            processing_method = item_data.get('processing_method', 'NONE')
            
            try:
                product = Product.objects.get(id=product_id)
                ScheduledItem.objects.create(
                    schedule=schedule,
                    product=product,
                    quantity=quantity,
                    processing_method=processing_method
                )
            except Product.DoesNotExist:
                pass  # Skip invalid products
                
        return schedule
        
        
class ScheduleFromOrderSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    is_recurring = serializers.BooleanField(default=False)
    recurrence_type = serializers.ChoiceField(
        choices=[('weekly', 'Weekly'), ('monthly', 'Monthly')],
        required=False
    )
    delivery_date = serializers.DateField(required=False)
    time_slot = serializers.ChoiceField(
        choices=[('morning', '8AM–11AM'), ('afternoon', '12PM–3PM'), ('evening', '4PM–7PM')]
    )
    
    def validate(self, data):
        if data.get('is_recurring') and not data.get('recurrence_type'):
            raise serializers.ValidationError("Recurrence type must be specified for recurring schedules")
            
        if not data.get('is_recurring') and not data.get('delivery_date'):
            raise serializers.ValidationError("Delivery date must be specified for one-time schedules")
            
        # Validate order exists
        order_id = data.get('order_id')
        try:
            Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            raise serializers.ValidationError("Invalid order ID")
            
        return data