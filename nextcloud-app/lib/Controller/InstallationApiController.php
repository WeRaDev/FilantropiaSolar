<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Controller;

use DateTime;
use OCA\FilantropiaSolar\AppInfo\Application;
use OCA\FilantropiaSolar\Db\Installation;
use OCA\FilantropiaSolar\Db\InstallationMapper;
use OCA\FilantropiaSolar\Service\StationLifecycle;
use OCP\AppFramework\ApiController;
use OCP\AppFramework\Db\DoesNotExistException;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\Attribute\NoAdminRequired;
use OCP\AppFramework\Http\Attribute\NoCSRFRequired;
use OCP\AppFramework\Http\JSONResponse;
use OCP\Files\IRootFolder;
use OCP\Http\Client\IClientService;
use OCP\IRequest;
use OCP\IUserSession;
use Psr\Log\LoggerInterface;

/**
 * Installation API Controller
 *
 * RESTful API for managing PV installations.
 */
class InstallationApiController extends ApiController
{
    /** ML Service URL (internal Docker network) */
    private const ML_SERVICE_URL = 'http://filantropia-ml:8501';

    public function __construct(
        IRequest $request,
        private readonly IUserSession $userSession,
        private readonly InstallationMapper $mapper,
        private readonly IClientService $clientService,
        private readonly IRootFolder $rootFolder,
        private readonly LoggerInterface $logger,
    ) {
        parent::__construct(Application::APP_ID, $request);
    }

    /**
     * List all installations (proxied from ML service with Mendeley data).
     *
     * GET /api/v1/installations
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function index(): JSONResponse
    {
        $mlInstallations = [];
        $dbInstallations = [];

        // 1. Dataset stations: MariaDB is the source of truth (imported Mendeley
        //    dataset). Fall back to the ML service only if the import has not run.
        try {
            $datasetRows = $this->mapper->findAllBySource('dataset');
            foreach ($datasetRows as $inst) {
                $mlInstallations[] = $this->datasetRowToArray($inst);
            }
        } catch (\Exception $dbEx) {
            $this->logger->error('Failed to read dataset installations from DB', ['exception' => $dbEx]);
        }

        if (count($mlInstallations) === 0) {
            try {
                $client = $this->clientService->newClient();
                $response = $client->get(self::ML_SERVICE_URL . '/data/installations');
                $data = json_decode($response->getBody(), true);

                if (isset($data['installations']) && is_array($data['installations'])) {
                    $mlInstallations = array_map(
                        fn($inst) => array_merge($inst, [
                            'status' => $this->calculateStatus($inst),
                            'source' => 'dataset',
                            'is_virtual' => false,
                        ]),
                        $data['installations']
                    );
                }
            } catch (\Exception $e) {
                $this->logger->error('Failed to fetch from ML service', ['exception' => $e]);
            }
        }

        // 2. Fetch user-created installations from DB
        $userId = $this->getUserId();
        if ($userId) {
            try {
                $userInstallations = $this->mapper->findAllByUser($userId);
                foreach ($userInstallations as $inst) {
                    $state = $inst->getLifecycleState() !== ''
                        ? $inst->getLifecycleState()
                        : StationLifecycle::VIRTUAL;
                    $dbInstallations[] = [
                        'id' => 'virtual_' . $inst->getId(),
                        'name' => $inst->getName(),
                        'location' => $inst->getLocation(),
                        'latitude' => $inst->getLatitude(),
                        'longitude' => $inst->getLongitude(),
                        'capacity_kwp' => (float) $inst->getCapacityKwp(),
                        'serial_number' => $inst->getSerialNumber(),
                        'is_virtual' => StationLifecycle::isVirtualFlag($state),
                        'source' => 'user',
                        'status' => 'warning',
                        'db_id' => $inst->getId(),
                        'lifecycle_state' => $state,
                        'soft_removed' => $inst->getSoftRemoved(),
                        'public_category' => StationLifecycle::publicCategory($state, $inst->getSoftRemoved()),
                        'is_public' => StationLifecycle::isPublic($state, $inst->getSoftRemoved()),
                    ];
                }
            } catch (\Exception $dbEx) {
                $this->logger->error('Failed to fetch user installations', ['exception' => $dbEx]);
            }
        }

        // 3. Merge: dataset + user installations
        $merged = array_merge($mlInstallations, $dbInstallations);

        return new JSONResponse([
            'success' => true,
            'installations' => $merged,
            'count' => count($merged),
        ]);
    }

    /**
     * Get single installation by ID (proxied from ML service).
     *
     * GET /api/v1/installations/{id}
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function show(string $id): JSONResponse
    {
        try {
            // Proxy to ML service
            $client = $this->clientService->newClient();
            $response = $client->get(self::ML_SERVICE_URL . '/data/installations/' . urlencode($id));
            $data = json_decode($response->getBody(), true);

            return new JSONResponse($data);
        } catch (\Exception $e) {
            $this->logger->error('Failed to fetch installation from ML service', ['id' => $id, 'exception' => $e]);
            return $this->errorResponse('Installation not found', Http::STATUS_NOT_FOUND);
        }
    }

    /**
     * Create new installation.
     *
     * POST /api/v1/installations
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function create(
        string $name,
        string $location,
        float $latitude,
        float $longitude,
        float $capacityKwp,
        ?string $serialNumber = null,
        ?float $connectionPowerKwn = null,
        ?float $gridPriceKwh = null,
        ?string $installationDate = null,
        bool $isVirtual = false,
    ): JSONResponse {
        $userId = $this->getUserId();
        if (!$userId) {
            return $this->errorResponse('Unauthorized', Http::STATUS_UNAUTHORIZED);
        }

        // Validate required fields
        if (empty($name) || empty($location)) {
            return $this->errorResponse('Name and location are required', Http::STATUS_BAD_REQUEST);
        }

        if ($capacityKwp <= 0) {
            return $this->errorResponse('Capacity must be positive', Http::STATUS_BAD_REQUEST);
        }

        try {
            $installation = new Installation();
            $installation->setUserId($userId);
            $installation->setName($name);
            $installation->setLocation($location);
            $installation->setLatitude((string) $latitude);
            $installation->setLongitude((string) $longitude);
            $installation->setCapacityKwp((string) $capacityKwp);
            $installation->setSerialNumber($serialNumber);
            $installation->setConnectionPowerKwn($connectionPowerKwn ? (string) $connectionPowerKwn : null);
            $installation->setGridPriceKwh((string) ($gridPriceKwh ?? Application::DEFAULT_GRID_PRICE));

            if ($installationDate) {
                $installation->setInstallationDate(new DateTime($installationDate));
            }
            $installation->setSource('user');
            // User-created stations are virtual until promoted via lifecycle API.
            $installation->applyLifecycleState(StationLifecycle::VIRTUAL);
            $installation->setSoftRemoved(false);

            $now = new DateTime();
            $installation->setCreatedAt($now);
            $installation->setUpdatedAt($now);

            $created = $this->mapper->insert($installation);

            $this->logger->info('Installation created', [
                'id' => $created->getId(),
                'name' => $name,
                'location' => $location,
            ]);

            return new JSONResponse([
                'success' => true,
                'installation' => $created,
                'message' => 'Installation created successfully',
            ], Http::STATUS_CREATED);

        } catch (\Exception $e) {
            $this->logger->error('Failed to create installation', ['exception' => $e]);
            return $this->errorResponse('Failed to create installation');
        }
    }

    /**
     * Update existing installation.
     *
     * PUT /api/v1/installations/{id}
     */
    #[NoAdminRequired]
    public function update(
        int $id,
        ?string $name = null,
        ?string $location = null,
        ?float $latitude = null,
        ?float $longitude = null,
        ?float $capacityKwp = null,
        ?string $serialNumber = null,
        ?float $connectionPowerKwn = null,
        ?float $gridPriceKwh = null,
        ?string $installationDate = null,
    ): JSONResponse {
        $userId = $this->getUserId();
        if (!$userId) {
            return $this->errorResponse('Unauthorized', Http::STATUS_UNAUTHORIZED);
        }

        try {
            $installation = $this->mapper->findByUser($id, $userId);

            // Update only provided fields
            if ($name !== null) {
                $installation->setName($name);
            }
            if ($location !== null) {
                $installation->setLocation($location);
            }
            if ($latitude !== null) {
                $installation->setLatitude((string) $latitude);
            }
            if ($longitude !== null) {
                $installation->setLongitude((string) $longitude);
            }
            if ($capacityKwp !== null) {
                if ($capacityKwp <= 0) {
                    return $this->errorResponse('Capacity must be positive', Http::STATUS_BAD_REQUEST);
                }
                $installation->setCapacityKwp((string) $capacityKwp);
            }
            if ($serialNumber !== null) {
                $installation->setSerialNumber($serialNumber);
            }
            if ($connectionPowerKwn !== null) {
                $installation->setConnectionPowerKwn((string) $connectionPowerKwn);
            }
            if ($gridPriceKwh !== null) {
                $installation->setGridPriceKwh((string) $gridPriceKwh);
            }
            if ($installationDate !== null) {
                $installation->setInstallationDate(new DateTime($installationDate));
            }

            $installation->setUpdatedAt(new DateTime());
            $updated = $this->mapper->update($installation);

            $this->logger->info('Installation updated', ['id' => $id]);

            return new JSONResponse([
                'success' => true,
                'installation' => $updated,
                'message' => 'Installation updated successfully',
            ]);

        } catch (DoesNotExistException $e) {
            return $this->errorResponse('Installation not found', Http::STATUS_NOT_FOUND);
        } catch (\Exception $e) {
            $this->logger->error('Failed to update installation', ['id' => $id, 'exception' => $e]);
            return $this->errorResponse('Failed to update installation');
        }
    }

    /**
     * Delete installation.
     *
     * DELETE /api/v1/installations/{id}
     */
    #[NoAdminRequired]
    public function destroy(int $id): JSONResponse
    {
        $userId = $this->getUserId();
        if (!$userId) {
            return $this->errorResponse('Unauthorized', Http::STATUS_UNAUTHORIZED);
        }

        try {
            $installation = $this->mapper->findByUser($id, $userId);
            $this->mapper->delete($installation);

            $this->logger->info('Installation deleted', ['id' => $id]);

            return new JSONResponse([
                'success' => true,
                'message' => 'Installation deleted successfully',
            ]);

        } catch (DoesNotExistException $e) {
            return $this->errorResponse('Installation not found', Http::STATUS_NOT_FOUND);
        } catch (\Exception $e) {
            $this->logger->error('Failed to delete installation', ['id' => $id, 'exception' => $e]);
            return $this->errorResponse('Failed to delete installation');
        }
    }

    /**
     * Restore all user installations (re-create previously deleted ones).
     *
     * POST /api/v1/installations/restore-dashboard
     */
    #[NoAdminRequired]
    public function restoreDashboard(): JSONResponse
    {
        $userId = $this->getUserId();
        if (!$userId) {
            return $this->errorResponse('Unauthorized', Http::STATUS_UNAUTHORIZED);
        }

        // For now, this is a no-op since we do hard deletes.
        // Future: if soft-delete is implemented, reset is_active=true here.
        return new JSONResponse([
            'success' => true,
            'message' => 'Dashboard restored',
        ]);
    }

    /**
     * Get installation statistics for popup display.
     *
     * GET /api/v1/installations/{id}/stats
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function stats(string $id): JSONResponse
    {
        try {
            // Proxy to ML service
            $client = $this->clientService->newClient();
            $response = $client->get(self::ML_SERVICE_URL . '/installations/' . urlencode($id) . '/stats');
            $data = json_decode($response->getBody(), true);

            return new JSONResponse($data);
        } catch (\Exception $e) {
            $this->logger->error('Failed to fetch installation stats from ML service', ['id' => $id, 'exception' => $e]);
            
            // Return fallback empty stats
            return new JSONResponse([
                'success' => false,
                'error' => 'Could not fetch statistics',
                'avg_yearly_production_kwh' => 0,
                'efficiency_kwh_kwp' => 0,
                'total_days' => 0,
            ]);
        }
    }

    /**
     * Export installation data to Nextcloud Files.
     *
     * POST /api/v1/installations/{id}/export
     */
    #[NoAdminRequired]
    public function export(string $id): JSONResponse
    {
        $userId = $this->getUserId();
        if (!$userId) {
            return $this->errorResponse('Unauthorized', Http::STATUS_UNAUTHORIZED);
        }

        try {
            // Fetch installation data from ML service
            $client = $this->clientService->newClient();
            $response = $client->get(self::ML_SERVICE_URL . '/data/installations/' . urlencode($id));
            $instData = json_decode($response->getBody(), true);

            if (!$instData || !isset($instData['installation'])) {
                return $this->errorResponse('Installation not found', Http::STATUS_NOT_FOUND);
            }

            $inst = $instData['installation'];
            $instName = preg_replace('/[^a-zA-Z0-9_-]/', '_', $inst['name'] ?? $id);

            // Create folder structure
            $userFolder = $this->rootFolder->getUserFolder($userId);
            $basePath = 'FilantropiaSolar Data';
            $instPath = $basePath . '/' . $instName;

            // Ensure base folder exists
            if (!$userFolder->nodeExists($basePath)) {
                $userFolder->newFolder($basePath);
            }

            // Ensure installation folder exists
            if (!$userFolder->nodeExists($instPath)) {
                $userFolder->newFolder($instPath);
            }

            $instFolder = $userFolder->get($instPath);

            // Export metadata.json
            $metadata = json_encode($inst, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
            if ($instFolder->nodeExists('metadata.json')) {
                $instFolder->get('metadata.json')->putContent($metadata);
            } else {
                $instFolder->newFile('metadata.json', $metadata);
            }

            // Try to export readings if available
            try {
                $readingsResponse = $client->get(self::ML_SERVICE_URL . '/data/installations/' . urlencode($id) . '/readings');
                $readingsData = json_decode($readingsResponse->getBody(), true);

                if (!empty($readingsData['readings'])) {
                    // Create CSV
                    $csv = "timestamp,production_kwh,temperature,humidity,cloud_cover\n";
                    foreach ($readingsData['readings'] as $r) {
                        $csv .= sprintf(
                            "%s,%.2f,%.1f,%.1f,%.1f\n",
                            $r['timestamp'] ?? '',
                            $r['production_kwh'] ?? 0,
                            $r['temperature'] ?? 0,
                            $r['humidity'] ?? 0,
                            $r['cloud_cover'] ?? 0
                        );
                    }

                    if ($instFolder->nodeExists('readings.csv')) {
                        $instFolder->get('readings.csv')->putContent($csv);
                    } else {
                        $instFolder->newFile('readings.csv', $csv);
                    }
                }
            } catch (\Exception $e) {
                // Readings export is optional
                $this->logger->info('No readings to export for installation', ['id' => $id]);
            }

            return new JSONResponse([
                'success' => true,
                'message' => 'Data exported successfully',
                'path' => $instPath,
                'files' => ['metadata.json', 'readings.csv'],
            ]);

        } catch (\Exception $e) {
            $this->logger->error('Failed to export installation data', ['id' => $id, 'exception' => $e]);
            return $this->errorResponse('Export failed: ' . $e->getMessage());
        }
    }

    /**
     * Map a dataset Installation entity to the API array shape (ML-compatible).
     */
    private function datasetRowToArray(Installation $inst): array
    {
        $toDate = $inst->getToDate()?->format('Y-m-d');
        $statusMeta = [
            'to_date' => $toDate,
            'error_flag' => $inst->getErrorFlag(),
        ];

        $state = $inst->getLifecycleState() !== ''
            ? $inst->getLifecycleState()
            : StationLifecycle::RUNNING;

        return [
            'id' => $inst->getInstallationId(),
            'serial_number' => $inst->getSerialNumber(),
            'name' => $inst->getName(),
            'location' => $inst->getLocation(),
            'nearest_location' => $inst->getNearestLocation(),
            'latitude' => (float) $inst->getLatitude(),
            'longitude' => (float) $inst->getLongitude(),
            'capacity_kwp' => (float) $inst->getCapacityKwp(),
            'connection_power_kwn' => $inst->getConnectionPowerKwn() !== null ? (float) $inst->getConnectionPowerKwn() : null,
            'from_date' => $inst->getFromDate()?->format('Y-m-d'),
            'to_date' => $toDate,
            'status' => $this->calculateStatus($statusMeta),
            'source' => 'dataset',
            'is_virtual' => StationLifecycle::isVirtualFlag($state),
            'db_id' => $inst->getId(),
            'lifecycle_state' => $state,
            'soft_removed' => $inst->getSoftRemoved(),
            'public_category' => StationLifecycle::publicCategory($state, $inst->getSoftRemoved()),
            'is_public' => StationLifecycle::isPublic($state, $inst->getSoftRemoved()),
            'odoo_lead_id' => $inst->getOdooLeadId(),
            'installed_at' => $inst->getInstalledAt()?->format('c'),
        ];
    }

    /**
     * Calculate installation status based on data recency.
     *
     * - Active: to_date is today (has current data)
     * - Warning: no historical data OR error_flag is set
     * - Offline: has historical data but to_date is in the past
     */
    private function calculateStatus(array $inst): string
    {
        $today = (new DateTime())->format('Y-m-d');

        // Check error flag first
        if (isset($inst['error_flag']) && $inst['error_flag']) {
            return 'warning';
        }

        // No data = warning
        if (empty($inst['to_date'])) {
            return 'warning';
        }

        // Extract date part (handles both 'Y-m-d' and 'Y-m-dTH:i:s' formats)
        $toDate = substr($inst['to_date'], 0, 10);

        // Compare with today
        if ($toDate === $today) {
            return 'active';
        }

        return 'offline';
    }

    /**
     * Get current user ID.
     */
    private function getUserId(): ?string
    {
        return $this->userSession->getUser()?->getUID();
    }

    /**
     * Create error response.
     */
    private function errorResponse(string $message, int $status = Http::STATUS_INTERNAL_SERVER_ERROR): JSONResponse
    {
        return new JSONResponse([
            'success' => false,
            'error' => $message,
        ], $status);
    }
}
