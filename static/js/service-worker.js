// Service Worker for Kikapu PWA
const CACHE_NAME = 'kikapu-cache-v1';
const urlsToCache = [
  '/',
  '/marketplace/', // Added marketplace URL
  '/static/css/tailwind.css',
  '/static/css/bootstrap-overrides.css',
  '/static/css/cart-mobile.css',
  '/static/js/cart.js',
  '/static/images/placeholder.png',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css'
];

// Install event - cache key static assets with improved error handling
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        // Use individual cache.add() operations instead of cache.addAll()
        // This way, if one resource fails, others can still be cached
        return Promise.allSettled(
          urlsToCache.map(url => 
            cache.add(url).catch(error => {
              console.warn(`Failed to cache ${url}: ${error.message}`);
              // Continue despite the error
              return Promise.resolve();
            })
          )
        );
      })
      .catch(error => {
        console.error('Service worker cache initialization failed:', error);
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Fetch event - use cache-first strategy for static assets, network-first for API requests
self.addEventListener('fetch', event => {
  // Skip non-GET requests and browser extensions
  if (event.request.method !== 'GET' || event.request.url.startsWith('chrome-extension://')) {
    return;
  }

  // For API requests, use network-first strategy
  if (event.request.url.includes('/api/')) {
    networkFirstStrategy(event);
    return;
  }

  // For static assets and other requests, use cache-first strategy
  event.respondWith(
    caches.match(event.request)
      .then(cachedResponse => {
        if (cachedResponse) {
          return cachedResponse;
        }
        
        return fetch(event.request)
          .then(response => {
            // Don't cache if not a valid response
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }

            // Clone the response
            const responseToCache = response.clone();
            
            caches.open(CACHE_NAME)
              .then(cache => {
                cache.put(event.request, responseToCache);
              })
              .catch(error => {
                console.warn('Failed to cache response:', error);
              });

            return response;
          })
          .catch(() => {
            // If both cache and network fail, return a fallback response for HTML requests
            if (event.request.headers.get('accept').includes('text/html')) {
              return caches.match('/');
            }
          });
      })
  );
});

// Network-first strategy implementation
function networkFirstStrategy(event) {
  event.respondWith(
    fetch(event.request)
      .then(response => {
        // Clone the response
        const responseClone = response.clone();
        
        if (response.ok) {
          caches.open(CACHE_NAME)
            .then(cache => {
              cache.put(event.request, responseClone);
            })
            .catch(error => {
              console.warn('Failed to cache API response:', error);
            });
        }
          
        return response;
      })
      .catch(() => {
        // If network request fails, try to serve from cache
        return caches.match(event.request);
      })
  );
}