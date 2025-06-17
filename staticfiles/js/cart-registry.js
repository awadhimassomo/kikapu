/**
 * Kikapu Cart Registry
 * Centralized cart management system for the Tanzanian B2B gas delivery platform
 * 
 * This registry manages all cart badges and ensures consistent cart count 
 * updates across the entire application.
 */

// Initialize the cart registry
window.KikapuCartRegistry = (function() {
    // Private registry data
    const _registeredBadges = {};
    let _currentCount = 0;
    let _isUpdating = false;
    
    // Log with consistent prefix for easier debugging
    function _log(message, ...args) {
        console.log(`[Cart Registry] ${message}`, ...args);
    }
    
    // Parse count to ensure it's a proper number
    function _parseCount(count) {
        const parsed = parseInt(count);
        return isNaN(parsed) ? 0 : parsed;
    }
    
    // Update all registered badges with the current count
    function _updateAllBadges(count) {
        const parsedCount = _parseCount(count);
        _currentCount = parsedCount;
        
        // Update each badge
        Object.values(_registeredBadges).forEach(badge => {
            if (badge && badge.update && typeof badge.update === 'function') {
                badge.update(parsedCount);
            }
        });
        
        _log(`Updated all badges (${Object.keys(_registeredBadges).length}) with count: ${parsedCount}`);
        return parsedCount;
    }
    
    // Public API
    return {
        /**
         * Register a cart badge with the registry
         * @param {string} id - Unique ID for the badge
         * @param {HTMLElement} element - DOM element representing the badge
         * @param {Function} updateFn - Function to call to update this specific badge
         */
        registerBadge: function(id, element, updateFn) {
            if (id && element) {
                _registeredBadges[id] = {
                    element: element,
                    update: updateFn || function(count) { 
                        element.textContent = count;
                        element.dataset.cartCount = count;
                    }
                };
                
                // Initialize with current count if available
                if (_currentCount > 0) {
                    _registeredBadges[id].update(_currentCount);
                } else if (element.dataset.cartCount) {
                    // If we don't have a count yet, use the badge's data attribute
                    const initialCount = _parseCount(element.dataset.cartCount);
                    if (initialCount > _currentCount) {
                        _currentCount = initialCount;
                    }
                }
                
                _log(`Registered badge: ${id}`);
            }
        },
        
        /**
         * Update all cart badges with a new count
         * @param {number} count - New cart count
         * @param {boolean} isOptimistic - Whether this is an optimistic update
         * @returns {number} The updated count
         */
        updateCount: function(count, isOptimistic = false) {
            // Prevent recursive updates
            if (_isUpdating) {
                _log('Prevented recursive update');
                return _currentCount;
            }
            
            _isUpdating = true;
            try {
                // Store for optional rollback if optimistic
                if (isOptimistic) {
                    this._previousCount = _currentCount;
                }
                
                const updatedCount = _updateAllBadges(count);
                
                // Dispatch global event (only if not already handling an event)
                if (!window.isProcessingCartEvent) {
                    window.isProcessingCartEvent = true;
                    try {
                        document.dispatchEvent(new CustomEvent('cart:updated', {
                            detail: {
                                count: updatedCount,
                                isOptimistic: isOptimistic
                            }
                        }));
                    } finally {
                        // Always reset after a short delay to prevent race conditions
                        setTimeout(() => {
                            window.isProcessingCartEvent = false;
                        }, 50);
                    }
                }
                
                return updatedCount;
            } finally {
                // Always reset the updating flag
                setTimeout(() => {
                    _isUpdating = false;
                }, 50);
            }
        },
        
        /**
         * Roll back to the previous count (used when optimistic updates fail)
         */
        rollback: function() {
            if (this._previousCount !== undefined) {
                _log('Rolling back to previous count:', this._previousCount);
                this.updateCount(this._previousCount);
                delete this._previousCount;
            }
        },
        
        /**
         * Get the current cart count
         * @returns {number} Current cart count
         */
        getCount: function() {
            return _currentCount;
        },
        
        /**
         * For TSh currency formatting - format a number as Tanzanian Shillings
         * @param {number} amount - Amount to format
         * @returns {string} Formatted amount in TSh
         */
        formatTSh: function(amount) {
            // Format as whole number (no decimal places) with thousands separator
            return 'TSh ' + Math.round(amount).toLocaleString('en-TZ');
        }
    };
})();

// Make the registry globally available
window.registerCartBadge = window.KikapuCartRegistry.registerBadge;
window.updateCartCount = window.KikapuCartRegistry.updateCount;
window.rollbackCartCount = window.KikapuCartRegistry.rollback;

// Listen for cart update events and synchronize
document.addEventListener('DOMContentLoaded', function() {
    console.log('[Cart Registry] Initializing...');
    
    // Handle cart:updated events from other components
    document.addEventListener('cart:updated', function(e) {
        if (!window.isProcessingCartEvent && e.detail && e.detail.count !== undefined) {
            // Set a flag to prevent recursion
            window.isProcessingCartEvent = true;
            setTimeout(() => {
                try {
                    const currentCount = window.KikapuCartRegistry.getCount();
                    const newCount = parseInt(e.detail.count);
                    
                    // Only update if the count is different
                    if (!isNaN(newCount) && newCount !== currentCount) {
                        window.KikapuCartRegistry.updateCount(newCount);
                    }
                } finally {
                    window.isProcessingCartEvent = false;
                }
            }, 50);
        }
    });
    
    // Initialize from any already registered badges
    if (window.kikapuCartBadges && window.kikapuCartBadges.length) {
        window.kikapuCartBadges.forEach(badge => {
            window.KikapuCartRegistry.registerBadge(badge.id, badge.element, badge.update);
        });
    }
});
