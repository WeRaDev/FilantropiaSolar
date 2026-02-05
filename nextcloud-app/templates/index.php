<?php
/**
 * FilantropiaSolar - Main Template
 * Loads the Vue.js application for the full UI experience
 */
declare(strict_types=1);

use OCP\Util;

// Load Vue.js application scripts and styles
Util::addScript('filantropia_solar', 'vendor');
Util::addScript('filantropia_solar', 'filantropia_solar-main');
Util::addStyle('filantropia_solar', 'filantropia_solar-main');
?>

<div id="app-content">
    <!-- Vue.js Application Mount Point -->
    <div id="filantropia-solar-app">
        <!-- Loading state while Vue initializes -->
        <div class="fs-loading">
            <div class="fs-loading-spinner"></div>
            <p><?php p($l->t('Loading FilantropiaSolar...')); ?></p>
        </div>
    </div>
</div>

<style>
/* Loading state styles */
.fs-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 400px;
    color: #666;
}

.fs-loading-spinner {
    width: 48px;
    height: 48px;
    border: 4px solid #f0f0f0;
    border-top-color: #C4B552;
    border-radius: 50%;
    animation: fs-spin 1s linear infinite;
    margin-bottom: 16px;
}

@keyframes fs-spin {
    to { transform: rotate(360deg); }
}

/* Ensure app content fills available space */
#app-content {
    width: 100%;
    height: calc(100vh - 50px);
    overflow: hidden;
    box-sizing: border-box;
    padding: 0 !important;
}

#filantropia-solar-app {
    width: 100%;
    height: 100%;
}

/* Golden brand theme overrides for Nextcloud dark mode compatibility */
.app-filantropia_solar {
    --fs-golden-primary: #C4B552;
    --fs-golden-secondary: #D4C563;
    --fs-golden-olive: #A89D3F;
    --fs-cream-bg: #FDFBF5;
    --fs-charcoal: #2D2D2D;
}
</style>
