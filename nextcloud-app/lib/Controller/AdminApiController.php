<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Controller;

use DateTime;
use OCA\FilantropiaSolar\AppInfo\Application;
use OCA\FilantropiaSolar\Db\Installation;
use OCA\FilantropiaSolar\Db\InstallationMapper;
use OCA\FilantropiaSolar\Service\StationLifecycle;
use OCP\AppFramework\ApiController;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\Attribute\NoCSRFRequired;
use OCP\AppFramework\Http\JSONResponse;
use OCP\Http\Client\IClientService;
use OCP\IConfig;
use OCP\IRequest;
use Psr\Log\LoggerInterface;

/**
 * Admin API Controller.
 *
 * Admin-only endpoints for:
 * - global dataset station management (CRUD)
 * - dataset re-import
 * - ML control actions proxied through Nextcloud
 * - app admin settings (ML URL)
 */
class AdminApiController extends ApiController
{
    private const DEFAULT_ML_SERVICE_URL = 'http://filantropia-ml:8501';

    public function __construct(
        IRequest $request,
        private readonly InstallationMapper $mapper,
        private readonly IClientService $clientService,
        private readonly IConfig $config,
        private readonly LoggerInterface $logger,
    ) {
        parent::__construct(Application::APP_ID, $request);
    }

    /**
     * Bootstrap payload for the admin UI.
     *
     * GET /api/v1/admin/bootstrap
     */
    #[NoCSRFRequired]
    public function bootstrap(): JSONResponse
    {
        return new JSONResponse([
            'success' => true,
            'settings' => [
                'ml_service_url' => $this->getMlServiceUrl(),
            ],
            'counts' => [
                'dataset_stations' => $this->mapper->countBySource('dataset'),
                'user_stations' => $this->mapper->countBySource('user'),
            ],
        ]);
    }

    /**
     * List global dataset stations.
     *
     * GET /api/v1/admin/stations
     */
    #[NoCSRFRequired]
    public function stations(): JSONResponse
    {
        $rows = $this->mapper->findAllBySource('dataset');
        $stations = array_map(fn(Installation $row): array => $this->toStationArray($row), $rows);

        return new JSONResponse([
            'success' => true,
            'stations' => $stations,
            'count' => count($stations),
        ]);
    }

    /**
     * Create a global dataset station.
     *
     * POST /api/v1/admin/stations
     */
    #[NoCSRFRequired]
    public function createStation(): JSONResponse
    {
        $payload = $this->request->getParams();
        $validation = $this->validateStationPayload($payload);
        if ($validation !== null) {
            return $validation;
        }

        try {
            $station = new Installation();
            $this->hydrateStation($station, $payload);
            $now = new DateTime();
            $station->setCreatedAt($now);
            $station->setUpdatedAt($now);

            $created = $this->mapper->insert($station);

            return new JSONResponse([
                'success' => true,
                'station' => $this->toStationArray($created),
                'message' => 'Global station created',
            ], Http::STATUS_CREATED);
        } catch (\Throwable $e) {
            $this->logger->error('Failed to create global station', ['exception' => $e]);
            return $this->error('Failed to create station');
        }
    }

    /**
     * Update a global dataset station.
     *
     * PUT /api/v1/admin/stations/{id}
     */
    #[NoCSRFRequired]
    public function updateStation(int $id): JSONResponse
    {
        $payload = $this->request->getParams();
        $validation = $this->validateStationPayload($payload, false);
        if ($validation !== null) {
            return $validation;
        }

        try {
            $station = $this->mapper->findDatasetById($id);
            if ($station === null) {
                return $this->error('Dataset station not found', Http::STATUS_NOT_FOUND);
            }

            $this->hydrateStation($station, $payload, false);
            $station->setUpdatedAt(new DateTime());
            $updated = $this->mapper->update($station);

            return new JSONResponse([
                'success' => true,
                'station' => $this->toStationArray($updated),
                'message' => 'Global station updated',
            ]);
        } catch (\Throwable $e) {
            $this->logger->error('Failed to update global station', ['id' => $id, 'exception' => $e]);
            return $this->error('Failed to update station');
        }
    }

    /**
     * Delete a global dataset station.
     *
     * DELETE /api/v1/admin/stations/{id}
     */
    #[NoCSRFRequired]
    public function deleteStation(int $id): JSONResponse
    {
        try {
            $station = $this->mapper->findDatasetById($id);
            if ($station === null) {
                return $this->error('Dataset station not found', Http::STATUS_NOT_FOUND);
            }

            $this->mapper->delete($station);

            return new JSONResponse([
                'success' => true,
                'message' => 'Global station deleted',
            ]);
        } catch (\Throwable $e) {
            $this->logger->error('Failed to delete global station', ['id' => $id, 'exception' => $e]);
            return $this->error('Failed to delete station');
        }
    }

    /**
     * Re-import dataset stations from ML metadata endpoint.
     *
     * POST /api/v1/admin/dataset/reimport
     */
    #[NoCSRFRequired]
    public function reimportDataset(): JSONResponse
    {
        try {
            $result = $this->importDatasetMetadata();
            return new JSONResponse([
                'success' => true,
                'result' => $result,
                'message' => 'Dataset re-import completed',
            ]);
        } catch (\Throwable $e) {
            $this->logger->error('Dataset re-import failed', ['exception' => $e]);
            return $this->error('Dataset re-import failed: ' . $e->getMessage(), Http::STATUS_BAD_GATEWAY);
        }
    }

    /**
     * GET /api/v1/admin/ml/cache
     */
    #[NoCSRFRequired]
    public function getCacheStatus(): JSONResponse
    {
        return $this->proxyMlGet('/admin/cache');
    }

    /**
     * POST /api/v1/admin/ml/cache/clear
     */
    #[NoCSRFRequired]
    public function clearCache(): JSONResponse
    {
        return $this->proxyMlPost('/admin/cache/clear', []);
    }

    /**
     * GET /api/v1/admin/ml/model-info
     */
    #[NoCSRFRequired]
    public function getModelInfo(): JSONResponse
    {
        return $this->proxyMlGet('/model-info');
    }

    /**
     * GET /api/v1/admin/ml/model/{id}
     */
    #[NoCSRFRequired]
    public function getModelDetails(string $id): JSONResponse
    {
        return $this->proxyMlGet('/admin/model/' . rawurlencode($id));
    }

    /**
     * POST /api/v1/admin/ml/train
     */
    #[NoCSRFRequired]
    public function trainAll(): JSONResponse
    {
        return $this->proxyMlPost('/train', []);
    }

    /**
     * POST /api/v1/admin/ml/train/{id}
     */
    #[NoCSRFRequired]
    public function trainStation(string $id): JSONResponse
    {
        return $this->proxyMlPost('/train/' . rawurlencode($id), []);
    }

    /**
     * GET /api/v1/admin/settings
     */
    #[NoCSRFRequired]
    public function getSettings(): JSONResponse
    {
        return new JSONResponse([
            'success' => true,
            'settings' => [
                'ml_service_url' => $this->getMlServiceUrl(),
            ],
        ]);
    }

    /**
     * POST /api/v1/admin/settings
     */
    #[NoCSRFRequired]
    public function saveSettings(): JSONResponse
    {
        $mlServiceUrl = trim((string) $this->request->getParam('ml_service_url', ''));
        if ($mlServiceUrl === '') {
            return $this->error('ml_service_url is required', Http::STATUS_BAD_REQUEST);
        }

        $this->config->setAppValue(Application::APP_ID, 'ml_service_url', rtrim($mlServiceUrl, '/'));

        return new JSONResponse([
            'success' => true,
            'settings' => [
                'ml_service_url' => $this->getMlServiceUrl(),
            ],
            'message' => 'Admin settings saved',
        ]);
    }

    private function validateStationPayload(array $payload, bool $requireAll = true): ?JSONResponse
    {
        $required = ['name', 'location', 'latitude', 'longitude', 'capacity_kwp', 'serial_number'];
        if ($requireAll) {
            foreach ($required as $field) {
                if (!isset($payload[$field]) || trim((string) $payload[$field]) === '') {
                    return $this->error(sprintf('%s is required', $field), Http::STATUS_BAD_REQUEST);
                }
            }
        }

        if (isset($payload['capacity_kwp']) && (float) $payload['capacity_kwp'] <= 0) {
            return $this->error('capacity_kwp must be positive', Http::STATUS_BAD_REQUEST);
        }

        return null;
    }

    private function hydrateStation(Installation $station, array $payload, bool $create = true): void
    {
        if ($create || array_key_exists('name', $payload)) {
            $station->setName((string) ($payload['name'] ?? $station->getName()));
        }
        if ($create || array_key_exists('location', $payload)) {
            $station->setLocation((string) ($payload['location'] ?? $station->getLocation()));
            $station->setNearestLocation((string) ($payload['location'] ?? $station->getNearestLocation()));
        }
        if ($create || array_key_exists('latitude', $payload)) {
            $station->setLatitude((string) ($payload['latitude'] ?? $station->getLatitude()));
        }
        if ($create || array_key_exists('longitude', $payload)) {
            $station->setLongitude((string) ($payload['longitude'] ?? $station->getLongitude()));
        }
        if ($create || array_key_exists('capacity_kwp', $payload)) {
            $station->setCapacityKwp((string) ($payload['capacity_kwp'] ?? $station->getCapacityKwp()));
        }
        if ($create || array_key_exists('serial_number', $payload)) {
            $station->setSerialNumber((string) ($payload['serial_number'] ?? $station->getSerialNumber()));
        }
        if (array_key_exists('connection_power_kwn', $payload)) {
            $station->setConnectionPowerKwn($payload['connection_power_kwn'] !== null ? (string) $payload['connection_power_kwn'] : null);
        }
        if (array_key_exists('from_date', $payload) && !empty($payload['from_date'])) {
            $station->setFromDate(new DateTime((string) $payload['from_date']));
        }
        if (array_key_exists('to_date', $payload) && !empty($payload['to_date'])) {
            $station->setToDate(new DateTime((string) $payload['to_date']));
        }
        if (array_key_exists('error_flag', $payload)) {
            $station->setErrorFlag((bool) $payload['error_flag']);
        }

        $station->setUserId(null);
        $station->setSource('dataset');
        $station->setIsVirtual(false);
        $station->setGridPriceKwh((string) Application::DEFAULT_GRID_PRICE);
        if ($create) {
            $station->applyLifecycleState(StationLifecycle::RUNNING);
            $station->setSoftRemoved(false);
        }
    }

    private function toStationArray(Installation $station): array
    {
        $state = $station->getLifecycleState() !== ''
            ? $station->getLifecycleState()
            : StationLifecycle::defaultStateForNew($station->getIsVirtual(), $station->getSource());

        return [
            'id' => $station->getId(),
            'installation_id' => $station->getInstallationId(),
            'name' => $station->getName(),
            'serial_number' => $station->getSerialNumber(),
            'location' => $station->getLocation(),
            'latitude' => (float) $station->getLatitude(),
            'longitude' => (float) $station->getLongitude(),
            'capacity_kwp' => (float) $station->getCapacityKwp(),
            'connection_power_kwn' => $station->getConnectionPowerKwn() !== null ? (float) $station->getConnectionPowerKwn() : null,
            'from_date' => $station->getFromDate()?->format('Y-m-d'),
            'to_date' => $station->getToDate()?->format('Y-m-d'),
            'error_flag' => $station->getErrorFlag(),
            'source' => $station->getSource(),
            'lifecycle_state' => $state,
            'soft_removed' => $station->getSoftRemoved(),
            'odoo_lead_id' => $station->getOdooLeadId(),
            'installed_at' => $station->getInstalledAt()?->format('c'),
            'is_public' => StationLifecycle::isPublic($state, $station->getSoftRemoved()),
            'public_category' => StationLifecycle::publicCategory($state, $station->getSoftRemoved()),
            'is_virtual' => StationLifecycle::isVirtualFlag($state),
        ];
    }

    private function importDatasetMetadata(): array
    {
        $client = $this->clientService->newClient();
        $response = $client->get($this->getMlServiceUrl() . '/data/installations', ['timeout' => 60]);
        $payload = json_decode((string) $response->getBody(), true);
        $installations = $payload['installations'] ?? [];
        if (!is_array($installations)) {
            throw new \RuntimeException('Invalid dataset payload from ML service');
        }

        $created = 0;
        $updated = 0;
        foreach ($installations as $inst) {
            $serial = (string) ($inst['serial_number'] ?? $inst['id'] ?? '');
            if ($serial === '') {
                continue;
            }

            $existing = $this->mapper->findDatasetBySerial($serial);
            $entity = $existing ?? new Installation();
            $this->hydrateStation($entity, [
                'name' => (string) ($inst['name'] ?? ('PV Plant ' . $serial)),
                'location' => (string) ($inst['location'] ?? 'Unknown'),
                'latitude' => (string) ($inst['latitude'] ?? '0'),
                'longitude' => (string) ($inst['longitude'] ?? '0'),
                'capacity_kwp' => (string) ($inst['capacity_kwp'] ?? '0'),
                'serial_number' => $serial,
                'connection_power_kwn' => isset($inst['connection_power_kwn']) ? (string) $inst['connection_power_kwn'] : null,
                'from_date' => $inst['from_date'] ?? null,
                'to_date' => $inst['to_date'] ?? null,
                'error_flag' => (bool) ($inst['error_flag'] ?? false),
            ]);

            $now = new DateTime();
            if ($existing !== null) {
                $entity->setUpdatedAt($now);
                $this->mapper->update($entity);
                $updated++;
            } else {
                $entity->setCreatedAt($now);
                $entity->setUpdatedAt($now);
                $this->mapper->insert($entity);
                $created++;
            }
        }

        return ['created' => $created, 'updated' => $updated, 'total' => count($installations)];
    }

    private function getMlServiceUrl(): string
    {
        return rtrim(
            $this->config->getAppValue(
                Application::APP_ID,
                'ml_service_url',
                self::DEFAULT_ML_SERVICE_URL
            ),
            '/'
        );
    }

    private function proxyMlGet(string $path): JSONResponse
    {
        try {
            $client = $this->clientService->newClient();
            $response = $client->get($this->getMlServiceUrl() . $path, ['timeout' => 60]);
            $payload = json_decode((string) $response->getBody(), true);
            return new JSONResponse($payload ?? ['success' => false, 'error' => 'Invalid ML response']);
        } catch (\Throwable $e) {
            $this->logger->error('ML GET proxy failed', ['path' => $path, 'exception' => $e]);
            return $this->error('ML service request failed', Http::STATUS_BAD_GATEWAY);
        }
    }

    private function proxyMlPost(string $path, array $body): JSONResponse
    {
        try {
            $client = $this->clientService->newClient();
            $response = $client->post($this->getMlServiceUrl() . $path, [
                'headers' => ['Content-Type' => 'application/json'],
                'body' => json_encode($body),
                'timeout' => 120,
            ]);
            $payload = json_decode((string) $response->getBody(), true);
            return new JSONResponse($payload ?? ['success' => false, 'error' => 'Invalid ML response']);
        } catch (\Throwable $e) {
            $this->logger->error('ML POST proxy failed', ['path' => $path, 'exception' => $e]);
            return $this->error('ML service request failed', Http::STATUS_BAD_GATEWAY);
        }
    }

    private function error(string $message, int $status = Http::STATUS_INTERNAL_SERVER_ERROR): JSONResponse
    {
        return new JSONResponse(['success' => false, 'error' => $message], $status);
    }
}
