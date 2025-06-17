"""
Debug views for testing agent permissions

These endpoints help diagnose authentication and permission issues.
"""

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Set up logging
logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_agent_permissions(request):
    """
    Debug endpoint to check the current user's agent permissions.
    This helps diagnose 403 Forbidden errors.
    """
    user = request.user
    
    # Log detailed permission information
    logger.info(f"Permission check for user: {user.phoneNumber}")
    logger.info(f"User type: {user.user_type}")
    logger.info(f"Has is_agent attribute: {hasattr(user, 'is_agent')}")
    
    if hasattr(user, 'is_agent'):
        logger.info(f"is_agent value: {user.is_agent}")
    
    logger.info(f"Has delivery_agent relation: {hasattr(user, 'delivery_agent')}")
    
    # Collect debug information
    debug_info = {
        'user_id': user.id,
        'username': user.username,
        'phoneNumber': user.phoneNumber,
        'user_type': user.user_type,
        'has_is_agent_attribute': hasattr(user, 'is_agent'),
        'is_agent_value': getattr(user, 'is_agent', None),
        'has_delivery_agent': hasattr(user, 'delivery_agent'),
        'timestamp': timezone.now().isoformat(),
    }
    
    # Add delivery agent details if available
    if hasattr(user, 'delivery_agent'):
        agent = user.delivery_agent
        debug_info.update({
            'agent_id': agent.agent_id,
            'agent_is_active': agent.is_active,
            'agent_is_verified': agent.is_verified,
            'agent_assigned_area': agent.assigned_area,
        })
    
    # Return user details and permission status
    return Response({
        'can_submit_market_price': hasattr(user, 'is_agent') and user.is_agent,
        'debug_info': debug_info,
        'next_steps': get_next_steps(user)
    })

def get_next_steps(user):
    """Return guidance for fixing permission issues"""
    if not hasattr(user, 'is_agent'):
        return [
            "The User model is missing the 'is_agent' property. Contact a developer to fix this."
        ]
    
    if not user.is_agent:
        steps = ["Your user account doesn't have proper agent permissions."]
        
        if user.user_type != 'AGENT':
            steps.append(f"Your user_type is '{user.user_type}' instead of 'AGENT'.")
        
        if not hasattr(user, 'delivery_agent'):
            steps.append("You don't have an associated delivery_agent record.")
        elif not user.delivery_agent.is_active:
            steps.append("Your agent account is not active.")
        
        steps.append("Contact your administrator to update your account permissions.")
        return steps
    
    return ["You have the correct agent permissions to submit market prices."]

@login_required
def permission_debug_view(request):
    """
    Web view for debugging permissions - shows detailed permission information
    for the currently logged-in user.
    """
    user = request.user
    
    # Collect permission data
    permission_data = {
        'user_info': {
            'id': user.id,
            'username': user.username,
            'phoneNumber': getattr(user, 'phoneNumber', 'N/A'),
            'email': user.email,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'user_type': getattr(user, 'user_type', 'N/A'),
            'has_is_agent_attribute': hasattr(user, 'is_agent'),
            'is_agent': getattr(user, 'is_agent', False) if hasattr(user, 'is_agent') else False,
            'date_joined': user.date_joined,
            'last_login': user.last_login,
        },
        'agent_info': None,
        'permission_status': {
            'can_submit_market_price': hasattr(user, 'is_agent') and getattr(user, 'is_agent', False)
        }
    }
    
    # Add agent info if available
    if hasattr(user, 'delivery_agent'):
        agent = user.delivery_agent
        permission_data['agent_info'] = {
            'agent_id': agent.agent_id,
            'is_active': agent.is_active,
            'is_verified': agent.is_verified,
            'assigned_area': agent.assigned_area,
            'join_date': agent.join_date,
            'last_active': agent.last_active,
        }
    
    # Add troubleshooting guidance
    permission_data['next_steps'] = get_next_steps(user)
    
    logger.info(f"Permission debug view accessed by user: {user.username}")
    
    return render(request, 'market_research/permission_debug.html', {
        'title': 'Permission Debug View',
        'permission_data': permission_data,
    })