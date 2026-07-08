<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Controller;

use OCA\FilantropiaSolar\AppInfo\Application;
use OCA\FilantropiaSolar\Db\InstallationMapper;
use OCP\AppFramework\ApiController;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\Attribute\NoCSRFRequired;
use OCP\AppFramework\Http\Attribute\PublicPage;
use OCP\AppFramework\Http\JSONResponse;
use OCP\Http\Client\IClientService;
use OCP\IConfig;
use OCP\IRequest;
use Psr\Log\LoggerInterface;

/**
 * Public read-only API for external consumers (e.g. the Odoo public site).
 *
 * Authenticated by a bearer token stored in app config ('public_api_token'),
 * decoupled from the Nextcloud user session. Exposes only dataset (global)
 * stations and aggregate figures - never user-owned virtual stations or
 * personal data.
 */
class PublicApiController extends ApiController
{
    /** ML service URL (internal Docker network). */
    private const ML_SERVICE_URL = 'http://filantropia-ml:8501';

    public function __construct(
        IRequest $request,
        private readonly InstallationMapper $mapper,
        private readonly IConfig $config,
        private readonly IClientService $clientService,
        private readonly LoggerInterface $logger,
    ) {
        parent::__construct(Application::APP_ID, $request);
    }

    /**
     * List public (dataset) stations.
     *
     * GET /api/public/v1/stations
     */
    #[PublicPage]
    #[NoCSRFRequired]
    public function stations(): JSONResponse
    {
        if (!$this->authorized()) {
            return new JSONResponse(['error' => 'unauthorized'], Http::STATUS_UNAUTHORIZED);
        }

        $rows = $this->mapper->findAllBySource('dataset');
        $stations = array_map(fn($i) => [
            'id' => $i->getInstallationId(),
            'name' => $i->getName(),
            'location' => $i->getLocation(),
            'latitude' => (float) $i->getLatitude(),
            'longitude' => (float) $i->getLongitude(),
            'capacity_kwp' => (float) $i->getCapacityKwp(),
            'from_date' => $i->getFromDate()?->format('Y-m-d'),
            'to_date' => $i->getToDate()?->format('Y-m-d'),
        ], $rows);

        return new JSONResponse([
            'success' => true,
            'stations' => $stations,
            'count' => count($stations),
        ]);
    }

    /**
     * Public aggregate dashboard figures (computed from DB, not ML).
     *
     * GET /api/public/v1/dashboard
     */
    #[PublicPage]
    #[NoCSRFRequired]
    public function dashboard(): JSONResponse
    {
        if (!$this->authorized()) {
            return new JSONResponse(['error' => 'unauthorized'], Http::STATUS_UNAUTHORIZED);
        }

        $rows = $this->mapper->findAllBySource('dataset');
        $totalCapacity = 0.0;
        $locations = [];
        foreach ($rows as $i) {
            $totalCapacity += (float) $i->getCapacityKwp();
            $locations[$i->getLocation()] = true;
        }

        return new JSONResponse([
            'success' => true,
            'station_count' => count($rows),
            'total_capacity_kwp' => round($totalCapacity, 2),
            'locations' => array_keys($locations),
        ]);
    }

    /**
     * Live production/savings estimate for a candidate (virtual) station.
     * Proxies the ML service. Used by the Odoo public quote flow.
     *
     * POST /api/public/v1/estimate  { latitude, longitude, capacity_kwp, location? }
     */
    #[PublicPage]
    #[NoCSRFRequired]
    public function estimate(): JSONResponse
    {
        if (!$this->authorized()) {
            return new JSONResponse(['error' => 'unauthorized'], Http::STATUS_UNAUTHORIZED);
        }

        $latitude = (float) $this->request->getParam('latitude', 0);
        $longitude = (float) $this->request->getParam('longitude', 0);
        $capacityKwp = (float) $this->request->getParam('capacity_kwp', 0);
        $location = (string) $this->request->getParam('location', '');

        if ($capacityKwp <= 0) {
            return new JSONResponse(['error' => 'capacity_kwp must be positive'], Http::STATUS_BAD_REQUEST);
        }

        try {
            $client = $this->clientService->newClient();
            $response = $client->post(self::ML_SERVICE_URL . '/estimate', [
                'json' => [
                    'latitude' => $latitude,
                    'longitude' => $longitude,
                    'capacity_kwp' => $capacityKwp,
                    'location' => $location,
                ],
                'timeout' => 30,
            ]);
            $data = json_decode((string) $response->getBody(), true);
            return new JSONResponse(['success' => true, 'estimate' => $data]);
        } catch (\Throwable $e) {
            $this->logger->error('Public estimate proxy failed', ['exception' => $e]);
            return new JSONResponse(['success' => false, 'error' => 'estimate unavailable'], Http::STATUS_BAD_GATEWAY);
        }
    }

    /**
     * Verify the request bearer token against the configured public API token.
     */
    private function authorized(): bool
    {
        $expected = (string) $this->config->getAppValue(Application::APP_ID, 'public_api_token', '');
        if ($expected === '') {
            $this->logger->warning('FilantropiaSolar public_api_token is not configured; rejecting public API request');
            return false;
        }

        $header = (string) $this->request->getHeader('Authorization');
        $token = str_starts_with($header, 'Bearer ') ? substr($header, 7) : '';

        return $token !== '' && hash_equals($expected, $token);
    }
}
