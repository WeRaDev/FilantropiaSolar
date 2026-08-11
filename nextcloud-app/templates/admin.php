<?php
declare(strict_types=1);

/** @var array $_ */
/** @var \OCP\IL10N $l */

use OCP\Util;

// Webpack entries: vendor + filantropia_solar-admin (not bare "admin.js")
Util::addScript('filantropia_solar', 'vendor');
Util::addScript('filantropia_solar', 'filantropia_solar-admin');
Util::addStyle('filantropia_solar', 'filantropia_solar-admin');
?>

<div id="filantropia_solar_admin" class="section">
    <h2><?php p($l->t('FilantropiaSolar Admin Dashboard')); ?></h2>
    <p class="settings-hint">
        <?php p($l->t('Manage stations and lifecycle (promote / install / soft-remove), ML training, cache, and ML service URL.')); ?>
    </p>
    <div id="filantropia_solar_admin_vue"></div>
</div>
