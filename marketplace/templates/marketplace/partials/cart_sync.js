/**
 * Cart Synchronization Helper
 * For the Tanzanian B2B gas delivery system
 */

// Function to fetch and broadcast the current cart count
function syncCartCountAfterChange() {
    console.log('Syncing cart count...');
    
    fetch('/marketplace/cart/count/')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Cart count synced:', data.count);
                
                // Broadcast the cart count update to all listeners
                document.dispatchEvent(new CustomEvent("cart:updated", {
                    detail: { count: data.count }
                }));
            } else {
                console.error('Error syncing cart count:', data.error);
            }
        })
        .catch(error => {
            console.error('Failed to sync cart count:', error);
        });
}

// Export the function for use in other modules
window.syncCartCountAfterChange = syncCartCountAfterChange;
