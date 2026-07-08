<?php
declare(strict_types=1);

/** @var array $_ */
/** @var \OCP\IL10N $l */

script('filantropia_solar', 'admin');
style('filantropia_solar', 'admin');
?>

<div id="filantropia_solar_admin" class="section">
    <h2><?php p($l->t('FilantropiaSolar Admin Dashboard')); ?></h2>
    <p class="settings-hint">
        <?php p($l->t('Manage global stations, trigger ML training, clear model cache, and configure the ML service URL.')); ?>
    </p>
    <div id="filantropia_solar_admin_vue"></div>
</div>