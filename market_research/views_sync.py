from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import UnsyncedData, SyncLog, MarketPriceResearch
from .serializers import (
    SyncRequestSerializer, 
    SyncResponseSerializer, 
    ConflictResolutionSerializer,
    MarketPriceResearchSerializer,
    UnsyncedDataSerializer
)

MAX_RETRIES = 3  # Maximum number of retry attempts for failed syncs

@swagger_auto_schema(
    method='post',
    operation_description="Endpoint for mobile app to sync offline collected data with the server",
    request_body=SyncRequestSerializer,
    responses={
        200: openapi.Response('Data synced successfully', SyncResponseSerializer),
        400: 'Invalid data',
        401: 'Not authorized'
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_data(request):
    """
    Process data sent from mobile app for synchronization
    
    The mobile device sends a batch of data collected offline,
    and we process each item and respond with status results.
    """
    serializer = SyncRequestSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'status': 'error',
            'message': 'Invalid data format',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    validated_data = serializer.validated_data
    device_id = validated_data['device_id']
    data_items = validated_data['data']
    
    # For tracking failed syncs
    failed_syncs = []
    
    # Process each item in the batch
    for item in data_items:
        sync_id = item['sync_id']
        data_type = item['data_type']
        payload = item['payload']
        
        try:
            # Check if this sync_id is already processed
            if UnsyncedData.objects.filter(id=sync_id).exists():
                # Item already processed, skip
                continue
            
            # Create a record of the unsynced data
            unsynced_data = UnsyncedData.objects.create(
                id=sync_id,
                device_id=device_id,
                data_type=data_type,
                payload=payload,
                agent=request.user,
                sync_status='PENDING'
            )
            
            # Process the data based on type
            with transaction.atomic():
                unsynced_data.mark_as_syncing()
                
                if data_type == 'price':
                    # Process market price research data
                    success, error_message = process_price_data(payload, request.user)
                    
                    if not success:
                        unsynced_data.mark_as_failed(error_message)
                        failed_syncs.append({
                            'sync_id': str(sync_id),
                            'error': error_message
                        })
                        # Create a log entry for the failed sync
                        SyncLog.objects.create(
                            data=unsynced_data,
                            status='FAILED',
                            response={'error': error_message}
                        )
                        continue
                
                elif data_type == 'sale':
                    # Process sales data
                    success, error_message = process_sale_data(payload, request.user)
                    
                    if not success:
                        unsynced_data.mark_as_failed(error_message)
                        failed_syncs.append({
                            'sync_id': str(sync_id),
                            'error': error_message
                        })
                        # Create a log entry for the failed sync
                        SyncLog.objects.create(
                            data=unsynced_data,
                            status='FAILED',
                            response={'error': error_message}
                        )
                        continue
                
                elif data_type == 'stock_update':
                    # Process stock update data
                    success, error_message = process_stock_update(payload, request.user)
                    
                    if not success:
                        unsynced_data.mark_as_failed(error_message)
                        failed_syncs.append({
                            'sync_id': str(sync_id),
                            'error': error_message
                        })
                        # Create a log entry for the failed sync
                        SyncLog.objects.create(
                            data=unsynced_data,
                            status='FAILED',
                            response={'error': error_message}
                        )
                        continue
                
                # If we reach here, sync was successful
                unsynced_data.mark_as_synced()
                
                # Create a log entry for the successful sync
                SyncLog.objects.create(
                    data=unsynced_data,
                    status='SUCCESS',
                    response={'message': 'Data processed successfully'}
                )
                
        except Exception as e:
            # Log the exception
            error_message = str(e)
            
            # Add to failed syncs
            failed_syncs.append({
                'sync_id': str(sync_id),
                'error': error_message
            })
            
            # Try to update the unsynced_data record if it was created
            try:
                unsynced_data = UnsyncedData.objects.get(id=sync_id)
                unsynced_data.mark_as_failed(error_message)
                
                # Create a log entry
                SyncLog.objects.create(
                    data=unsynced_data,
                    status='FAILED',
                    response={'error': error_message}
                )
            except UnsyncedData.DoesNotExist:
                # Record not created, nothing to update
                pass
    
    # Prepare the response
    if not failed_syncs:
        response_data = {
            'status': 'success',
            'message': 'All data synced successfully',
        }
    else:
        response_data = {
            'status': 'partial',
            'message': f'{len(data_items) - len(failed_syncs)} of {len(data_items)} items synced successfully',
            'failed_sync_ids': failed_syncs
        }
    
    return Response(response_data)

@swagger_auto_schema(
    method='post',
    operation_description="Endpoint for resolving data sync conflicts",
    request_body=ConflictResolutionSerializer,
    responses={
        200: openapi.Response('Conflict resolved successfully'),
        400: 'Invalid data',
        404: 'Sync record not found',
        401: 'Not authorized'
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resolve_conflict(request):
    """
    Resolve conflicts in synced data
    
    When the server detects a conflict during sync (e.g., duplicate records),
    the client can use this endpoint to resolve the conflict.
    """
    serializer = ConflictResolutionSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response({
            'status': 'error',
            'message': 'Invalid data format',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    validated_data = serializer.validated_data
    sync_id = validated_data['sync_id']
    resolution = validated_data['resolution']
    
    try:
        # Get the unsynced data record
        unsynced_data = UnsyncedData.objects.get(id=sync_id)
        
        # Check permission - only the original agent or admin can resolve
        if not request.user.is_staff and unsynced_data.agent != request.user:
            return Response({
                'status': 'error',
                'message': 'You do not have permission to resolve this conflict'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Make sure this is actually a conflict
        if unsynced_data.sync_status != 'CONFLICT':
            return Response({
                'status': 'error',
                'message': 'This record is not in conflict state'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Process the resolution based on the action
        with transaction.atomic():
            action = resolution['action']
            
            if action == 'overwrite':
                # Replace existing data with the new payload
                success, error_message = handle_overwrite_resolution(unsynced_data, resolution.get('payload', {}))
            
            elif action == 'discard':
                # Discard the sync item, mark as synced with no action
                success, error_message = True, ""
                unsynced_data.mark_as_synced()
                
                # Log the resolution
                SyncLog.objects.create(
                    data=unsynced_data,
                    status='SUCCESS',
                    response={'message': 'Conflict resolved: data discarded'}
                )
            
            elif action == 'merge':
                # Merge existing data with the new payload
                success, error_message = handle_merge_resolution(unsynced_data, resolution.get('payload', {}))
            
            else:
                # Should never get here due to serializer validation
                return Response({
                    'status': 'error',
                    'message': f'Invalid action: {action}'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if resolution was successful
            if not success:
                return Response({
                    'status': 'error',
                    'message': error_message
                }, status=status.HTTP_400_BAD_REQUEST)
            
        return Response({
            'status': 'success',
            'message': 'Conflict resolved successfully'
        })
        
    except UnsyncedData.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Sync record not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f'Error resolving conflict: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@swagger_auto_schema(
    method='get',
    operation_description="Get pending sync items for the current user",
    responses={
        200: UnsyncedDataSerializer(many=True),
        401: 'Not authorized'
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pending_syncs(request):
    """
    Get all pending sync items for the current user
    
    This allows the mobile app to retrieve items that need
    to be synced in case of previous failures.
    """
    # Get all pending items for this user's device
    device_id = request.GET.get('device_id', None)
    
    if not device_id:
        return Response({
            'status': 'error',
            'message': 'device_id parameter is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    pending_items = UnsyncedData.objects.filter(
        agent=request.user,
        device_id=device_id,
        sync_status__in=['PENDING', 'FAILED', 'CONFLICT']
    ).order_by('timestamp')
    
    serializer = UnsyncedDataSerializer(pending_items, many=True)
    
    return Response(serializer.data)

# Helper functions for processing different data types

def process_price_data(payload, user):
    """Process market price research data from payload"""
    try:
        # Extract price data from payload
        price_data = payload.copy()
        
        # Set the agent ID if not provided
        if 'agent' not in price_data:
            price_data['agent'] = user.id
        
        # Validate using the serializer
        serializer = MarketPriceResearchSerializer(data=price_data)
        if not serializer.is_valid():
            return False, f"Invalid price data: {serializer.errors}"
        
        # Check for duplicates based on key fields
        existing = MarketPriceResearch.objects.filter(
            product_name=price_data['product_name'],
            source_name=price_data['source_name'],
            date_observed=price_data.get('date_observed', timezone.now())
        )
        
        if existing.exists():
            # We have a potential conflict
            return False, "Duplicate price entry detected"
        
        # Create the price entry
        serializer.save(agent=user)
        
        return True, ""
        
    except Exception as e:
        return False, str(e)

def process_sale_data(payload, user):
    """Process sales data from payload"""
    # This would integrate with your existing sales/order processing
    # Not implemented in this example
    return True, ""

def process_stock_update(payload, user):
    """Process stock update data from payload"""
    # This would integrate with your inventory management
    # Not implemented in this example
    return True, ""

def handle_overwrite_resolution(unsynced_data, payload):
    """Handle 'overwrite' resolution for conflicts"""
    try:
        data_type = unsynced_data.data_type
        
        if data_type == 'price':
            # Completely replace with new data
            process_price_data(payload, unsynced_data.agent)
        
        elif data_type == 'sale':
            # Handle sales data overwrite
            process_sale_data(payload, unsynced_data.agent)
        
        elif data_type == 'stock_update':
            # Handle stock update overwrite
            process_stock_update(payload, unsynced_data.agent)
        
        # Mark as resolved
        unsynced_data.mark_as_synced()
        
        # Create a log entry
        SyncLog.objects.create(
            data=unsynced_data,
            status='SUCCESS',
            response={'message': 'Conflict resolved: data overwritten'}
        )
        
        return True, ""
        
    except Exception as e:
        return False, str(e)

def handle_merge_resolution(unsynced_data, payload):
    """Handle 'merge' resolution for conflicts"""
    try:
        data_type = unsynced_data.data_type
        
        if data_type == 'price':
            # Get the original payload and merge with new data
            original_data = unsynced_data.get_payload_object()
            
            # Update only the fields provided in the resolution payload
            for key, value in payload.items():
                original_data[key] = value
            
            # Process the merged data
            process_price_data(original_data, unsynced_data.agent)
        
        # Similar handling for other data types would go here
        
        # Mark as resolved
        unsynced_data.mark_as_synced()
        
        # Create a log entry
        SyncLog.objects.create(
            data=unsynced_data,
            status='SUCCESS',
            response={'message': 'Conflict resolved: data merged'}
        )
        
        return True, ""
        
    except Exception as e:
        return False, str(e)