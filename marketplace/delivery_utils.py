"""
Delivery fee calculation utilities for Kikapu marketplace
"""
from decimal import Decimal
from typing import Dict, Optional, Tuple
import math

# Base delivery fees for different options
DELIVERY_BASE_FEES = {
    'STANDARD': Decimal('5.00'),
    'EXPRESS': Decimal('10.00'),
    'SCHEDULED': Decimal('7.50'),
}

# Additional fee per kilometer
DISTANCE_FEE_PER_KM = Decimal('0.50')

# Fee multipliers for order weight (in kg)
WEIGHT_FEE_MULTIPLIERS = [
    (5, Decimal('1.0')),   # 0-5 kg: no additional fee
    (10, Decimal('1.2')),  # 5-10 kg: 20% extra
    (20, Decimal('1.5')),  # 10-20 kg: 50% extra
    (float('inf'), Decimal('2.0')),  # Over 20 kg: double fee
]

# Minimum fee regardless of other factors
MINIMUM_DELIVERY_FEE = Decimal('3.00')

def calculate_distance(origin: Tuple[float, float], destination: Tuple[float, float]) -> float:
    """
    Calculate the distance between two points using the Haversine formula.
    
    Args:
        origin: Tuple of (latitude, longitude) for the starting point
        destination: Tuple of (latitude, longitude) for the ending point
        
    Returns:
        Distance in kilometers
    """
    if not all(origin) or not all(destination):
        return 5.0  # Default to 5 km if coordinates are missing
        
    # Earth radius in kilometers
    R = 6371.0
    
    lat1, lon1 = math.radians(origin[0]), math.radians(origin[1])
    lat2, lon2 = math.radians(destination[0]), math.radians(destination[1])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    return distance

def get_weight_multiplier(weight_kg: float) -> Decimal:
    """
    Determine the weight multiplier based on the order's weight
    
    Args:
        weight_kg: Total weight of the order in kilograms
        
    Returns:
        Price multiplier for the given weight
    """
    for weight_limit, multiplier in WEIGHT_FEE_MULTIPLIERS:
        if weight_kg <= weight_limit:
            return multiplier
    
    # Should never reach here due to float('inf') in the last entry
    return WEIGHT_FEE_MULTIPLIERS[-1][1]

def calculate_delivery_fee(
    delivery_option: str,
    distance_km: Optional[float] = None,
    weight_kg: Optional[float] = None,
    origin_coords: Optional[Tuple[float, float]] = None,
    destination_coords: Optional[Tuple[float, float]] = None,
    special_handling: bool = False,
) -> Decimal:
    """
    Calculate delivery fee based on delivery option, distance, weight, and special handling.
    
    Args:
        delivery_option: One of 'STANDARD', 'EXPRESS', or 'SCHEDULED'
        distance_km: Distance in kilometers (if already known)
        weight_kg: Total weight of the order in kilograms
        origin_coords: Tuple of (latitude, longitude) for the business/vendor location
        destination_coords: Tuple of (latitude, longitude) for the delivery location
        special_handling: Whether special handling is required
        
    Returns:
        Calculated delivery fee as Decimal
    """
    # Get base fee for delivery option
    base_fee = DELIVERY_BASE_FEES.get(delivery_option, DELIVERY_BASE_FEES['STANDARD'])
    
    # Calculate or use provided distance
    if distance_km is None and origin_coords and destination_coords:
        distance_km = calculate_distance(origin_coords, destination_coords)
    elif distance_km is None:
        distance_km = 5.0  # Default to 5 km if no distance info provided
    
    # Calculate distance fee
    distance_fee = Decimal(str(distance_km)) * DISTANCE_FEE_PER_KM
    
    # Apply weight multiplier if weight is provided
    if weight_kg is not None:
        weight_multiplier = get_weight_multiplier(weight_kg)
    else:
        weight_multiplier = Decimal('1.0')
    
    # Add special handling fee if required
    special_handling_fee = Decimal('5.00') if special_handling else Decimal('0.00')
    
    # Calculate total fee
    total_fee = (base_fee + distance_fee) * weight_multiplier + special_handling_fee
    
    # Ensure fee is not below minimum
    total_fee = max(total_fee, MINIMUM_DELIVERY_FEE)
    
    # Round to 2 decimal places
    return total_fee.quantize(Decimal('0.01'))

def estimate_order_weight(order) -> float:
    """
    Estimate the total weight of an order based on products and quantities.
    
    Args:
        order: Order object with related items
        
    Returns:
        Estimated weight in kilograms
    """
    # Default weight per item if not specified (in kg)
    DEFAULT_ITEM_WEIGHT = 0.5
    
    total_weight = 0.0
    
    for item in order.items.all():
        # For now we use a simple approach - assuming each product is 0.5kg
        # In a real application, you would add a weight field to the Product model
        item_weight = DEFAULT_ITEM_WEIGHT
        total_weight += item_weight * item.quantity
    
    return total_weight

def calculate_order_delivery_fee(order) -> Decimal:
    """
    Calculate delivery fee for a given order.
    
    Args:
        order: Order object with delivery details
        
    Returns:
        Calculated delivery fee
    """
    # Get business coordinates (in a real app, you'd get this from the business profile)
    # For now we use dummy coordinates
    business_coords = (None, None)
    
    # Get delivery coordinates from order
    delivery_coords = (order.latitude, order.longitude) if order.latitude and order.longitude else (None, None)
    
    # Estimate order weight
    weight_kg = estimate_order_weight(order)
    
    # Calculate delivery fee
    delivery_fee = calculate_delivery_fee(
        delivery_option=order.delivery_option,
        origin_coords=business_coords,
        destination_coords=delivery_coords,
        weight_kg=weight_kg
    )
    
    return delivery_fee

def get_delivery_eta(delivery_option: str) -> Dict:
    """
    Get estimated delivery time information based on delivery option.
    
    Args:
        delivery_option: One of 'STANDARD', 'EXPRESS', or 'SCHEDULED'
        
    Returns:
        Dictionary with min_hours, max_hours and formatted ETA string
    """
    if delivery_option == 'EXPRESS':
        return {
            'min_hours': 2,
            'max_hours': 4,
            'formatted': '2-4 hours'
        }
    elif delivery_option == 'STANDARD':
        return {
            'min_hours': 6,
            'max_hours': 8,
            'formatted': '6-8 hours'
        }
    elif delivery_option == 'SCHEDULED':
        return {
            'min_hours': None,
            'max_hours': None,
            'formatted': 'At scheduled time'
        }
    else:
        return {
            'min_hours': 6,
            'max_hours': 8,
            'formatted': '6-8 hours'  # Default to standard delivery times
        }