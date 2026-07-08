<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Settings;

use OCA\FilantropiaSolar\AppInfo\Application;
use OCA\FilantropiaSolar\Service\PredictionService;
use OCP\AppFramework\Http\TemplateResponse;
use OCP\IConfig;
use OCP\IL10N;
use OCP\Settings\ISettings;

/**
 * Admin Settings
 *
 * Provides the admin settings form for FilantropiaSolar configuration.
 */
class AdminSettings implements ISettings
{
    public function __construct(
        private readonly IConfig $config,
        private readonly IL10N $l10n,
        private readonly PredictionService $predictionService,
    ) {
    }

    /**
     * Get the settings form.
     */
    public function getForm(): TemplateResponse
    {
        $mlServiceUrl = $this->config->getAppValue(
            Application::APP_ID,
            'ml_service_url',
            'http://filantropia-ml:8501'
        );

        $defaultGridPrice = $this->config->getAppValue(
            Application::APP_ID,
            'default_grid_price',
            (string) Application::DEFAULT_GRID_PRICE
        );

        $weatherSyncInterval = $this->config->getAppValue(
            Application::APP_ID,
            'weather_sync_interval',
            '3'
        );

        $predictionsEnabled = $this->config->getAppValue(
            Application::APP_ID,
            'predictions_enabled',
            'true'
        );

        // Get ML service status
        $mlStatus = $this->predictionService->getServiceStatus();

        return new TemplateResponse(
            Application::APP_ID,
            'admin',
            [
                'ml_service_url' => $mlServiceUrl,
                'default_grid_price' => $defaultGridPrice,
                'weather_sync_interval' => $weatherSyncInterval,
                'predictions_enabled' => $predictionsEnabled === 'true',
                'ml_status' => $mlStatus,
                'locations' => array_keys(Application::LOCATION_COORDS),
            ],
            ''
        );
    }

    /**
     * Get the section ID.
     */
    public function getSection(): string
    {
        return Application::APP_ID;
    }

    /**
     * Get the priority (lower = higher in section).
     */
    public function getPriority(): int
    {
        return 10;
    }
}
