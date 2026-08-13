<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Controller;

use DateTime;
use OCA\FilantropiaSolar\AppInfo\Application;
use OCA\FilantropiaSolar\Db\Installation;
use OCA\FilantropiaSolar\Db\EnergyReadingMapper;
use OCA\FilantropiaSolar\Db\InstallationMapper;
use OCA\FilantropiaSolar\Service\OdooLifecycleMirror;
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
        private readonly EnergyReadingMapper $readingMapper,
        private readonly IClientService $clientService,
        private readonly IRootFolder $rootFolder,
        private readonly LoggerInterface $logger,
        private readonly OdooLifecycleMirror $odooMirror,
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
        // M0: ops list is fleet/user/crm only — never Mendeley training corpus.
        $includeDataset = filter_var(
            $this->request->getParam('include_dataset', '0'),
            FILTER_VALIDATE_BOOLEAN,
        );

        $rows = [];
        try {
            if ($includeDataset) {
                $rows = $this->mapper->findAll();
            } else {
                $rows = $this->mapper->findOpsStations();
            }
        } catch (\Exception $e) {
            $this->logger->error('Failed to list ops installations', ['exception' => $e]);
            return $this->errorResponse('Failed to list installations');
        }

        $installations = [];
        foreach ($rows as $inst) {
            $source = $inst->getSource() ?: 'user';
            if ($source === 'dataset') {
                $payload = $this->datasetRowToArray($inst);
            } else {
                $payload = $this->userOrCrmRowToArray($inst, $source === '' ? 'user' : $source);
            }
            $installations[] = $this->attachSeriesStats($payload, (int) $inst->getId());
        }

        return new JSONResponse([
            'success' => true,
            'installations' => $installations,
            'count' => count($installations),
            'includes_dataset' => $includeDataset,
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
            $this->odooMirror->notify($created);

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
    #[NoCSRFRequired]
    public function update(string $id): JSONResponse
    {
        $userId = $this->getUserId();
        if (!$userId) {
            return $this->errorResponse('Unauthorized', Http::STATUS_UNAUTHORIZED);
        }

        $installation = $this->resolveStation($id);
        if ($installation === null) {
            return $this->errorResponse('Installation not found', Http::STATUS_NOT_FOUND);
        }

        $payload = $this->request->getParams();
        try {
            if (array_key_exists('name', $payload) && $payload['name'] !== null && $payload['name'] !== '') {
                $installation->setName((string) $payload['name']);
            }
            if (array_key_exists('location', $payload) && $payload['location'] !== null && $payload['location'] !== '') {
                $installation->setLocation((string) $payload['location']);
            }
            if (array_key_exists('latitude', $payload) && $payload['latitude'] !== null && $payload['latitude'] !== '') {
                $installation->setLatitude((string) $payload['latitude']);
            }
            if (array_key_exists('longitude', $payload) && $payload['longitude'] !== null && $payload['longitude'] !== '') {
                $installation->setLongitude((string) $payload['longitude']);
            }
            if (array_key_exists('capacity_kwp', $payload) || array_key_exists('capacityKwp', $payload)) {
                $cap = (float) ($payload['capacity_kwp'] ?? $payload['capacityKwp']);
                if ($cap <= 0) {
                    return $this->errorResponse('Capacity must be positive', Http::STATUS_BAD_REQUEST);
                }
                $installation->setCapacityKwp((string) $cap);
            }
            if (array_key_exists('grid_price_kwh', $payload) || array_key_exists('gridPriceKwh', $payload)) {
                $price = $payload['grid_price_kwh'] ?? $payload['gridPriceKwh'];
                if ($price !== null && $price !== '') {
                    $installation->setGridPriceKwh((string) $price);
                }
            }
            if (array_key_exists('website', $payload)) {
                $w = $payload['website'];
                $installation->setWebsite($w !== null && $w !== '' ? (string) $w : null);
            }
            if (array_key_exists('short_description', $payload) || array_key_exists('shortDescription', $payload)) {
                $d = $payload['short_description'] ?? $payload['shortDescription'];
                $installation->setShortDescription($d !== null && $d !== '' ? (string) $d : null);
            }
            if (array_key_exists('installation_date', $payload) || array_key_exists('effective_date', $payload) || array_key_exists('installationDate', $payload)) {
                $raw = $payload['installation_date'] ?? $payload['effective_date'] ?? $payload['installationDate'];
                if ($raw) {
                    $installation->setInstallationDate(new DateTime((string) $raw));
                }
            }

            $installation->setUpdatedAt(new DateTime());
            $updated = $this->mapper->update($installation);

            return new JSONResponse([
                'success' => true,
                'installation' => $this->lifecyclePayload($updated),
                'message' => 'Installation updated successfully',
            ]);
        } catch (\Exception $e) {
            $this->logger->error('Failed to update installation', ['id' => $id, 'exception' => $e]);
            return $this->errorResponse('Failed to update installation');
        }
    }

    /**
     * Hard-delete an ops station (fleet/user/crm) and cascade readings.
     * Mendeley training corpus (source=dataset) cannot be deleted here.
     *
     * DELETE /api/v1/installations/{id}
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function destroy(string $id): JSONResponse
    {
        $userId = $this->getUserId();
        if (!$userId) {
            return $this->errorResponse('Unauthorized', Http::STATUS_UNAUTHORIZED);
        }

        try {
            $installation = $this->resolveStation($id);
            if ($installation === null) {
                return $this->errorResponse('Installation not found', Http::STATUS_NOT_FOUND);
            }

            $source = $installation->getSource() ?: 'user';
            if ($source === 'dataset') {
                return $this->errorResponse(
                    'Dataset (training) stations cannot be deleted from ops. Use admin dataset tools.',
                    Http::STATUS_FORBIDDEN,
                );
            }

            $dbId = (int) $installation->getId();
            $deletedReadings = 0;
            if ($dbId > 0) {
                $deletedReadings = $this->readingMapper->deleteByInstallation($dbId);
            }

            $this->mapper->delete($installation);

            $this->logger->info('Installation hard-deleted', [
                'id' => $dbId,
                'source' => $source,
                'readings_removed' => $deletedReadings,
                'by' => $userId,
            ]);

            return new JSONResponse([
                'success' => true,
                'message' => 'Installation deleted successfully',
                'id' => $dbId,
                'readings_removed' => $deletedReadings,
            ]);
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
     * Promote Virtual → Planned (session auth; dashboard ops).
     *
     * POST /api/v1/installations/{id}/promote-planned
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function promotePlanned(string $id): JSONResponse
    {
        $station = $this->resolveStation($id);
        if ($station === null) {
            return $this->errorResponse('Installation not found', Http::STATUS_NOT_FOUND);
        }

        $state = $this->stateOf($station);
        if (!StationLifecycle::canPromoteToPlanned($state, $station->getSoftRemoved())) {
            return $this->errorResponse(
                'Illegal transition to planned from ' . $state,
                Http::STATUS_CONFLICT,
            );
        }

        if ($state !== StationLifecycle::PLANNED) {
            $station->applyLifecycleState(StationLifecycle::PLANNED);
            $station->setUpdatedAt(new DateTime());
            $station = $this->mapper->update($station);
        }
        $this->odooMirror->notify($station);

        return new JSONResponse([
            'success' => true,
            'installation' => $this->lifecyclePayload($station),
            'message' => 'Station promoted to planned',
        ]);
    }

    /**
     * Mark Planned → Running / installed.
     *
     * POST /api/v1/installations/{id}/mark-installed
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function markInstalled(string $id): JSONResponse
    {
        $station = $this->resolveStation($id);
        if ($station === null) {
            return $this->errorResponse('Installation not found', Http::STATUS_NOT_FOUND);
        }

        $state = $this->stateOf($station);
        if (!StationLifecycle::canMarkInstalled($state, $station->getSoftRemoved())) {
            return $this->errorResponse(
                'Illegal transition to running from ' . $state,
                Http::STATUS_CONFLICT,
            );
        }

        $installedAtRaw = $this->request->getParam('installed_at');
        if ($state !== StationLifecycle::RUNNING) {
            $station->applyLifecycleState(StationLifecycle::RUNNING);
            try {
                $station->setInstalledAt(
                    $installedAtRaw ? new DateTime((string) $installedAtRaw) : new DateTime(),
                );
            } catch (\Throwable) {
                $station->setInstalledAt(new DateTime());
            }
            $station->setUpdatedAt(new DateTime());
            $station = $this->mapper->update($station);
        }
        $this->odooMirror->notify($station);

        return new JSONResponse([
            'success' => true,
            'installation' => $this->lifecyclePayload($station),
            'message' => 'Station marked installed (running)',
        ]);
    }

    /**
     * Soft-remove from public surfaces (row kept).
     *
     * POST /api/v1/installations/{id}/soft-remove
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function softRemove(string $id): JSONResponse
    {
        $station = $this->resolveStation($id);
        if ($station === null) {
            return $this->errorResponse('Installation not found', Http::STATUS_NOT_FOUND);
        }

        if (!$station->getSoftRemoved()) {
            $station->setSoftRemoved(true);
            $station->setUpdatedAt(new DateTime());
            $station = $this->mapper->update($station);
        }
        $this->odooMirror->notify($station);

        return new JSONResponse([
            'success' => true,
            'installation' => $this->lifecyclePayload($station),
            'message' => 'Station soft-removed from public listing',
        ]);
    }

    /**
     * Set lifecycle state explicitly (Virtual | Planned | Running).
     *
     * POST /api/v1/installations/{id}/set-lifecycle
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function setLifecycle(string $id): JSONResponse
    {
        $station = $this->resolveStation($id);
        if ($station === null) {
            return $this->errorResponse('Installation not found', Http::STATUS_NOT_FOUND);
        }

        $payload = $this->request->getParams();
        $target = strtolower(trim((string) ($payload['lifecycle_state'] ?? $this->request->getParam('lifecycle_state', ''))));
        if (!StationLifecycle::isValidState($target)) {
            return $this->errorResponse('Invalid lifecycle_state', Http::STATUS_BAD_REQUEST);
        }
        if (!StationLifecycle::canSetLifecycleState($target, $station->getSoftRemoved())) {
            return $this->errorResponse('Cannot change lifecycle while soft-removed', Http::STATUS_CONFLICT);
        }

        $prev = $this->stateOf($station);
        if ($prev !== $target) {
            $station->applyLifecycleState($target);
            if ($target === StationLifecycle::RUNNING && $station->getInstalledAt() === null) {
                $station->setInstalledAt(new DateTime());
            }
            if ($target === StationLifecycle::VIRTUAL) {
                // demote: clear installed_at optional
            }
            $station->setUpdatedAt(new DateTime());
            $station = $this->mapper->update($station);
            $this->logger->info('Lifecycle set', [
                'installation_id' => $station->getInstallationId(),
                'from' => $prev,
                'to' => $target,
            ]);
        }
        $this->odooMirror->notify($station);

        return new JSONResponse([
            'success' => true,
            'installation' => $this->lifecyclePayload($station),
            'message' => 'Lifecycle updated to ' . $target,
        ]);
    }

    private function resolveStation(string $id): ?Installation
    {
        $id = trim($id);
        if ($id === '') {
            return null;
        }

        // virtual_<dbId> / crm_<dbId> forms used by dashboard
        foreach (['virtual_', 'crm_'] as $prefix) {
            if (str_starts_with($id, $prefix)) {
                $dbId = (int) substr($id, strlen($prefix));
                if ($dbId > 0) {
                    try {
                        return $this->mapper->find($dbId);
                    } catch (DoesNotExistException) {
                        return null;
                    }
                }
            }
        }

        // bare numeric DB id (preferred for ops writes)
        if (ctype_digit($id)) {
            try {
                return $this->mapper->find((int) $id);
            } catch (DoesNotExistException) {
                // fall through
            }
        }

        // location_serial and dotted names: try installation key, then scan by name
        $found = $this->mapper->findByInstallationKey($id);
        if ($found !== null) {
            return $found;
        }

        // Fallback: name match (e.g. SolarSeed.Torres.Vedras) among all rows
        try {
            foreach ($this->mapper->findAll() as $row) {
                if ($row->getName() === $id || $row->getInstallationId() === $id) {
                    return $row;
                }
            }
        } catch (\Throwable) {
            // ignore
        }

        return null;
    }

    private function stateOf(Installation $station): string
    {
        $state = $station->getLifecycleState();
        if ($state === null || $state === '') {
            return StationLifecycle::defaultStateForNew($station->getIsVirtual(), $station->getSource());
        }

        return $state;
    }

    /**
     * @return array<string, mixed>
     */
    private function lifecyclePayload(Installation $station): array
    {
        $source = $station->getSource() ?: 'user';
        if ($source === 'dataset') {
            return $this->datasetRowToArray($station);
        }

        return $this->userOrCrmRowToArray($station, $source);
    }

    /**
     * @return array<string, mixed>
     */
    private function userOrCrmRowToArray(Installation $inst, string $source): array
    {
        $state = $inst->getLifecycleState() !== ''
            ? $inst->getLifecycleState()
            : StationLifecycle::defaultStateForNew($inst->getIsVirtual(), $source);
        $soft = $inst->getSoftRemoved();

        // Prefer stable installation_id key for lifecycle writes; keep virtual_ alias for UI
        $publicId = $inst->getInstallationId();
        if ($publicId === '' || $publicId === null) {
            $publicId = ($source === 'user' ? 'virtual_' : 'crm_') . $inst->getId();
        }

        return [
            'id' => $source === 'user' ? ('virtual_' . $inst->getId()) : $publicId,
            'installation_id' => $publicId,
            'name' => $inst->getName(),
            'location' => $inst->getLocation(),
            'latitude' => (float) $inst->getLatitude(),
            'longitude' => (float) $inst->getLongitude(),
            'capacity_kwp' => (float) $inst->getCapacityKwp(),
            'serial_number' => $inst->getSerialNumber(),
            'is_virtual' => StationLifecycle::isVirtualFlag($state),
            'source' => $source,
            'status' => $state === StationLifecycle::RUNNING ? 'active' : 'warning',
            'db_id' => $inst->getId(),
            'lifecycle_state' => $state,
            'soft_removed' => $soft,
            'public_category' => StationLifecycle::publicCategory($state, $soft),
            'is_public' => StationLifecycle::isPublic($state, $soft),
            'odoo_lead_id' => $inst->getOdooLeadId(),
            'installed_at' => $inst->getInstalledAt()?->format('c'),
            'website' => $inst->getWebsite(),
            'short_description' => $inst->getShortDescription(),
            'grid_price_kwh' => $inst->getGridPriceKwh() !== null ? (float) $inst->getGridPriceKwh() : null,
        ];
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
            'website' => $inst->getWebsite(),
            'short_description' => $inst->getShortDescription(),
            'grid_price_kwh' => $inst->getGridPriceKwh() !== null ? (float) $inst->getGridPriceKwh() : null,
        ];
    }


    /**
     * Attach NC series aggregates (truthful metrics Phase A).
     *
     * @param array<string, mixed> $payload
     * @return array<string, mixed>
     */
    private function attachSeriesStats(array $payload, int $dbId): array
    {
        if ($dbId <= 0) {
            $payload['total_production_kwh'] = 0.0;
            $payload['total_savings_eur'] = 0.0;
            $payload['readings_count'] = 0;
            $payload['has_series_data'] = false;
            $payload['series_source'] = 'none';
            return $payload;
        }

        try {
            $production = $this->readingMapper->sumProductionAll($dbId);
            $count = $this->readingMapper->countByInstallation($dbId);
            $hasMeasured = $this->readingMapper->hasMeasuredData($dbId);
        } catch (\Throwable $e) {
            $this->logger->warning('Series stats failed', ['id' => $dbId, 'exception' => $e]);
            $production = 0.0;
            $count = 0;
            $hasMeasured = false;
        }

        $price = isset($payload['grid_price_kwh']) ? (float) $payload['grid_price_kwh'] : (float) Application::DEFAULT_GRID_PRICE;
        $capacity = (float) ($payload['capacity_kwp'] ?? 0);
        // D8 capacity factor proxy when we have series: kWh / (kWp * hours) not available without window;
        // expose simple kWh/kWp if capacity > 0 else 0.
        $efficiency = ($capacity > 0 && $production > 0) ? min(1.0, $production / ($capacity * 1500.0)) : 0.0;

        $payload['total_production_kwh'] = round($production, 4);
        $payload['total_savings_eur'] = round($production * $price, 4);
        $payload['readings_count'] = $count;
        $payload['has_series_data'] = $count > 0;
        $payload['has_measured_data'] = $hasMeasured;
        $payload['series_source'] = $count > 0 ? 'nc_readings' : 'none';
        $payload['efficiency'] = round($efficiency, 4);
        // Ops status: for running stations, active=measured, offline=no measured series
        $lc = (string) ($payload['lifecycle_state'] ?? 'running');
        if ($lc === StationLifecycle::RUNNING && empty($payload['soft_removed'])) {
            $payload['status'] = $hasMeasured ? 'active' : 'offline';
        }

        return $payload;
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
