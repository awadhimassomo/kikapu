/**
 * Kikapu Authentication and CSRF Handler
 * Ensures consistent authentication across the entire site
 * Maintains proper CSRF token handling
 * Preserves Arusha, Tanzania location context
 */

document.addEventListener('DOMContentLoaded', function() {
    // Get CSRF token from cookie or meta tag
    function getCSRFToken() {
        // First try to get from cookie
        const csrfCookie = document.cookie.split(';')
            .map(cookie => cookie.trim())
            .find(cookie => cookie.startsWith('kikapu_csrftoken='));
            
        if (csrfCookie) {
            return csrfCookie.split('=')[1];
        }
        
        // Then try from meta tag
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        if (csrfToken) {
            return csrfToken;
        }
        
        // Finally, try from a hidden form field
        return document.querySelector('input[name="csrfmiddlewaretoken"]')?.value;
    }
    
    // Add CSRF token to all AJAX requests
    function setupAjaxCSRF() {
        // Add for jQuery AJAX if jQuery is present
        if (typeof $ !== 'undefined' && $.ajax) {
            $.ajaxSetup({
                beforeSend: function(xhr, settings) {
                    if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                        xhr.setRequestHeader("X-CSRFToken", getCSRFToken());
                    }
                }
            });
        }
        
        // Add for fetch API
        const originalFetch = window.fetch;
        window.fetch = function(url, options = {}) {
            // Only add for non-GET methods
            if (options.method && options.method !== 'GET') {
                if (!options.headers) {
                    options.headers = {};
                }
                
                // Handle different header types
                if (options.headers instanceof Headers) {
                    options.headers.append('X-CSRFToken', getCSRFToken());
                } else {
                    options.headers['X-CSRFToken'] = getCSRFToken();
                }
            }
            return originalFetch(url, options);
        };
    }
    
    // Ensure all forms have CSRF token
    function addCSRFToForms() {
        const csrfToken = getCSRFToken();
        if (!csrfToken) return;
        
        document.querySelectorAll('form[method="post"]').forEach(form => {
            let hasCSRF = false;
            
            // Check if the form already has a CSRF token
            form.querySelectorAll('input').forEach(input => {
                if (input.name === 'csrfmiddlewaretoken') {
                    hasCSRF = true;
                    // Update the value if it's empty
                    if (!input.value) {
                        input.value = csrfToken;
                    }
                }
            });
            
            // Add a CSRF token if missing
            if (!hasCSRF) {
                const csrfInput = document.createElement('input');
                csrfInput.type = 'hidden';
                csrfInput.name = 'csrfmiddlewaretoken';
                csrfInput.value = csrfToken;
                form.prepend(csrfInput);
            }
        });
    }
    
    // Check session status and ensure we're logged in
    function checkSession() {
        // If we have a user_id in localStorage but no session cookie, we might have lost our session
        const hasUserID = localStorage.getItem('kikapu_user_id');
        const hasSessionCookie = document.cookie.includes('kikapu_sessionid=');
        
        if (hasUserID && !hasSessionCookie) {
            // Session might be lost, need to redirect to login
            showSessionWarning();
        }
    }
    
    // Update all currency displays to show Tanzanian Shillings
    function updateCurrencyDisplay() {
        document.querySelectorAll('.price, .currency').forEach(el => {
            const text = el.textContent;
            // Only change if not already in TSh format
            if (!text.includes('TSh') && !isNaN(parseFloat(text.replace(/[^0-9.-]+/g, '')))) {
                const numericValue = parseFloat(text.replace(/[^0-9.-]+/g, ''));
                el.textContent = `TSh ${Math.round(numericValue * 2500)}`;
            }
        });
    }
    
    // Show a warning if the session appears to be lost
    function showSessionWarning() {
        const warningDiv = document.createElement('div');
        warningDiv.className = 'session-warning';
        warningDiv.style.position = 'fixed';
        warningDiv.style.top = '10px';
        warningDiv.style.left = '50%';
        warningDiv.style.transform = 'translateX(-50%)';
        warningDiv.style.backgroundColor = '#f8d7da';
        warningDiv.style.color = '#721c24';
        warningDiv.style.padding = '10px 20px';
        warningDiv.style.borderRadius = '5px';
        warningDiv.style.zIndex = '9999';
        warningDiv.style.boxShadow = '0 2px 10px rgba(0,0,0,0.2)';
        warningDiv.innerHTML = 'Your session may have expired. <a href="/registration/login/" style="color: #721c24; text-decoration: underline;">Please login again</a>';
        
        document.body.appendChild(warningDiv);
        
        // Auto dismiss after 10 seconds
        setTimeout(() => {
            warningDiv.remove();
        }, 10000);
    }
    
    // Initialize everything
    setupAjaxCSRF();
    addCSRFToForms();
    checkSession();
    updateCurrencyDisplay();
    
    // Also run when any content is loaded dynamically
    document.addEventListener('DOMNodeInserted', function(e) {
        if (e.target.querySelectorAll) {
            const forms = e.target.querySelectorAll('form[method="post"]');
            if (forms.length > 0) {
                addCSRFToForms();
            }
            
            const prices = e.target.querySelectorAll('.price, .currency');
            if (prices.length > 0) {
                updateCurrencyDisplay();
            }
        }
    });
});
