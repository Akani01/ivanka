
(function () {
  'use strict';

  const installBtn = document.getElementById('pwaInstall');
  const menuBtn    = document.getElementById('menuInstall');
  const standalone = window.matchMedia('(display-mode: standalone)').matches
                  || window.navigator.standalone === true;

  // Already installed → hide both entry points
  if (standalone) {
    if (installBtn) installBtn.remove();
    if (menuBtn) menuBtn.remove();
    return;
  }

  const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
  let deferredPrompt = null;

  function showButtons() {
    if (installBtn) installBtn.hidden = false;
    if (menuBtn)    menuBtn.hidden = false;
  }
  function hideButtons() {
    if (installBtn) installBtn.hidden = true;
    if (menuBtn)    menuBtn.hidden = true;
  }

  async function triggerInstall() {
    if (!deferredPrompt) {
      if (isIOS) {
        alert('Tap the Share button (square with arrow), then "Add to Home Screen".');
      }
      return;
    }
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    console.log('[PWA] install outcome:', outcome);
    deferredPrompt = null;
    hideButtons();
  }

  // Chrome / Edge / Samsung Internet / Android
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    showButtons();
  });

  // iOS Safari has no beforeinstallprompt — reveal a manual hint button
  if (isIOS) {
    showButtons();
    if (installBtn) installBtn.innerHTML = '<i class="fas fa-share-from-square"></i> Add to Home Screen';
  }

  if (installBtn) installBtn.addEventListener('click', triggerInstall);
  if (menuBtn)    menuBtn.addEventListener('click', triggerInstall);

  // Hide once installed
  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    hideButtons();
    console.log('[PWA] app installed');
  });
})();

(function(){
 if(!('serviceWorker' in navigator))return;
 const url=document.body.dataset.swUrl;
 if(!url)return;
 window.addEventListener('load',()=>navigator.serviceWorker.register(url,{scope:document.body.dataset.storeHome||'/'}).catch(()=>{}));
})();
