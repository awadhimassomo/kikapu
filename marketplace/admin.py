from django.contrib import admin
from .models import (
    Category, Product, ProductImage, ProductProcessingMethod,
    Order, OrderItem, DeliveryAddress, 
    BusinessNotification, Cart, CartItem,
    Purchase, ProductAssociation, RelatedProduct,
    DeliveryGroup, GroupOrder
)

# Inlines
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

class ProductProcessingMethodInline(admin.TabularInline):
    model = ProductProcessingMethod
    extra = 1

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('subtotal',)

class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ('subtotal',)

class GroupOrderInline(admin.TabularInline):
    model = GroupOrder
    extra = 0
    fields = ('order', 'member', 'added_by_leader', 'name', 'phone', 'leader_discount_applied', 'discount_amount')
    readonly_fields = ('discount_amount',)

# Admin classes
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'description')
    list_filter = ('parent',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'business', 'category', 'price', 'unit', 'stock_quantity', 'is_available', 'created_at')
    list_filter = ('is_available', 'category', 'business', 'unit')
    search_fields = ('name', 'description', 'business__business_name')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ProductImageInline, ProductProcessingMethodInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'business', 'category', 'description')
        }),
        ('Pricing and Stock', {
            'fields': ('price', 'unit', 'stock_quantity', 'is_available')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'image', 'is_primary')
    list_filter = ('is_primary', 'product')
    search_fields = ('product__name',)

@admin.register(ProductProcessingMethod)
class ProductProcessingMethodAdmin(admin.ModelAdmin):
    list_display = ('product', 'method_display', 'is_default')
    list_filter = ('method', 'is_default')
    search_fields = ('product__name',)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'get_customer_name', 'status', 'delivery_option', 
                    'total_amount', 'order_date')
    list_filter = ('status', 'delivery_option', 'order_date')
    search_fields = ('order_number', 'customer__user__email',
                     'customer__user__firstName', 'customer__user__lastName')
    readonly_fields = ('order_date', 'updated_at')
    inlines = [OrderItemInline]
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'customer', 'status', 'subtotal', 'delivery_fee', 'total_amount')
        }),

        ('Delivery Details', {
            'fields': ('shipping_address', 'delivery_address', 'delivery_location', 'delivery_option',
                       'delivery_method', 'scheduled_delivery_date', 'scheduled_delivery_time',
                       'delivery_notes', 'latitude', 'longitude', 'delivery_group')
        }),
        ('Timing Information', {
            'fields': ('estimated_delivery_time', 'actual_delivery_time', 'order_date', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_customer_name(self, obj):
        return f"{obj.customer.user.firstName} {obj.customer.user.lastName}"
    get_customer_name.short_description = 'Customer'

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'price', 'processing_method_display', 'subtotal')
    list_filter = ('processing_method', 'order__status')
    search_fields = ('order__order_number', 'product__name')
    readonly_fields = ('subtotal',)

@admin.register(DeliveryAddress)
class DeliveryAddressAdmin(admin.ModelAdmin):
    list_display = ('customer', 'address_line_1', 'city', 'region', 'is_default')
    list_filter = ('is_default', 'city', 'region')
    search_fields = ('customer__user__email', 'address_line_1', 'city', 'region', 'landmark')

@admin.register(BusinessNotification)
class BusinessNotificationAdmin(admin.ModelAdmin):
    list_display = ('business', 'notification_type', 'title', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('business__business_name', 'title', 'message')
    readonly_fields = ('created_at',)

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'total', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [CartItemInline]

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'product', 'quantity', 'subtotal')
    list_filter = ('created_at',)
    search_fields = ('cart__user__username', 'product__name')
    readonly_fields = ('subtotal',)

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'order_id', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('product__name', 'user__username', 'order_id')
    date_hierarchy = 'timestamp'

@admin.register(ProductAssociation)
class ProductAssociationAdmin(admin.ModelAdmin):
    list_display = ('product', 'recommendation', 'confidence', 'lift', 'support', 'last_updated')
    list_filter = ('last_updated',)
    search_fields = ('product__name', 'recommendation__name')
    readonly_fields = ('last_updated',)
    ordering = ('-lift',)

@admin.register(RelatedProduct)
class RelatedProductAdmin(admin.ModelAdmin):
    list_display = ('product', 'related_product', 'relationship_type', 'relevance_score', 'created_at')
    list_filter = ('relationship_type', 'relevance_score', 'created_at')
    search_fields = ('product__name', 'related_product__name', 'notes')
    ordering = ('-relevance_score', 'product__name')
    raw_id_fields = ('product', 'related_product')
    fieldsets = (
        ('Relationship', {
            'fields': ('product', 'related_product', 'relationship_type', 'relevance_score')
        }),
        ('Additional Information', {
            'fields': ('notes',)
        }),
    )

@admin.register(DeliveryGroup)
class DeliveryGroupAdmin(admin.ModelAdmin):
    list_display = ('code', 'leader', 'delivery_date', 'time_slot', 'is_active', 'get_member_count', 'created_at')
    list_filter = ('is_active', 'delivery_date', 'time_slot')
    search_fields = ('code', 'leader__user__username', 'leader__user__email')
    readonly_fields = ('code', 'created_at', 'expires_at', 'shared_link')
    fieldsets = (
        ('Basic Info', {'fields': ('code', 'leader', 'is_active')}),
        ('Delivery Details', {'fields': ('delivery_date', 'time_slot')}),
        ('Sharing', {'fields': ('shared_link',)}),
        ('Timing', {'fields': ('created_at', 'expires_at')}),
    )
    inlines = [GroupOrderInline]
    
    def get_member_count(self, obj):
        return obj.get_member_count()
    get_member_count.short_description = 'Members'

@admin.register(GroupOrder)
class GroupOrderAdmin(admin.ModelAdmin):
    list_display = ('order', 'group', 'member', 'added_by_leader', 'name', 'phone', 'leader_discount_applied')
    list_filter = ('added_by_leader', 'leader_discount_applied', 'group__delivery_date')
    search_fields = ('order__order_number', 'group__code', 'member__user__username', 'name', 'phone')
    readonly_fields = ('discount_amount', 'created_at', 'updated_at')
    fieldsets = (
        ('Basic Info', {'fields': ('group', 'order', 'member')}),
        ('Added by Leader', {'fields': ('added_by_leader', 'name', 'phone')}),
        ('Discount', {'fields': ('leader_discount_applied', 'discount_amount')}),
        ('Timing', {'fields': ('created_at', 'updated_at')}),
    )
