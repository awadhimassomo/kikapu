from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.urls import reverse

from .models import ProductCategory, Unit, Region, Listing, ListingImage, ListingInterest
from registration.models import User

# Main listing page view
def index(request):
    categories = ProductCategory.objects.all()
    regions = Region.objects.all()
    
    # Base queryset
    listings = Listing.objects.filter(is_active=True).order_by('-created_at')
    
    # Apply search filters
    search_query = request.GET.get('search', '')
    listing_type = request.GET.get('type', '')
    category_id = request.GET.get('category', '')
    region_id = request.GET.get('region', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    sort_by = request.GET.get('sort', 'date_desc')
    
    if search_query:
        listings = listings.filter(
            Q(title__icontains=search_query) | 
            Q(description__icontains=search_query) | 
            Q(additional_details__icontains=search_query)
        )
    
    if listing_type:
        listings = listings.filter(listing_type=listing_type)
    
    if category_id:
        listings = listings.filter(category_id=category_id)
    
    if region_id:
        listings = listings.filter(region_id=region_id)
    
    if min_price and min_price.isdigit():
        listings = listings.filter(price__gte=min_price)
    
    if max_price and max_price.isdigit():
        listings = listings.filter(price__lte=max_price)
    
    # Apply sorting
    if sort_by == 'date_asc':
        listings = listings.order_by('created_at')
    elif sort_by == 'price_asc':
        listings = listings.order_by('price')
    elif sort_by == 'price_desc':
        listings = listings.order_by('-price')
    else:  # Default: date_desc
        listings = listings.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(listings, 12)  # Show 12 listings per page
    page = request.GET.get('page')
    
    try:
        listings = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page
        listings = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page of results
        listings = paginator.page(paginator.num_pages)
    
    context = {
        'listings': listings,
        'categories': categories,
        'regions': regions,
        'is_paginated': paginator.num_pages > 1,
        'page_obj': listings,
    }
    
    return render(request, 'tradepoint/index.html', context)

# Dashboard for users to manage their listings
@login_required
def dashboard(request):
    user = request.user
    
    # Get user's listings
    user_listings = Listing.objects.filter(user=user).order_by('-created_at')
    
    # Get interests received
    interests_received = ListingInterest.objects.filter(
        listing__user=user
    ).select_related('user', 'listing').order_by('-created_at')
    
    # Get interests sent
    interests_sent = ListingInterest.objects.filter(
        user=user
    ).select_related('listing', 'listing__user').order_by('-created_at')
    
    # Get total view count for all user's listings
    total_views = sum(listing.view_count or 0 for listing in user_listings)
    
    context = {
        'user_listings': user_listings,
        'interests_received': interests_received,
        'interests_sent': interests_sent,
        'active_listings_count': user_listings.filter(is_active=True).count(),
        'interests_received_count': interests_received.count(),
        'total_views': total_views,
    }
    
    return render(request, 'tradepoint/dashboard.html', context)

# Detailed view for a specific listing
def listing_detail(request, listing_id):
    listing = get_object_or_404(Listing, id=listing_id)
    listing_images = ListingImage.objects.filter(listing=listing)
    
    # Increment view count
    if request.user != listing.user:
        listing.view_count = (listing.view_count or 0) + 1
        listing.save(update_fields=['view_count'])
    
    # Check if the current user has already shown interest
    user_has_shown_interest = False
    if request.user.is_authenticated:
        user_has_shown_interest = ListingInterest.objects.filter(
            listing=listing, 
            user=request.user
        ).exists()
    
    # Get similar listings
    similar_listings = Listing.objects.filter(
        is_active=True,
        category=listing.category
    ).exclude(id=listing.id).order_by('-created_at')[:3]
    
    context = {
        'listing': listing,
        'listing_images': listing_images,
        'user_has_shown_interest': user_has_shown_interest,
        'similar_listings': similar_listings,
    }
    
    return render(request, 'tradepoint/listing_detail.html', context)

# Form for creating a new listing
@login_required
def create_listing(request):
    if request.method == 'POST':
        # Handle form submission
        title = request.POST.get('title')
        listing_type = request.POST.get('listing_type')
        category_id = request.POST.get('category')
        region_id = request.POST.get('region')
        price = request.POST.get('price')
        quantity = request.POST.get('quantity')
        unit_id = request.POST.get('unit')
        description = request.POST.get('description')
        additional_details = request.POST.get('additional_details')
        contact_phone = request.POST.get('contact_phone')
        contact_whatsapp = request.POST.get('contact_whatsapp')
        contact_email = request.POST.get('contact_email')
        
        # Validate required fields
        if not all([title, listing_type, category_id, region_id, description, contact_phone]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'tradepoint/create_listing.html', {
                'form': request.POST,
                'categories': ProductCategory.objects.all(),
                'regions': Region.objects.all(),
                'units': Unit.objects.all(),
            })
        
        # Create the listing
        listing = Listing.objects.create(
            user=request.user,
            title=title,
            listing_type=listing_type,
            category_id=category_id,
            region_id=region_id,
            price=price if price else None,
            quantity=quantity if quantity else None,
            unit_id=unit_id if unit_id else None,
            description=description,
            additional_details=additional_details,
            contact_phone=contact_phone,
            contact_whatsapp=contact_whatsapp,
            contact_email=contact_email,
            is_active=True
        )
        
        # Handle images
        images = request.FILES.getlist('images')
        for image in images:
            ListingImage.objects.create(
                listing=listing,
                image=image
            )
        
        messages.success(request, 'Your listing has been created successfully!')
        return redirect('tradepoint:listing_detail', listing_id=listing.id)
    
    # Display the form
    context = {
        'categories': ProductCategory.objects.all(),
        'regions': Region.objects.all(),
        'units': Unit.objects.all(),
    }
    
    return render(request, 'tradepoint/create_listing.html', context)

# Form for updating an existing listing
@login_required
def update_listing(request, listing_id):
    listing = get_object_or_404(Listing, id=listing_id)
    
    # Check if the user is the owner
    if request.user != listing.user:
        return HttpResponseForbidden("You don't have permission to edit this listing.")
    
    if request.method == 'POST':
        # Handle form submission
        listing.title = request.POST.get('title')
        listing.listing_type = request.POST.get('listing_type')
        listing.category_id = request.POST.get('category')
        listing.region_id = request.POST.get('region')
        listing.price = request.POST.get('price') or None
        listing.quantity = request.POST.get('quantity') or None
        listing.unit_id = request.POST.get('unit') or None
        listing.description = request.POST.get('description')
        listing.additional_details = request.POST.get('additional_details')
        listing.contact_phone = request.POST.get('contact_phone')
        listing.contact_whatsapp = request.POST.get('contact_whatsapp')
        listing.contact_email = request.POST.get('contact_email')
        
        # Validate required fields
        if not all([listing.title, listing.listing_type, listing.category_id, 
                    listing.region_id, listing.description, listing.contact_phone]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'tradepoint/update_listing.html', {
                'form': request.POST,
                'categories': ProductCategory.objects.all(),
                'regions': Region.objects.all(),
                'units': Unit.objects.all(),
                'listing': listing,
                'current_images': ListingImage.objects.filter(listing=listing),
            })
        
        listing.save()
        
        # Handle image replacements
        for key, value in request.FILES.items():
            if key.startswith('replace_image_'):
                try:
                    image_id = key.split('_')[-1]
                    image = ListingImage.objects.get(id=image_id, listing=listing)
                    image.image = value
                    image.save()
                except (ListingImage.DoesNotExist, IndexError):
                    pass
        
        # Handle new images
        new_images = request.FILES.getlist('new_images')
        for image in new_images:
            ListingImage.objects.create(
                listing=listing,
                image=image
            )
        
        messages.success(request, 'Your listing has been updated successfully!')
        return redirect('tradepoint:listing_detail', listing_id=listing.id)
    
    # Display the form with current values
    context = {
        'form': listing,
        'categories': ProductCategory.objects.all(),
        'regions': Region.objects.all(),
        'units': Unit.objects.all(),
        'listing': listing,
        'current_images': ListingImage.objects.filter(listing=listing),
    }
    
    return render(request, 'tradepoint/update_listing.html', context)

# Confirm and delete a listing
@login_required
def delete_listing(request, listing_id):
    listing = get_object_or_404(Listing, id=listing_id)
    
    # Check if the user is the owner
    if request.user != listing.user:
        return HttpResponseForbidden("You don't have permission to delete this listing.")
    
    if request.method == 'POST':
        # Delete all associated images
        ListingImage.objects.filter(listing=listing).delete()
        
        # Delete all associated interests
        ListingInterest.objects.filter(listing=listing).delete()
        
        # Delete the listing
        listing.delete()
        
        messages.success(request, 'Your listing has been deleted successfully!')
        return redirect('tradepoint:dashboard')
    
    return render(request, 'tradepoint/delete_listing.html', {'listing': listing})

# Delete a listing image
@login_required
def delete_image(request, image_id):
    image = get_object_or_404(ListingImage, id=image_id)
    
    # Check if the user is the owner
    if request.user != image.listing.user:
        return HttpResponseForbidden("You don't have permission to delete this image.")
    
    listing_id = image.listing.id
    image.delete()
    
    next_url = request.GET.get('next', reverse('tradepoint:update_listing', args=[listing_id]))
    return redirect(next_url)

# Show interest in a listing
@login_required
def show_interest(request, listing_id):
    listing = get_object_or_404(Listing, id=listing_id)
    
    # Check if the user is not the owner and hasn't already shown interest
    if request.user == listing.user:
        messages.error(request, 'You cannot show interest in your own listing.')
        return redirect('tradepoint:listing_detail', listing_id=listing_id)
    
    # Check if already shown interest
    existing_interest = ListingInterest.objects.filter(listing=listing, user=request.user).first()
    if existing_interest:
        messages.info(request, 'You have already shown interest in this listing.')
        return redirect('tradepoint:listing_detail', listing_id=listing_id)
    
    # Create the interest
    message = request.POST.get('message', '')
    ListingInterest.objects.create(
        listing=listing,
        user=request.user,
        message=message,
        status='pending'
    )
    
    messages.success(request, 'Your interest has been sent to the listing owner.')
    return redirect('tradepoint:listing_detail', listing_id=listing_id)

# Mark an interest as contacted
@login_required
def mark_as_contacted(request, interest_id):
    interest = get_object_or_404(ListingInterest, id=interest_id)
    
    # Check if the user is the listing owner
    if request.user != interest.listing.user:
        return HttpResponseForbidden("You don't have permission to update this interest.")
    
    interest.status = 'contacted'
    interest.save()
    
    messages.success(request, 'Interest marked as contacted.')
    return redirect('tradepoint:dashboard')

# Report a listing
@login_required
def report_listing(request, listing_id):
    if request.method == 'POST':
        listing = get_object_or_404(Listing, id=listing_id)
        reason = request.POST.get('reason')
        details = request.POST.get('details', '')
        
        # In a real application, you'd save this report to a model
        # For now, we'll just show a success message
        messages.success(request, 'Thank you for your report. Our team will review it.')
        
        # Could also send an email to admins here
        
    return redirect('tradepoint:listing_detail', listing_id=listing_id)
