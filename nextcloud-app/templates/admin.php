<?php
declare(strict_types=1);

/** @var array $_ */
/** @var \OCP\IL10N $l */

script('filantropia_solar', 'admin');
style('filantropia_solar', 'admin');
?>

<div id="filantropia_solar_admin" class="section">
    <h2><?php p($l->t('FilantropiaSolar Settings')); ?></h2>
    <p class="settings-hint"><?php p($l->t('Configure the solar energy analysis platform.')); ?></p>

    <form id="filantropia_solar_settings">
        <!-- ML Service Configuration -->
        <div class="settings-group">
            <h3><?php p($l->t('ML Service')); ?></h3>

            <div class="form-field">
                <label for="ml_service_url"><?php p($l->t('ML Service URL')); ?></label>
                <input type="url"
                       id="ml_service_url"
                       name="ml_service_url"
                       value="<?php p($_['ml_service_url']); ?>"
                       placeholder="http://filantropia-ml:8501">
                <p class="hint"><?php p($l->t('URL of the ML microservice for predictions.')); ?></p>
            </div>

            <div class="form-field">
                <label><?php p($l->t('Service Status')); ?></label>
                <span class="status-badge status-<?php p($_['ml_status']['status'] ?? 'unknown'); ?>">
                    <?php p($_['ml_status']['status'] ?? 'unknown'); ?>
                </span>
                <?php if (isset($_['ml_status']['models_loaded'])): ?>
                    <span class="status-detail">
                        (<?php p($_['ml_status']['models_loaded']); ?> <?php p($l->t('models loaded')); ?>)
                    </span>
                <?php endif; ?>
            </div>

            <div class="form-field">
                <input type="checkbox"
                       id="predictions_enabled"
                       name="predictions_enabled"
                       class="checkbox"
                       <?php if ($_['predictions_enabled']): ?>checked<?php endif; ?>>
                <label for="predictions_enabled"><?php p($l->t('Enable ML Predictions')); ?></label>
            </div>
        </div>

        <!-- Energy Settings -->
        <div class="settings-group">
            <h3><?php p($l->t('Energy Settings')); ?></h3>

            <div class="form-field">
                <label for="default_grid_price"><?php p($l->t('Default Grid Price (EUR/kWh)')); ?></label>
                <input type="number"
                       id="default_grid_price"
                       name="default_grid_price"
                       value="<?php p($_['default_grid_price']); ?>"
                       step="0.01"
                       min="0"
                       max="1">
                <p class="hint"><?php p($l->t('Default electricity price for savings calculations.')); ?></p>
            </div>

            <div class="form-field">
                <label for="weather_sync_interval"><?php p($l->t('Weather Sync Interval (hours)')); ?></label>
                <input type="number"
                       id="weather_sync_interval"
                       name="weather_sync_interval"
                       value="<?php p($_['weather_sync_interval']); ?>"
                       min="1"
                       max="24">
                <p class="hint"><?php p($l->t('How often to fetch weather data from Open-Meteo.')); ?></p>
            </div>
        </div>

        <!-- Locations -->
        <div class="settings-group">
            <h3><?php p($l->t('Supported Locations')); ?></h3>
            <p class="hint"><?php p($l->t('Weather data and predictions are available for these Portuguese locations:')); ?></p>
            <ul class="location-list">
                <?php foreach ($_['locations'] as $location): ?>
                    <li><?php p($location); ?></li>
                <?php endforeach; ?>
            </ul>
        </div>

        <div class="form-actions">
            <button type="submit" class="primary">
                <?php p($l->t('Save Settings')); ?>
            </button>
            <span class="save-status"></span>
        </div>
    </form>
</div>

<style>
#filantropia_solar_admin {
    max-width: 800px;
}

#filantropia_solar_admin .settings-group {
    margin-bottom: 24px;
    padding: 16px;
    background: var(--color-background-dark);
    border-radius: 8px;
}

#filantropia_solar_admin h3 {
    margin: 0 0 16px 0;
    color: #C4B552;
}

#filantropia_solar_admin .form-field {
    margin-bottom: 16px;
}

#filantropia_solar_admin label {
    display: block;
    margin-bottom: 4px;
    font-weight: 500;
}

#filantropia_solar_admin input[type="url"],
#filantropia_solar_admin input[type="number"] {
    width: 100%;
    max-width: 400px;
    padding: 8px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
}

#filantropia_solar_admin .hint {
    margin: 4px 0 0 0;
    font-size: 12px;
    color: var(--color-text-lighter);
}

#filantropia_solar_admin .status-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
}

#filantropia_solar_admin .status-healthy {
    background: #C4B552;
    color: #fff;
}

#filantropia_solar_admin .status-unreachable,
#filantropia_solar_admin .status-unknown {
    background: #e74c3c;
    color: #fff;
}

#filantropia_solar_admin .location-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    list-style: none;
    padding: 0;
    margin: 8px 0 0 0;
}

#filantropia_solar_admin .location-list li {
    padding: 4px 12px;
    background: #C4B552;
    color: #fff;
    border-radius: 12px;
    font-size: 13px;
}

#filantropia_solar_admin .form-actions {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-top: 24px;
}

#filantropia_solar_admin button.primary {
    background: #C4B552;
    border: none;
    color: #fff;
    padding: 10px 24px;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 500;
}

#filantropia_solar_admin button.primary:hover {
    background: #A89D3F;
}

#filantropia_solar_admin .save-status {
    font-size: 13px;
    color: var(--color-success);
}
</style>

<script>
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('filantropia_solar_settings');
    const status = form.querySelector('.save-status');

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        status.textContent = '<?php p($l->t('Saving...')); ?>';

        const formData = new FormData(form);
        const data = {
            ml_service_url: formData.get('ml_service_url'),
            default_grid_price: formData.get('default_grid_price'),
            weather_sync_interval: formData.get('weather_sync_interval'),
            predictions_enabled: form.querySelector('#predictions_enabled').checked ? 'true' : 'false',
        };

        try {
            const response = await fetch(OC.generateUrl('/apps/filantropia_solar/api/v1/admin/settings'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'requesttoken': OC.requestToken,
                },
                body: JSON.stringify(data),
            });

            if (response.ok) {
                status.textContent = '<?php p($l->t('Settings saved')); ?>';
                setTimeout(() => { status.textContent = ''; }, 3000);
            } else {
                status.textContent = '<?php p($l->t('Error saving settings')); ?>';
                status.style.color = 'var(--color-error)';
            }
        } catch (error) {
            status.textContent = '<?php p($l->t('Error saving settings')); ?>';
            status.style.color = 'var(--color-error)';
        }
    });
});
</script>
