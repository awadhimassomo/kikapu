from django.contrib import admin
from .models import ProductCategory, Unit, Region, Listing, ListingImage, ListingInterest

# Register product categories
@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

# Register units
@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'abbreviation')
    search_fields = ('name', 'abbreviation')

# Register regions
@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

# Register listing images inline
class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 1

# Register listing interests inline
class ListingInterestInline(admin.TabularInline):
    model = ListingInterest
    extra = 0
    readonly_fields = ('user', 'created_at')

# Register listings
@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'category', 'region', 'price', 'type', 'is_active', 'created_at')
    list_filter = ('is_active', 'type', 'category', 'region', 'created_at')
    search_fields = ('title', 'description', 'user__email', 'user__first_name', 'user__last_name')
    date_hierarchy = 'created_at'
    inlines = [ListingImageInline, ListingInterestInline]

# Register listing interests (for direct access)
@admin.register(ListingInterest)
class ListingInterestAdmin(admin.ModelAdmin):
    list_display = ('user', 'listing', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'listing__title')
    date_hierarchy = 'created_at'
