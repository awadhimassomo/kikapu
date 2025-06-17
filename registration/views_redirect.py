from django.http import JsonResponse
import json
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

# Setup logger
logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([AllowAny])
def redirect_agent_register(request):
    """
    Redirects agent registration requests to the DeliveryAgentViewSet.create method
    """
    # Import the viewset within the function to avoid circular imports
    try:
        # Make sure we get a fresh import of DeliveryAgentViewSet
        import importlib
        from . import views
        importlib.reload(views)
        DeliveryAgentViewSet = views.DeliveryAgentViewSet
    except ImportError as e:
        logger.error(f"ImportError: {str(e)}")
        return Response({
            'success': False,
            'message': 'Could not import DeliveryAgentViewSet',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    logger.info(f"Received agent registration request at {request.path}")
    logger.info(f"HTTP Method: {request.method}")
    logger.info(f"Content Type: {request.content_type}")

    # Check if request has a body
    if not request.body:
        logger.error("Request body is empty")
        return Response({
            'success': False,
            'message': 'Request body is required'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Parse request body if content type is JSON
    if request.content_type == 'application/json':
        try:
            if not hasattr(request, 'data'):
                request.data = json.loads(request.body)
                logger.info("Manually parsed JSON body")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in request body: {str(e)}")
            return Response({
                'success': False,
                'message': 'Invalid JSON in request body',
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    # Safely log request data (hide sensitive information like passwords)
    try:
        if hasattr(request, 'data'):
            safe_data = {key: ('******' if key == 'password' else value) for key, value in request.data.items()}
            logger.info(f"Request data: {safe_data}")
        else:
            logger.warning("Request has no 'data' attribute")
    except Exception as e:
        logger.error(f"Error logging request data: {str(e)}")

    # Forward to DeliveryAgentViewSet
    try:
        # Create a viewset instance
        viewset = DeliveryAgentViewSet()

        # Set up the viewset to handle this request
        viewset.request = request
        viewset.format_kwarg = None
        viewset.action = 'create'

        logger.info("Forwarding to DeliveryAgentViewSet.create")

        # Call the create method directly
        return viewset.create(request)

    except Exception as e:
        logger.error(f"Error in redirect_agent_register: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return Response({
            'success': False,
            'message': 'An error occurred during agent registration',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
