(function () {
  'use strict';

  if (window.__OPPOGLOBE_NOTIFICATIONS_LOADED__) return;
  window.__OPPOGLOBE_NOTIFICATIONS_LOADED__ = true;

  const SOUND_KEY = 'oppoglobe_notification_sound';
  const AUDIO_SRC = '/static/hiring/audio/notification.mp3';
  const SW_URL = '/sw.js';
  const CHANNEL_NAME = 'oppoglobe-notifications';

  let audio = null;
  let audioUnlocked = false;
  let lastPlayedKey = '';
  let lastPlayedAt = 0;

  function soundEnabled() {
    return localStorage.getItem(SOUND_KEY) !== 'off';
  }

  function getAudio() {
    if (audio) return audio;
    audio = new Audio(AUDIO_SRC);
    audio.preload = 'auto';
    audio.volume = 1;
    return audio;
  }

  async function unlockAudio() {
    if (audioUnlocked || !soundEnabled()) return;
    const el = getAudio();
    try {
      const oldVolume = el.volume;
      el.volume = 0;
      await el.play();
      el.pause();
      el.currentTime = 0;
      el.volume = oldVolume;
      audioUnlocked = true;
    } catch (_) {
      // Browsers require a user gesture before page audio may autoplay.
    }
  }

  async function playSound(payload) {
    if (!soundEnabled()) return;
    if (payload && (payload.silent === true || payload.sound === false)) return;

    const key = String(
      (payload && (payload.notification_id || payload.tag || payload.id)) ||
      ((payload && payload.title) || '') + '|' + ((payload && payload.body) || '')
    );
    const now = Date.now();
    if (key && key === lastPlayedKey && now - lastPlayedAt < 2500) return;

    lastPlayedKey = key;
    lastPlayedAt = now;

    const el = getAudio();
    try {
      el.pause();
      el.currentTime = 0;
      el.volume = 1;
      await el.play();
      audioUnlocked = true;
    } catch (_) {
      // If autoplay is blocked, the OS/browser notification still provides
      // its normal notification sound when silent=false.
    }
  }

  function dispatchNotification(payload) {
    playSound(payload || {});
    window.dispatchEvent(new CustomEvent('oppoglobe:notification', {
      detail: payload || {}
    }));
  }

  async function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) return;
    try {
      await navigator.serviceWorker.register(SW_URL, { scope: '/' });
      await navigator.serviceWorker.ready;
    } catch (err) {
      console.debug('OppoGlobe service worker registration skipped:', err);
    }
  }

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', function (event) {
      const data = event.data || {};
      if (data.type === 'OPPOGLOBE_PUSH_RECEIVED') {
        dispatchNotification(data.payload || {});
      }
    });
  }

  // BroadcastChannel is a second path so several open tabs stay in sync.
  let channel = null;
  if ('BroadcastChannel' in window) {
    try {
      channel = new BroadcastChannel(CHANNEL_NAME);
      channel.addEventListener('message', function (event) {
        const data = event.data || {};
        if (data.type === 'OPPOGLOBE_PUSH_RECEIVED') {
          dispatchNotification(data.payload || {});
        }
      });
    } catch (_) {}
  }

  // Unlock audio on the first normal interaction on every standalone page.
  ['pointerdown', 'touchstart', 'keydown'].forEach(function (eventName) {
    window.addEventListener(eventName, unlockAudio, { passive: true, once: true });
  });

  window.OppoGlobeNotifications = {
    playSound,
    unlockAudio,
    soundEnabled,
    enableSound: function () {
      localStorage.setItem(SOUND_KEY, 'on');
      return unlockAudio();
    },
    disableSound: function () {
      localStorage.setItem(SOUND_KEY, 'off');
    }
  };

  registerServiceWorker();
})();
