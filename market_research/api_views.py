from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Commodity
from .serializers import CommoditySerializer

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_commodity_api(request):
    """API endpoint for adding commodities via AJAX"""
    try:
        data = request.data
        
        # Validate required fields
        required_fields = ['name', 'category', 'default_unit']
        for field in required_fields:
            if not data.get(field):
                return Response({
                    'success': False,
                    'message': f'Field {field} is required',
                    'field_errors': {field: ['This field is required']}
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if a commodity with this name already exists
        if Commodity.objects.filter(name__iexact=data['name']).exists():
            return Response({
                'success': False,
                'message': f"A commodity with the name '{data['name']}' already exists.",
                'field_errors': {'name': ['This commodity name already exists. Please use a different name.']}
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create new commodity
        try:
            commodity = Commodity(
                name=data['name'],
                category=data['category'],
                default_unit=data['default_unit'],
                description=data.get('description', '')
            )
            commodity.save()
        except Exception as e:
            # Handle potential database uniqueness errors
            if 'unique constraint' in str(e).lower() or 'duplicate key' in str(e).lower():
                return Response({
                    'success': False,
                    'message': f"A commodity with the name '{data['name']}' already exists.",
                    'field_errors': {'name': ['This commodity name already exists. Please use a different name.']}
                }, status=status.HTTP_400_BAD_REQUEST)
            raise
        
        # Return success response
        return Response({
            'success': True,
            'message': f"Commodity '{commodity.name}' has been added successfully.",
            'commodity': {
                'id': commodity.id,
                'name': commodity.name,
                'category': commodity.category,
                'default_unit': commodity.default_unit
            }
        }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Error adding commodity: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_commodity_api(request, commodity_id):
    """API endpoint for deleting commodities via AJAX"""
    try:
        # Find and delete the commodity
        commodity = get_object_or_404(Commodity, id=commodity_id)
        commodity_name = commodity.name
        commodity.delete()
        
        # Return success response
        return Response({
            'success': True,
            'message': f"Commodity '{commodity_name}' has been deleted successfully."
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response({
            'success': False,
            'message': f'Error deleting commodity: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
