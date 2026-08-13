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
        ['name' => 'installation_api#exportAnalysis', 'url' => '/api/v1/installations/{id}/export-analysis', 'verb' => 'POST'],
        ['name' => 'installation_api#importFromFiles', 'url' => '/api/v1/installations/{id}/import-from-files', 'verb' => 'POST'],
        ['name' => 'installation_api#restoreDashboard', 'url' => '/api/v1/installations/restore-dashboard', 'verb' => 'POST'],
        ['name' => 'installation_api#stats', 'url' => '/api/v1/installations/{id}/stats', 'verb' => 'GET'],
        ['name' => 'installation_api#promotePlanned', 'url' => '/api/v1/installations/{id}/promote-planned', 'verb' => 'POST'],
        ['name' => 'installation_api#markInstalled', 'url' => '/api/v1/installations/{id}/mark-installed', 'verb' => 'POST'],
        ['name' => 'installation_api#softRemove', 'url' => '/api/v1/installations/{id}/soft-remove', 'verb' => 'POST'],
        ['name' => 'installation_api#setLifecycle', 'url' => '/api/v1/installations/{id}/set-lifecycle', 'verb' => 'POST'],

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

        // Public read-only API (token-authed) for external consumers (Odoo)
        ['name' => 'public_api#stations', 'url' => '/api/public/v1/stations', 'verb' => 'GET'],
        ['name' => 'public_api#dashboard', 'url' => '/api/public/v1/dashboard', 'verb' => 'GET'],
        ['name' => 'public_api#estimate', 'url' => '/api/public/v1/estimate', 'verb' => 'POST'],

        // Lifecycle API (token-authed) for Odoo CRM glue (MVP-2)
        ['name' => 'lifecycle_api#createVirtual', 'url' => '/api/lifecycle/v1/stations/virtual', 'verb' => 'POST'],
        ['name' => 'lifecycle_api#promotePlanned', 'url' => '/api/lifecycle/v1/stations/{installationId}/promote-planned', 'verb' => 'POST'],
        ['name' => 'lifecycle_api#markInstalled', 'url' => '/api/lifecycle/v1/stations/{installationId}/mark-installed', 'verb' => 'POST'],
        ['name' => 'lifecycle_api#softRemove', 'url' => '/api/lifecycle/v1/stations/{installationId}/soft-remove', 'verb' => 'POST'],
        ['name' => 'lifecycle_api#bindLead', 'url' => '/api/lifecycle/v1/stations/{installationId}/bind-lead', 'verb' => 'POST'],
        ['name' => 'lifecycle_api#setLifecycle', 'url' => '/api/lifecycle/v1/stations/{installationId}/set-lifecycle', 'verb' => 'POST'],
        ['name' => 'lifecycle_api#updateProfile', 'url' => '/api/lifecycle/v1/stations/{installationId}/profile', 'verb' => 'POST'],
        ['name' => 'lifecycle_api#index', 'url' => '/api/lifecycle/v1/stations', 'verb' => 'GET'],
        ['name' => 'lifecycle_api#show', 'url' => '/api/lifecycle/v1/stations/{installationId}', 'verb' => 'GET'],

        // Admin API (admin-only): global dataset stations + ML controls + admin settings
        ['name' => 'admin_api#bootstrap', 'url' => '/api/v1/admin/bootstrap', 'verb' => 'GET'],
        ['name' => 'admin_api#stations', 'url' => '/api/v1/admin/stations', 'verb' => 'GET'],
        ['name' => 'admin_api#createStation', 'url' => '/api/v1/admin/stations', 'verb' => 'POST'],
        ['name' => 'admin_api#updateStation', 'url' => '/api/v1/admin/stations/{id}', 'verb' => 'PUT'],
        ['name' => 'admin_api#deleteStation', 'url' => '/api/v1/admin/stations/{id}', 'verb' => 'DELETE'],
        ['name' => 'admin_api#promotePlanned', 'url' => '/api/v1/admin/stations/{installationId}/promote-planned', 'verb' => 'POST'],
        ['name' => 'admin_api#markInstalled', 'url' => '/api/v1/admin/stations/{installationId}/mark-installed', 'verb' => 'POST'],
        ['name' => 'admin_api#softRemove', 'url' => '/api/v1/admin/stations/{installationId}/soft-remove', 'verb' => 'POST'],
        ['name' => 'admin_api#reimportDataset', 'url' => '/api/v1/admin/dataset/reimport', 'verb' => 'POST'],
        ['name' => 'admin_api#getCacheStatus', 'url' => '/api/v1/admin/ml/cache', 'verb' => 'GET'],
        ['name' => 'admin_api#clearCache', 'url' => '/api/v1/admin/ml/cache/clear', 'verb' => 'POST'],
        ['name' => 'admin_api#getModelInfo', 'url' => '/api/v1/admin/ml/model-info', 'verb' => 'GET'],
        ['name' => 'admin_api#getModelDetails', 'url' => '/api/v1/admin/ml/model/{id}', 'verb' => 'GET'],
        ['name' => 'admin_api#trainAll', 'url' => '/api/v1/admin/ml/train', 'verb' => 'POST'],
        ['name' => 'admin_api#trainStation', 'url' => '/api/v1/admin/ml/train/{id}', 'verb' => 'POST'],
        ['name' => 'admin_api#getSettings', 'url' => '/api/v1/admin/settings', 'verb' => 'GET'],
        ['name' => 'admin_api#saveSettings', 'url' => '/api/v1/admin/settings', 'verb' => 'POST'],
    ],
];
