/**
 * TradingAI Pro - Service Worker
 * Enables offline support, caching, and push notifications
 */

const CACHE_NAME = 'tradingai-v2.0';
const STATIC_CACHE = 'tradingai-static-v2.0';
const DYNAMIC_CACHE = 'tradingai-dynamic-v2.0';

// Assets to cache immediately
const STATIC_ASSETS = [
  '/',
  '/static/manifest.json',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  'https://cdn.tailwindcss.com',
  'https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js',
  'https://cdn.jsdelivr.net/npm/chart.js',
  'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap'
];

// API endpoints to cache with network-first strategy
const API_ENDPOINTS = [
  '/api/signals',
  '/api/best',
  '/api/market',
  '/api/portfolio',
  '/health'
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
  console.log('[SW] Installing TradingAI PWA...');
  
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => {
        console.log('[SW] Caching static assets');
        return cache.addAll(STATIC_ASSETS);
      })
      .then(() => self.skipWaiting())
  );
});

// Activate event - clean old caches
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating TradingAI PWA...');
  
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== STATIC_CACHE && name !== DYNAMIC_CACHE)
          .map((name) => {
            console.log('[SW] Deleting old cache:', name);
            return caches.delete(name);
          })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch event - serve from cache or network
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);
  
  // Skip non-GET requests
  if (request.method !== 'GET') return;
  
  // API requests - Network first, fallback to cache
  if (url.pathname.startsWith('/api/') || API_ENDPOINTS.some(ep => url.pathname.includes(ep))) {
    event.respondWith(networkFirst(request));
    return;
  }
  
  // Static assets - Cache first, fallback to network
  event.respondWith(cacheFirst(request));
});

// Cache-first strategy
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) {
    return cached;
  }
  
  try {
    const response = await fetch(request);
    
    // Cache successful responses
    if (response.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, response.clone());
    }
    
    return response;
  } catch (error) {
    console.log('[SW] Fetch failed:', error);
    return new Response('Offline', { status: 503 });
  }
}

// Network-first strategy (for API calls)
async function networkFirst(request) {
  try {
    const response = await fetch(request);
    
    // Cache successful API responses
    if (response.ok) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, response.clone());
    }
    
    return response;
  } catch (error) {
    console.log('[SW] Network failed, trying cache:', request.url);
    const cached = await caches.match(request);
    
    if (cached) {
      return cached;
    }
    
    // Return offline JSON for API requests
    return new Response(
      JSON.stringify({
        error: 'Offline',
        message: 'No cached data available',
        offline: true
      }),
      {
        status: 503,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
}

// Push notification handler
self.addEventListener('push', (event) => {
  console.log('[SW] Push received');
  
  let data = { title: 'TradingAI Alert', body: 'New trading signal!' };
  
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data.body = event.data.text();
    }
  }
  
  const options = {
    body: data.body || data.message,
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/icon-72x72.png',
    vibrate: [100, 50, 100],
    data: {
      url: data.url || '/',
      timestamp: Date.now()
    },
    actions: [
      { action: 'view', title: '📊 View Signal' },
      { action: 'dismiss', title: '✖ Dismiss' }
    ],
    tag: data.tag || 'tradingai-notification',
    renotify: true
  };
  
  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Notification click handler
self.addEventListener('notificationclick', (event) => {
  console.log('[SW] Notification clicked:', event.action);
  
  event.notification.close();
  
  if (event.action === 'dismiss') return;
  
  const url = event.notification.data?.url || '/';
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        // Focus existing window if open
        for (const client of clientList) {
          if (client.url.includes(self.location.origin) && 'focus' in client) {
            client.navigate(url);
            return client.focus();
          }
        }
        // Open new window
        return clients.openWindow(url);
      })
  );
});

// Background sync for offline actions
self.addEventListener('sync', (event) => {
  console.log('[SW] Background sync:', event.tag);
  
  if (event.tag === 'sync-trades') {
    event.waitUntil(syncTrades());
  }
});

async function syncTrades() {
  // Sync any pending trades when back online
  const cache = await caches.open('tradingai-pending');
  const requests = await cache.keys();
  
  for (const request of requests) {
    try {
      const response = await fetch(request);
      if (response.ok) {
        await cache.delete(request);
        console.log('[SW] Synced:', request.url);
      }
    } catch (error) {
      console.log('[SW] Sync failed:', error);
    }
  }
}

// Periodic background sync (if supported)
self.addEventListener('periodicsync', (event) => {
  if (event.tag === 'update-signals') {
    event.waitUntil(updateSignals());
  }
});

async function updateSignals() {
  try {
    const response = await fetch('/api/signals');
    const data = await response.json();
    
    // Notify if new high-confidence signals
    const highConfidence = data.signals?.filter(s => s.score >= 8.5) || [];
    
    if (highConfidence.length > 0) {
      self.registration.showNotification('🚀 High Confidence Signal!', {
        body: `${highConfidence[0].symbol}: Score ${highConfidence[0].score}/10`,
        icon: '/static/icons/icon-192x192.png',
        tag: 'signal-alert'
      });
    }
  } catch (error) {
    console.log('[SW] Periodic sync failed:', error);
  }
}

console.log('[SW] TradingAI Service Worker loaded');
