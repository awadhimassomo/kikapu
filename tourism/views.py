from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import datetime
from decimal import Decimal
from .models import FarmExperience, Booking

def farm_experiences(request):
    experiences = FarmExperience.objects.filter(available=True)
    return render(request, 'tourism/experiences.html', {'experiences': experiences})

def experience_detail(request, pk):
    experience = get_object_or_404(FarmExperience, pk=pk)
    return render(request, 'tourism/detail.html', {'experience': experience})

@login_required
def book_experience(request, pk):
    """
    Unified booking view for any type of farm experience
    """
    experience = get_object_or_404(FarmExperience, pk=pk)
    
    if request.method == 'POST':
        # Extract booking details from form
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date') if experience.experience_type == 'FARMHOUSE' else None
        party_size = int(request.POST.get('party_size', 1))
        special_requests = request.POST.get('special_requests', '')
        contact_phone = request.POST.get('contact_phone')
        payment_method = request.POST.get('payment_method', 'MOBILE_MONEY')
        
        # Validate form data
        if not all([start_date_str, contact_phone]):
            messages.error(request, "Please fill in all required fields.")
            return render(request, 'tourism/booking.html', {
                'experience': experience,
                'error': "Please fill in all required fields."
            })
        
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
            
            # Create booking
            booking = Booking(
                user=request.user,
                experience=experience,
                start_date=start_date,
                end_date=end_date,
                party_size=party_size,
                special_requests=special_requests,
                contact_phone=contact_phone,
                total_price=total_price,
                payment_method=payment_method
            )
            
            # Generate booking number and save
            booking.save()
            
            messages.success(request, f"Your booking has been confirmed! Booking number: {booking.booking_number}")
            return redirect('tourism:booking_confirmation', booking_id=booking.id)
        except Exception as e:
            messages.error(request, f"Error processing booking: {str(e)}")
            return render(request, 'tourism/booking.html', {
                'experience': experience,
                'error': str(e)
            })
    
    return render(request, 'tourism/booking.html', {
        'experience': experience,
        'today': timezone.now().date().isoformat(),
    })

@login_required
def booking_confirmation(request, booking_id):
    """Show booking confirmation details"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    return render(request, 'tourism/booking_confirmation.html', {'booking': booking})

@login_required
def my_bookings(request):
    """Show all bookings for the current user"""
    bookings = Booking.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'tourism/my_bookings.html', {'bookings': bookings})

# Legacy functions for compatibility, redirecting to the unified booking view
@login_required
def book_farmhouse(request, pk=None):
    if pk:
        return redirect('tourism:book_experience', pk=pk)
    
    # For backward compatibility, show available farmhouse experiences
    experiences = FarmExperience.objects.filter(available=True, experience_type='FARMHOUSE')
    return render(request, 'tourism/book_farmhouse.html', {
        'title': 'Book a Farmhouse Retreat',
        'description': 'Escape to nature with our farmhouse retreats.',
        'experiences': experiences
    })
    
@login_required
def book_restaurant(request, pk=None):
    if pk:
        return redirect('tourism:book_experience', pk=pk)
    
    # For backward compatibility, show available restaurant experiences
    experiences = FarmExperience.objects.filter(available=True, experience_type='RESTAURANT')
    return render(request, 'tourism/book_restaurant.html', {
        'title': 'Reserve a Table',
        'description': 'Enjoy farm-to-table dining experiences.',
        'experiences': experiences
    })
