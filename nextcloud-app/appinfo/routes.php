<?php

declare(strict_types=1);

/**
 * FilantropiaSolar - Nextcloud App Routes
 *
 * Defines all page and API routes for the application.
 */

return [
    'routes' => [
        // Page routes
        ['name' => 'page#index', 'url' => '/', 'verb' => 'GET'],
        ['name' => 'page#detail', 'url' => '/installation/{id}', 'verb' => 'GET'],
        ['name' => 'page#dashboard', 'url' => '/dashboard', 'verb' => 'GET'],

        // Installation API - Full CRUD
        ['name' => 'installation_api#index', 'url' => '/api/v1/installations', 'verb' => 'GET'],
        ['name' => 'installation_api#show', 'url' => '/api/v1/installations/{id}', 'verb' => 'GET'],
        ['name' => 'installation_api#create', 'url' => '/api/v1/installations', 'verb' => 'POST'],
        ['name' => 'installation_api#update', 'url' => '/api/v1/installations/{id}', 'verb' => 'PUT'],
        ['name' => 'installation_api#destroy', 'url' => '/api/v1/installations/{id}', 'verb' => 'DELETE'],
        ['name' => 'installation_api#export', 'url' => '/api/v1/installations/{id}/export', 'verb' => 'POST'],
        ['name' => 'installation_api#restoreDashboard', 'url' => '/api/v1/installations/restore-dashboard', 'verb' => 'POST'],
        ['name' => 'installation_api#stats', 'url' => '/api/v1/installations/{id}/stats', 'verb' => 'GET'],

        // Energy API
        ['name' => 'energy_api#readings', 'url' => '/api/v1/installations/{id}/readings', 'verb' => 'GET'],
        ['name' => 'energy_api#stats', 'url' => '/api/v1/installations/{id}/stats', 'verb' => 'GET'],
        ['name' => 'energy_api#import', 'url' => '/api/v1/installations/{id}/import', 'verb' => 'POST'],

        // Dashboard API
        ['name' => 'dashboard_api#overview', 'url' => '/api/v1/dashboard', 'verb' => 'GET'],
        ['name' => 'dashboard_api#savings', 'url' => '/api/v1/dashboard/savings', 'verb' => 'GET'],

        // Prediction API
        ['name' => 'prediction_api#forecast', 'url' => '/api/v1/installations/{id}/forecast', 'verb' => 'GET'],
        ['name' => 'prediction_api#trigger', 'url' => '/api/v1/installations/{id}/predict', 'verb' => 'POST'],
        ['name' => 'prediction_api#period', 'url' => '/api/v1/predict/period', 'verb' => 'POST'],
    ],
];
