from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime
from decimal import Decimal
from tourism.models import FarmExperience, Booking
from .cart_utils import get_or_create_cart

def marketplace_tourism_experiences(request):
    """
    Display tourism experiences in the marketplace interface
    """
    experiences = FarmExperience.objects.filter(available=True)
    return render(request, 'marketplace/tourism/experiences.html', {
        'title': 'Farm & Tourism Experiences',
        'experiences': experiences,
        'today': timezone.now().date().isoformat()
    })

def marketplace_experience_detail(request, pk):
    """
    Show details of a tourism experience in the marketplace interface
    """
    experience = get_object_or_404(FarmExperience, pk=pk)
    return render(request, 'marketplace/tourism/experience_detail.html', {
        'title': experience.title,
        'experience': experience,
        'today': timezone.now().date().isoformat()
    })

@login_required
def add_experience_to_cart(request, pk):
    """
    Add a tourism experience to the cart
    """
    experience = get_object_or_404(FarmExperience, pk=pk)
    
    if request.method == 'POST':
        # Extract booking details from form
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date') if experience.experience_type == 'FARMHOUSE' else None
        party_size = int(request.POST.get('party_size', 1))
        
        # Validate form data
        if not start_date_str:
            messages.error(request, "Please select a date.")
            return redirect('marketplace:tourism_experience_detail', pk=pk)
        
        try:
            # Parse dates
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
            
            # Calculate total price
            if experience.experience_type == 'FARMHOUSE' and end_date:
                # Calculate number of days
                days = (end_date - start_date).days + 1  # Include end day
                total_price = experience.price_per_day * Decimal(days) * Decimal(party_size)
            else:
                # For restaurant or single-day experiences
                total_price = experience.price_per_day * Decimal(party_size)
              # Get or create the cart if user is authenticated
            if request.user.is_authenticated:
                cart = get_or_create_cart(request.user)
            
            # Store tourism booking in the session as a special cart item
            if not hasattr(request.session, 'tourism_bookings'):
                request.session['tourism_bookings'] = []
            
            # Create a booking dict to store in session
            booking_data = {
                'id': f'tourism_{experience.id}_{start_date_str}',
                'experience_id': experience.id,
                'experience_title': experience.title,
                'start_date': start_date_str,
                'end_date': end_date_str,
                'party_size': party_size,
                'price_per_day': float(experience.price_per_day),
                'total_price': float(total_price),
                'experience_type': experience.experience_type,
            }
            
            # Add to session
            tourism_bookings = request.session['tourism_bookings']
            tourism_bookings.append(booking_data)
            request.session['tourism_bookings'] = tourism_bookings
            request.session.modified = True
            
            messages.success(request, f"Added {experience.title} to your cart.")
            return redirect('marketplace:view_cart')
            
        except Exception as e:
            messages.error(request, f"Error adding to cart: {str(e)}")
            return redirect('marketplace:tourism_experience_detail', pk=pk)
    
    return redirect('marketplace:tourism_experience_detail', pk=pk)

@login_required
def remove_experience_from_cart(request, booking_id):
    """
    Remove a tourism experience from the cart
    """
    if hasattr(request.session, 'tourism_bookings'):
        tourism_bookings = request.session['tourism_bookings']
        # Find and remove the booking with the matching ID
        for i, booking in enumerate(tourism_bookings):
            if booking['id'] == booking_id:
                experience_title = booking['experience_title']
                del tourism_bookings[i]
                request.session['tourism_bookings'] = tourism_bookings
                request.session.modified = True
                messages.success(request, f"Removed {experience_title} from your cart.")
                break
    
    return redirect('marketplace:view_cart')

@login_required
def process_tourism_bookings(request, order):
    """
    Process tourism bookings from the cart and create actual booking records
    This function should be called during checkout
    
    Returns: List of created bookings
    """
    created_bookings = []
    
    if not hasattr(request.session, 'tourism_bookings'):
        return created_bookings
    
    tourism_bookings = request.session['tourism_bookings']
    if not tourism_bookings:
        return created_bookings
    
    for booking_data in tourism_bookings:
        try:
            experience = FarmExperience.objects.get(id=booking_data['experience_id'])
            
            # Parse dates
            start_date = datetime.strptime(booking_data['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(booking_data['end_date'], '%Y-%m-%d').date() if booking_data['end_date'] else None
            
            # Create a real booking
            booking = Booking(
                user=request.user,
                experience=experience,
                start_date=start_date,
                end_date=end_date,
                party_size=booking_data['party_size'],
                special_requests=request.POST.get('special_requests', ''),
                contact_phone=request.user.phoneNumber,  # Use the user's phone number
                total_price=Decimal(str(booking_data['total_price'])),
                payment_method='MARKETPLACE_ORDER',
                status='CONFIRMED',  # Auto-confirm since it's paid through marketplace order
            )
            
            # Generate booking number and save
            booking.save()
            created_bookings.append(booking)
            
        except Exception as e:
            messages.error(request, f"Error processing booking for {booking_data['experience_title']}: {str(e)}")
    
    # Clear tourism bookings from session
    request.session['tourism_bookings'] = []
    request.session.modified = True
    
    return created_bookings