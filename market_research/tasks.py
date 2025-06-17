from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from .models import UnsyncedData, SyncLog
from .views_sync import process_price_data, process_sale_data, process_stock_update

logger = logging.getLogger(__name__)

@shared_task
def retry_failed_syncs():
    """
    Periodic task to retry failed data synchronizations
    
    This task will look for failed sync attempts and retry them
    based on the configured maximum retries.
    """
    max_retries = 3  # Maximum number of retry attempts
    retry_delay = 15  # Minutes between retries
    
    # Find failed syncs that have been attempted less than max_retries times
    # and haven't been attempted in the last retry_delay minutes
    retry_before = timezone.now() - timedelta(minutes=retry_delay)
    
    failed_syncs = UnsyncedData.objects.filter(
        sync_status='FAILED',
        retry_count__lt=max_retries,
        last_attempt__lt=retry_before
    )
    
    logger.info(f"Found {failed_syncs.count()} failed syncs to retry")
    
    retry_count = 0
    success_count = 0
    
    for sync_item in failed_syncs:
        try:
            # Mark as syncing
            sync_item.mark_as_syncing()
            
            # Process based on data type
            success = False
            error_message = ""
            
            if sync_item.data_type == 'price':
                success, error_message = process_price_data(sync_item.get_payload_object(), sync_item.agent)
            
            elif sync_item.data_type == 'sale':
                success, error_message = process_sale_data(sync_item.get_payload_object(), sync_item.agent)
            
            elif sync_item.data_type == 'stock_update':
                success, error_message = process_stock_update(sync_item.get_payload_object(), sync_item.agent)
            
            # Update status based on result
            if success:
                sync_item.mark_as_synced()
                
                # Create a success log entry
                SyncLog.objects.create(
                    data=sync_item,
                    status='SUCCESS',
                    response={'message': 'Auto-retry successful'}
                )
                
                success_count += 1
                
            else:
                # Still failed, update error message
                sync_item.mark_as_failed(error_message)
                
                # Create a failed log entry
                SyncLog.objects.create(
                    data=sync_item,
                    status='FAILED',
                    response={'error': error_message}
                )
                
                # If we've hit the max retries, mark as permanently failed
                if sync_item.retry_count >= max_retries:
                    logger.warning(f"Sync item {sync_item.id} has reached max retry attempts")
            
            retry_count += 1
            
        except Exception as e:
            logger.error(f"Error retrying sync item {sync_item.id}: {str(e)}")
            
            # Update the error message
            sync_item.mark_as_failed(str(e))
            
            # Create a failed log entry
            SyncLog.objects.create(
                data=sync_item,
                status='FAILED',
                response={'error': str(e)}
            )
    
    logger.info(f"Retry task completed: {success_count} of {retry_count} items synced successfully")
    
    return {
        'total_retried': retry_count,
        'successful': success_count,
        'failed': retry_count - success_count
    }

@shared_task
def clean_old_synced_data(days=30):
    """
    Remove old synced data that is no longer needed
    
    This task will delete synced records older than the specified number of days
    to prevent the database from growing too large.
    """
    cutoff_date = timezone.now() - timedelta(days=days)
    
    # Find old synced records
    old_records = UnsyncedData.objects.filter(
        sync_status='SYNCED',
        timestamp__lt=cutoff_date
    )
    
    count = old_records.count()
    
    # Delete the records
    if count > 0:
        logger.info(f"Cleaning up {count} old synced records")
        old_records.delete()
    
    return {
        'deleted': count,
        'cutoff_date': cutoff_date.isoformat()
    }