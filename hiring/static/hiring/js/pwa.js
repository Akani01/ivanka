// ============================================================
// TOLOLEYA PWA - Complete Client-Side Setup
// ============================================================

class OppoGlobePWA {
    constructor() {
        this.deferredPrompt = null;
        this.isInstalled = false;
        this.installPromptShown = false;
        this.swRegistration = null;
        this.swRegistrationAttempts = 0;
        this.maxSwAttempts = 5;
        this.toastTimeout = null;
        this.installBtnTimeout = null;
        
        // Check if already in standalone mode
        this.isStandalone = window.matchMedia('(display-mode: standalone)').matches;
        
        if (this.isStandalone) {
            this.isInstalled = true;
            console.log('📱 OppoGlobe is running as installed app');
        }
        
        this.init();
    }
    
    async init() {
        await this.registerServiceWorkerWithRetry();
        this.setupInstallPrompt();
        this.setupNotifications();
        this.checkForUpdates();
        this.setupConnectivityHandlers();
    }
    
    // ============================================================
    // SERVICE WORKER REGISTRATION WITH RETRY
    // ============================================================
    
    async registerServiceWorkerWithRetry() {
        if (!('serviceWorker' in navigator)) {
            console.warn('⚠️ Service Workers not supported');
            return;
        }
        
        for (let attempt = 1; attempt <= this.maxSwAttempts; attempt++) {
            try {
                const swResponse = await fetch('/sw.js', { method: 'HEAD' });
                
                if (swResponse.status === 429) {
                    console.log(`⏳ Rate limited (429), waiting ${attempt * 3}s before retry ${attempt}...`);
                    await this.sleep(attempt * 3000);
                    continue;
                }
                
                if (!swResponse.ok) {
                    console.log(`⚠️ SW fetch returned ${swResponse.status}, retry ${attempt}...`);
                    await this.sleep(2000);
                    continue;
                }
                
                this.swRegistration = await navigator.serviceWorker.register('/sw.js', {
                    scope: '/'
                });
                
                console.log('✅ Service Worker registered:', this.swRegistration);
                this.swRegistrationAttempts = 0;
                
                navigator.serviceWorker.addEventListener('controllerchange', () => {
                    console.log('🔄 Service Worker controller changed');
                    this.showUpdateNotification();
                });
                
                setInterval(() => this.checkForUpdates(), 60000);
                
                return this.swRegistration;
            } catch (error) {
                console.error(`❌ Service Worker registration attempt ${attempt} failed:`, error.message);
                this.swRegistrationAttempts = attempt;
                
                if (attempt === this.maxSwAttempts) {
                    console.error('❌ All SW registration attempts failed');
                    this.showToast('App update check failed. Please refresh.', 'warning');
                } else {
                    await this.sleep(3000);
                }
            }
        }
    }
    
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    async registerServiceWorker() {
        return this.registerServiceWorkerWithRetry();
    }
    
    async checkForUpdates() {
        if (!this.swRegistration) return;
        try {
            await this.swRegistration.update();
            console.log('🔄 Checked for SW updates');
        } catch (error) {
            console.error('Failed to check for updates:', error);
        }
    }
    
    // ============================================================
    // INSTALL PROMPT - MINIMAL & NON-INTRUSIVE
    // ============================================================
    
    setupInstallPrompt() {
        window.addEventListener('beforeinstallprompt', (e) => {
            console.log('📱 Install prompt available');
            e.preventDefault();
            this.deferredPrompt = e;
            this.installPromptShown = true;
            
            // Show minimal install banner
            this.showInstallBanner();
            
            if (typeof gtag !== 'undefined') {
                gtag('event', 'pwa_prompt_shown', {
                    'event_category': 'PWA',
                    'event_label': 'Install Prompt'
                });
            }
        });
        
        window.addEventListener('appinstalled', () => {
            console.log('🎉 OppoGlobe installed successfully!');
            this.isInstalled = true;
            this.hideInstallBanner();
            
            if (typeof gtag !== 'undefined') {
                gtag('event', 'pwa_installed', {
                    'event_category': 'PWA',
                    'event_label': 'App Installed'
                });
            }
            
            this.sendInstallEvent('installed');
            this.showToast('🎉 OppoGlobe installed successfully!', 'success');
        });
        
        window.addEventListener('displaymodechange', (e) => {
            console.log('Display mode changed:', e);
            this.isStandalone = window.matchMedia('(display-mode: standalone)').matches;
            if (this.isStandalone) {
                this.isInstalled = true;
                this.hideInstallBanner();
            }
        });
    }
    
    // ============================================================
    // MINIMAL INSTALL BANNER (Non-intrusive, auto-dismiss)
    // ============================================================
    
    showInstallBanner() {
        // Remove existing banner if any
        this.hideInstallBanner();
        
        // Don't show if app is already installed or in standalone mode
        if (this.isInstalled || this.isStandalone) return;
        
        const banner = document.createElement('div');
        banner.id = 'OppoGlobeInstallBanner';
        banner.style.cssText = `
            position: fixed;
            bottom: 80px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 9999;
            background: white;
            border-radius: 14px;
            padding: 12px 20px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.12);
            display: flex;
            align-items: center;
            gap: 14px;
            max-width: 420px;
            width: 90%;
            animation: slideUp 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
            border: 1px solid rgba(0,0,0,0.06);
            backdrop-filter: blur(8px);
            background: rgba(255,255,255,0.95);
        `;
        
        banner.innerHTML = `
            <div style="display:flex;align-items:center;gap:12px;flex:1;min-width:0;">
                <div style="width:40px;height:40px;border-radius:10px;background:linear-gradient(135deg,#c62828,#ff589e);display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                    <i class="fas fa-download" style="color:white;font-size:18px;"></i>
                </div>
                <div style="flex:1;min-width:0;">
                    <div style="font-weight:600;font-size:14px;color:#1a1a2e;">Install OppoGlobe</div>
                    <div style="font-size:12px;color:#8e8e8e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">Get the full app experience</div>
                </div>
            </div>
            <div style="display:flex;align-items:center;gap:6px;flex-shrink:0;">
                <button id="installNowBtn" style="
                    background: linear-gradient(135deg, #c62828, #ff589e);
                    color: white;
                    border: none;
                    padding: 6px 16px;
                    border-radius: 20px;
                    font-size: 13px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: transform 0.2s;
                    white-space: nowrap;
                ">Install</button>
                <button id="installDismissBtn" style="
                    background: none;
                    border: none;
                    color: #8e8e8e;
                    font-size: 18px;
                    cursor: pointer;
                    padding: 4px 8px;
                    transition: color 0.2s;
                ">✕</button>
            </div>
        `;
        
        document.body.appendChild(banner);
        
        // Install button handler
        document.getElementById('installNowBtn')?.addEventListener('click', () => {
            this.handleInstallClick();
        });
        
        // Dismiss button handler
        document.getElementById('installDismissBtn')?.addEventListener('click', () => {
            this.hideInstallBanner();
            // Store dismissal preference
            try {
                localStorage.setItem('OppoGlobe_install_dismissed', 'true');
            } catch(e) {}
        });
        
        // Auto-hide after 20 seconds if not interacted
        if (this.installBtnTimeout) clearTimeout(this.installBtnTimeout);
        this.installBtnTimeout = setTimeout(() => {
            this.hideInstallBanner();
        }, 20000);
    }
    
    hideInstallBanner() {
        const banner = document.getElementById('OppoGlobeInstallBanner');
        if (banner) {
            banner.style.animation = 'slideDown 0.3s ease forwards';
            setTimeout(() => {
                if (banner.parentNode) banner.remove();
            }, 300);
        }
        if (this.installBtnTimeout) {
            clearTimeout(this.installBtnTimeout);
            this.installBtnTimeout = null;
        }
    }
    
    async handleInstallClick() {
        if (!this.deferredPrompt) {
            this.showToast('Install prompt not available. Try opening in Chrome.', 'warning');
            return;
        }
        
        try {
            this.deferredPrompt.prompt();
            const result = await this.deferredPrompt.userChoice;
            
            if (result.outcome === 'accepted') {
                console.log('✅ User installed the app');
                this.isInstalled = true;
                this.hideInstallBanner();
                
                if (typeof gtag !== 'undefined') {
                    gtag('event', 'pwa_install_accepted', {
                        'event_category': 'PWA'
                    });
                }
                
                this.sendInstallEvent('accepted');
                this.showToast('🎉 Thank you for installing OppoGlobe!', 'success');
            } else {
                console.log('❌ User dismissed install');
                this.showToast('Installation canceled', 'info');
                
                if (typeof gtag !== 'undefined') {
                    gtag('event', 'pwa_install_dismissed', {
                        'event_category': 'PWA'
                    });
                }
            }
            
            this.deferredPrompt = null;
        } catch (error) {
            console.error('Install error:', error);
            this.showToast('Error installing app', 'error');
        }
    }
    
    // ============================================================
    // NOTIFICATIONS - MINIMAL & PROFESSIONAL
    // ============================================================
    
    setupNotifications() {
        if (!('Notification' in window)) {
            console.log('Notifications not supported');
            return;
        }
        
        const isLoggedIn = document.querySelector('[data-user-logged-in]')?.dataset.userLoggedIn === 'true';
        if (!isLoggedIn) return;
        
        if (Notification.permission === 'granted') {
            console.log('✅ Notification permission granted');
            this.subscribeToPush();
        } else if (Notification.permission === 'default') {
            const bell = document.querySelector('.notification-wrapper a');
            if (bell) {
                bell.addEventListener('click', (e) => {
                    if (Notification.permission === 'default') {
                        e.preventDefault();
                        this.askNotificationPermission();
                    }
                });
            }
        }
    }
    
    async askNotificationPermission() {
        if (!('Notification' in window)) {
            this.showToast('Notifications not supported', 'warning');
            return;
        }
        
        if (Notification.permission === 'granted') {
            this.showToast('Notifications already enabled', 'success');
            return;
        }
        
        if (Notification.permission === 'denied') {
            this.showToast('Notifications blocked. Please enable in browser settings.', 'warning');
            return;
        }
        
        try {
            const permission = await Notification.requestPermission();
            
            if (permission === 'granted') {
                console.log('✅ Notification permission granted');
                this.showToast('Notifications enabled! 🔔', 'success');
                await this.subscribeToPush();
            } else {
                console.log('❌ Notification permission denied');
                this.showToast('Notifications disabled', 'warning');
            }
        } catch (error) {
            console.error('Notification permission error:', error);
        }
    }
    
    async subscribeToPush() {
        try {
            let registration = await navigator.serviceWorker.ready;
            
            const VAPID_PUBLIC_KEY = 'BAt7mPbnnynQNSCQalbpByolKwY_0LS3JyiQ0VSWpDDC2wFkyVJBsEMmra-beaYx-cUMTXgeQAtrzIYDYnnp7tk';
            
            const subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: this.urlBase64ToUint8Array(VAPID_PUBLIC_KEY)
            });
            
            console.log('✅ Push subscription successful:', subscription);
            
            await this.sendSubscriptionToServer(subscription);
            
            this.showToast('🔔 Push notifications enabled!', 'success');
            
            return subscription;
        } catch (error) {
            console.error('❌ Push subscription error:', error);
            
            let errorMsg = 'Push notifications unavailable. ';
            if (error.message.includes('ApplicationServerKey')) {
                errorMsg += 'Invalid VAPID key configuration.';
            } else if (error.message.includes('permission')) {
                errorMsg += 'Please allow notification permissions.';
            } else if (error.message.includes('429')) {
                errorMsg += 'Server is busy. Please try again later.';
            } else {
                errorMsg += error.message;
            }
            
            this.showToast(errorMsg, 'warning');
            return null;
        }
    }
    
    async sendSubscriptionToServer(subscription) {
        try {
            const response = await fetch('/api/push/subscribe/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify(subscription)
            });
            
            const data = await response.json();
            
            if (data.success) {
                console.log('✅ Subscription saved to server:', data);
            } else {
                console.error('❌ Server error:', data.error);
            }
        } catch (error) {
            console.error('❌ Failed to save subscription:', error);
        }
    }
    
    // ============================================================
    // CONNECTIVITY HANDLERS
    // ============================================================
    
    setupConnectivityHandlers() {
        window.addEventListener('online', () => {
            console.log('🌐 Back online');
            this.hideOfflineBanner();
            this.showToast('Back online!', 'success');
            
            if (!this.swRegistration) {
                this.registerServiceWorkerWithRetry();
            }
            
            this.syncPendingData();
        });
        
        window.addEventListener('offline', () => {
            console.log('📴 Offline');
            this.showOfflineBanner();
            this.showToast('You are offline. Some features may be limited.', 'warning');
        });
        
        if (!navigator.onLine) {
            this.showOfflineBanner();
        }
    }
    
    showOfflineBanner() {
        let banner = document.getElementById('offlineBanner');
        if (banner) return;
        
        banner = document.createElement('div');
        banner.id = 'offlineBanner';
        banner.innerHTML = `
            <i class="fas fa-wifi-slash me-2"></i>
            You are offline. Some features may not work.
        `;
        banner.style.cssText = `
            position: fixed;
            top: 70px;
            left: 0;
            right: 0;
            background: #dc3545;
            color: white;
            text-align: center;
            padding: 8px;
            z-index: 9999;
            font-weight: 500;
            font-size: 13px;
            animation: slideDown 0.3s ease;
        `;
        
        document.body.prepend(banner);
    }
    
    hideOfflineBanner() {
        const banner = document.getElementById('offlineBanner');
        if (banner) {
            banner.style.animation = 'slideUp 0.3s ease forwards';
            setTimeout(() => banner.remove(), 300);
        }
    }
    
    async syncPendingData() {
        try {
            const response = await fetch('/api/sync-pending/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken()
                }
            });
            const data = await response.json();
            console.log('✅ Synced pending data:', data);
        } catch (error) {
            console.error('Sync failed:', error);
        }
    }
    
    // ============================================================
    // MINIMAL TOAST NOTIFICATIONS (Non-intrusive, auto-dismiss)
    // ============================================================
    
    showToast(message, type = 'info') {
        // Clear any existing toast timeout
        if (this.toastTimeout) {
            clearTimeout(this.toastTimeout);
            this.toastTimeout = null;
        }
        
        // Remove existing toast
        const existingToast = document.getElementById('OppoGlobeToast');
        if (existingToast) {
            existingToast.style.animation = 'slideDown 0.3s ease forwards';
            setTimeout(() => {
                if (existingToast.parentNode) existingToast.remove();
            }, 300);
        }
        
        const colors = {
            success: { bg: '#28a745', icon: 'fa-check-circle' },
            error: { bg: '#dc3545', icon: 'fa-exclamation-circle' },
            info: { bg: '#17a2b8', icon: 'fa-info-circle' },
            warning: { bg: '#ffc107', icon: 'fa-exclamation-triangle' }
        };
        
        const color = colors[type] || colors.info;
        
        const toast = document.createElement('div');
        toast.id = 'OppoGlobeToast';
        toast.style.cssText = `
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 10001;
            background: rgba(26, 26, 46, 0.92);
            backdrop-filter: blur(12px);
            color: white;
            padding: 10px 20px;
            border-radius: 12px;
            font-weight: 500;
            font-size: 14px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.15);
            animation: slideUp 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
            display: flex;
            align-items: center;
            gap: 10px;
            max-width: 90%;
            border: 1px solid rgba(255,255,255,0.06);
            pointer-events: none;
            user-select: none;
        `;
        
        const iconColor = type === 'success' ? '#28a745' : 
                         type === 'error' ? '#dc3545' : 
                         type === 'warning' ? '#ffc107' : '#17a2b8';
        
        toast.innerHTML = `
            <i class="fas ${color.icon}" style="color:${iconColor};font-size:16px;"></i>
            <span style="flex:1;min-width:0;">${message}</span>
            <button onclick="this.parentElement.style.animation='slideDown 0.3s ease forwards';setTimeout(()=>this.parentElement.remove(),300)" style="
                background: none;
                border: none;
                color: rgba(255,255,255,0.5);
                font-size: 16px;
                cursor: pointer;
                padding: 0 4px;
                pointer-events: auto;
                transition: color 0.2s;
            ">✕</button>
        `;
        
        document.body.appendChild(toast);
        
        // Auto-dismiss after 4 seconds
        this.toastTimeout = setTimeout(() => {
            const t = document.getElementById('OppoGlobeToast');
            if (t) {
                t.style.animation = 'slideDown 0.3s ease forwards';
                setTimeout(() => {
                    if (t.parentNode) t.remove();
                }, 300);
            }
            this.toastTimeout = null;
        }, 4000);
    }
    
    showUpdateNotification() {
        const toast = document.createElement('div');
        toast.id = 'OppoGlobeUpdateToast';
        toast.style.cssText = `
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 10001;
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(12px);
            border-radius: 14px;
            padding: 14px 20px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.12);
            display: flex;
            align-items: center;
            gap: 14px;
            max-width: 420px;
            width: 90%;
            animation: slideUp 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
            border: 1px solid rgba(0,0,0,0.06);
        `;
        
        toast.innerHTML = `
            <div style="display:flex;align-items:center;gap:12px;flex:1;min-width:0;">
                <div style="width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#c62828,#ff589e);display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                    <i class="fas fa-sync-alt" style="color:white;font-size:16px;"></i>
                </div>
                <div style="flex:1;min-width:0;">
                    <div style="font-weight:600;font-size:14px;color:#1a1a2e;">Update Available</div>
                    <div style="font-size:12px;color:#8e8e8e;">A new version is ready</div>
                </div>
            </div>
            <button onclick="window.location.reload()" style="
                background: linear-gradient(135deg, #c62828, #ff589e);
                color: white;
                border: none;
                padding: 6px 16px;
                border-radius: 20px;
                font-size: 13px;
                font-weight: 600;
                cursor: pointer;
                transition: transform 0.2s;
                white-space: nowrap;
            ">Update</button>
            <button onclick="this.parentElement.style.animation='slideDown 0.3s ease forwards';setTimeout(()=>this.parentElement.remove(),300)" style="
                background: none;
                border: none;
                color: #8e8e8e;
                font-size: 16px;
                cursor: pointer;
                padding: 0 4px;
            ">✕</button>
        `;
        
        document.body.appendChild(toast);
        setTimeout(() => {
            const t = document.getElementById('OppoGlobeUpdateToast');
            if (t) {
                t.style.animation = 'slideDown 0.3s ease forwards';
                setTimeout(() => {
                    if (t.parentNode) t.remove();
                }, 300);
            }
        }, 10000);
    }
    
    // ============================================================
    // UTILITY FUNCTIONS
    // ============================================================
    
    sendInstallEvent(status) {
        fetch('/api/pwa/install-event/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            },
            body: JSON.stringify({
                status: status,
                display_mode: this.isStandalone ? 'standalone' : 'browser',
                platform: navigator.platform,
                user_agent: navigator.userAgent,
                timestamp: new Date().toISOString()
            })
        }).catch(err => console.error('Failed to send install event:', err));
    }
    
    getCSRFToken() {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') return decodeURIComponent(value);
        }
        return null;
    }
    
    urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding)
            .replace(/-/g, '+')
            .replace(/_/g, '/');
        
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }
}

// ============================================================
// INITIALIZE PWA
// ============================================================

document.addEventListener('DOMContentLoaded', function() {
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches;
    
    if (!isStandalone) {
        window.OppoGlobePWA = new OppoGlobePWA();
        console.log('✅ OppoGlobe PWA initialized');
    } else {
        console.log('📱 OppoGlobe running as installed app');
    }
});

// Add CSS animations
const pwaStyles = document.createElement('style');
pwaStyles.textContent = `
    @keyframes slideUp {
        from { transform: translateX(-50%) translateY(20px); opacity: 0; }
        to { transform: translateX(-50%) translateY(0); opacity: 1; }
    }
    @keyframes slideDown {
        from { transform: translateX(-50%) translateY(0); opacity: 1; }
        to { transform: translateX(-50%) translateY(20px); opacity: 0; }
    }
`;
document.head.appendChild(pwaStyles);

console.log('📱 OppoGlobe PWA loaded successfully');