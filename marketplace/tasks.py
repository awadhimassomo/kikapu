from celery import shared_task
from django.utils import timezone
from django.db.models import Q

from .models import DeliverySchedule, Order, OrderItem


@shared_task
def generate_orders_from_schedules():
    """
    Daily task to check for scheduled deliveries and create orders accordingly
    """
    today = timezone.now().date()
    
    # Get all active schedules for today (one-time or recurring)
    schedules = DeliverySchedule.objects.filter(
        is_active=True
    ).filter(
        Q(delivery_date=today) |  # One-time schedules for today
        # Weekly schedules that match today's weekday
        Q(is_recurring=True, recurrence_type='weekly', 
          created_at__week_day=today.isoweekday()) |
        # Monthly schedules that match today's day of month
        Q(is_recurring=True, recurrence_type='monthly', 
          created_at__day=today.day)
    )
    
    created_orders = []
    
    for schedule in schedules:
        try:
            order = create_order_from_schedule(schedule)
            created_orders.append(order.id)
            
            # Update the tracking metrics
            schedule.times_fulfilled += 1
            schedule.save()
            
            # Deactivate one-time schedules after fulfillment
            if not schedule.is_recurring:
                schedule.is_active = False
                schedule.save()
                
        except Exception as e:
            # Log error but continue processing other schedules
            print(f"Error creating order from schedule {schedule.id}: {str(e)}")
    
    return created_orders


def create_order_from_schedule(schedule):
    """
    Create an order based on a delivery schedule
    """
    subtotal = 0
    items = []

    # Calculate subtotal and collect items
    for item in schedule.scheduleditems.all():
        # Check if product is available
        if not item.product.is_available:
            # Handle unavailable products
            # For now we'll just skip them, but you could implement notifications
            continue
            
        subtotal += item.product.price * item.quantity
        items.append(item)

    # Make sure we have items to order
    if not items:
        raise ValueError("No available items in schedule")

    # Create the order
    order = Order.objects.create(
        customer=schedule.customer,
        subtotal=subtotal,
        delivery_option='scheduled',
        shipping_address=schedule.delivery_address,
        delivery_time_slot=schedule.time_slot,
        notes=f"Auto-generated from scheduled delivery {schedule.id}. {schedule.notes}",
        source="scheduled"
    )
    
    # Add delivery fee and calculate total
    from .delivery_utils import calculate_order_delivery_fee
    delivery_fee = calculate_order_delivery_fee(order)
    order.delivery_fee = delivery_fee
    order.total_amount = subtotal + delivery_fee
    order.save()

    # Create order items
    for item in items:
        OrderItem.objects.create(
            order=order,
            product=item.product,
            quantity=item.quantity,
            price=item.product.price,
            processing_method=item.processing_method
        )

    return order