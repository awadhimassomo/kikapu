"""
Utility functions for handling group delivery operations.
"""
import string
import random
import urllib.parse
from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone
from django.db import transaction
from django.urls import reverse
from django.conf import settings

from .models import DeliveryGroup, GroupOrder


def generate_group_code():
    """Generate a random 6-character alphanumeric code for groups."""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(6))


def create_delivery_group(leader, delivery_date, time_slot):
    """
    Creates a new delivery group with the given parameters.
    
    Args:
        leader: CustomerProfile object of the group leader
        delivery_date: Date of delivery
        time_slot: Time slot string from DeliveryGroup.TIME_SLOT_CHOICES
        
    Returns:
        The newly created DeliveryGroup object
    """
    with transaction.atomic():
        # Generate a unique code
        while True:
            code = generate_group_code()
            if not DeliveryGroup.objects.filter(code=code).exists():
                break
        
        # Set expiration time (24 hours from now)
        expires_at = timezone.now() + timedelta(hours=24)
        
        # Create the group
        group = DeliveryGroup.objects.create(
            leader=leader,
            code=code,
            delivery_date=delivery_date,
            time_slot=time_slot,
            expires_at=expires_at,
            is_active=True
        )
        
        return group


def add_order_to_group(order, delivery_group, added_by_leader=False, name=None, phone=None):
    """
    Adds an order to a delivery group.
    
    Args:
        order: Order object to add to the group
        delivery_group: DeliveryGroup object
        added_by_leader: Boolean indicating if this order was added by the group leader
        name: Name of the person (used when added by leader)
        phone: Phone number (used when added by leader)
        
    Returns:
        The newly created GroupOrder object
    """
    with transaction.atomic():
        # Create the group order
        group_order = GroupOrder.objects.create(
            group=delivery_group,
            order=order,
            member=order.customer,
            added_by_leader=added_by_leader,
            name=name if added_by_leader else order.customer.user.get_full_name(),
            phone=phone if added_by_leader else order.customer.user.phone
        )
        
        # Link the order to this delivery group
        order.delivery_group = delivery_group
        order.save(update_fields=['delivery_group'])
        
        # Recalculate delivery fees for all orders in the group
        recalculate_group_delivery_fees(delivery_group)
        
        return group_order


def remove_order_from_group(group_order):
    """
    Removes an order from a delivery group.
    
    Args:
        group_order: GroupOrder object to remove
        
    Returns:
        The updated DeliveryGroup object
    """
    with transaction.atomic():
        # Get the group and order
        group = group_order.group
        order = group_order.order
        
        # Remove the link from order to group
        order.delivery_group = None
        
        # Reset the delivery fee to standard
        order.delivery_fee = Decimal('5000')
        order.total_amount = order.subtotal + order.delivery_fee
        order.save(update_fields=['delivery_group', 'delivery_fee', 'total_amount'])
        
        # Delete the group order
        group_order.delete()
        
        # Recalculate delivery fees for remaining orders
        if GroupOrder.objects.filter(group=group).exists():
            recalculate_group_delivery_fees(group)
        
        return group


def recalculate_group_delivery_fees(group):
    """
    Recalculates delivery fees for all orders in a group.
    
    Args:
        group: DeliveryGroup object
        
    Returns:
        The number of orders updated
    """
    with transaction.atomic():
        group_orders = GroupOrder.objects.filter(group=group).select_related('order')
        
        # If no orders, nothing to do
        if not group_orders:
            return 0
        
        # Count how many members in the group
        member_count = group_orders.count()
        
        # Base delivery fee is 5000 TSh
        base_fee = Decimal('5000')
        
        # Calculate fee per member (rounded to the nearest 100)
        fee_per_member = (base_fee / member_count).quantize(Decimal('100'))
        
        # For each order, update delivery fee and total
        orders_updated = 0
        for group_order in group_orders:
            order = group_order.order
            
            # Calculate the order total with updated delivery fee
            order.delivery_fee = fee_per_member
            
            # If this is the leader's order, apply 10% discount to subtotal
            if group.leader == group_order.member and not group_order.added_by_leader:
                leader_discount = (order.subtotal * Decimal('0.10')).quantize(Decimal('1'))
                order.total_amount = order.subtotal + order.delivery_fee - leader_discount
                
                # Store the discount amount for reporting
                order.discount_amount = leader_discount
            else:
                order.total_amount = order.subtotal + order.delivery_fee
            
            order.save(update_fields=['delivery_fee', 'total_amount', 'discount_amount'])
            orders_updated += 1
        
        return orders_updated


def get_group_summary(group):
    """
    Gets a summary of a delivery group including all members and fee calculations.
    
    Args:
        group: DeliveryGroup object
        
    Returns:
        Dictionary with group summary information
    """
    group_orders = GroupOrder.objects.filter(group=group).select_related('order', 'member')
    
    # Base delivery fee
    base_fee = Decimal('5000')
    
    # Calculate fee per member
    member_count = group_orders.count()
    fee_per_member = Decimal('0')
    if member_count > 0:
        fee_per_member = (base_fee / member_count).quantize(Decimal('100'))
    
    # Build member list
    members = []
    total_subtotal = Decimal('0')
    
    for group_order in group_orders:
        order = group_order.order
        is_leader = (group.leader == group_order.member) and not group_order.added_by_leader
        
        # Calculate leader discount if applicable
        discount = Decimal('0')
        if is_leader:
            discount = (order.subtotal * Decimal('0.10')).quantize(Decimal('1'))
        
        member_info = {
            'order_id': order.id,
            'order_number': order.order_number,
            'name': group_order.name,
            'is_leader': is_leader,
            'added_by_leader': group_order.added_by_leader,
            'subtotal': order.subtotal,
            'delivery_fee': fee_per_member,
            'discount': discount,
            'total': order.subtotal + fee_per_member - discount
        }
        
        members.append(member_info)
        total_subtotal += order.subtotal
    
    return {
        'total_members': member_count,
        'delivery_fee': base_fee,
        'delivery_fee_per_member': fee_per_member,
        'members': members,
        'total_subtotal': total_subtotal,
        'total_discount': sum(m['discount'] for m in members),
        'total_with_fees': total_subtotal + base_fee - sum(m['discount'] for m in members)
    }