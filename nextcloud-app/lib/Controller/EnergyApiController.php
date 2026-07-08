<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Controller;

use DateTime;
use OCA\FilantropiaSolar\AppInfo\Application;
use OCA\FilantropiaSolar\Db\InstallationMapper;
use OCA\FilantropiaSolar\Service\SavingsService;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\Attribute\NoAdminRequired;
use OCP\AppFramework\Http\Attribute\NoCSRFRequired;
use OCP\AppFramework\Http\JSONResponse;
use OCP\AppFramework\OCSController;
use OCP\Http\Client\IClientService;
use OCP\IDBConnection;
use OCP\IRequest;
use Psr\Log\LoggerInterface;

/**
 * Energy API Controller
 *
 * Handles energy readings, statistics, and data import for installations.
 */
class EnergyApiController extends OCSController
{
    /** ML Service URL (internal Docker network) */
    private const ML_SERVICE_URL = 'http://filantropia-ml:8501';

    public function __construct(
        IRequest $request,
        private readonly InstallationMapper $mapper,
        private readonly SavingsService $savingsService,
        private readonly IClientService $clientService,
        private readonly IDBConnection $db,
        private readonly LoggerInterface $logger,
        private readonly ?string $userId,
    ) {
        parent::__construct(Application::APP_ID, $request);
    }

    /**
     * Get energy readings for an installation (proxied from ML service).
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     * @param string $id Installation ID
     * @param int $limit Number of readings to retrieve
     * @return JSONResponse
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function readings(string $id, int $limit = 168): JSONResponse
    {
        try {
            // Proxy to ML service which has the Mendeley dataset
            $client = $this->clientService->newClient();
            $url = self::ML_SERVICE_URL . '/data/installations/' . urlencode($id) . '/readings';
            $response = $client->get($url, [
                'query' => ['limit' => $limit],
            ]);
            $data = json_decode($response->getBody(), true);

            return new JSONResponse($data);
        } catch (\Exception $e) {
            $this->logger->error('Failed to fetch readings from ML service', ['id' => $id, 'exception' => $e]);
            return new JSONResponse([
                'readings' => [],
                'count' => 0,
            ]);
        }
    }

    /**
     * Get statistics for an installation (proxied from ML service).
     *
     * Returns yearly production average and efficiency for popup display.
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     * @param string $id Installation ID
     * @return JSONResponse
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function stats(string $id): JSONResponse
    {
        try {
            // Proxy to ML service - v3.0.4 stats endpoint for popup
            $client = $this->clientService->newClient();
            $url = self::ML_SERVICE_URL . '/installations/' . urlencode($id) . '/stats';
            $response = $client->get($url);
            $data = json_decode($response->getBody(), true);

            return new JSONResponse($data);
        } catch (\Exception $e) {
            $this->logger->error('Failed to fetch stats from ML service', ['id' => $id, 'exception' => $e]);
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
     * Import energy readings for an installation.
     *
     * @NoAdminRequired
     * @param int $id Installation ID
     * @return JSONResponse
     */
    public function import(int $id): JSONResponse
    {
        try {
            // Verify ownership
            $installation = $this->mapper->find($id);
            if ($installation->getUserId() !== $this->userId) {
                return new JSONResponse(
                    ['error' => 'Not found'],
                    Http::STATUS_NOT_FOUND
                );
            }

            // Get readings from request
            $data = $this->request->getParams();
            $readings = $data['readings'] ?? [];

            if (empty($readings)) {
                return new JSONResponse(
                    ['error' => 'No readings provided'],
                    Http::STATUS_BAD_REQUEST
                );
            }

            $imported = 0;
            $skipped = 0;

            foreach ($readings as $reading) {
                try {
                    $qb = $this->db->getQueryBuilder();
                    $qb->insert('filantropia_readings')
                        ->values([
                            'installation_id' => $qb->createNamedParameter($id),
                            'timestamp' => $qb->createNamedParameter($reading['timestamp']),
                            'production_kwh' => $qb->createNamedParameter($reading['production_kwh'] ?? null),
                            'consumption_kwh' => $qb->createNamedParameter($reading['consumption_kwh'] ?? null),
                            'solar_radiation_wm2' => $qb->createNamedParameter($reading['solar_radiation_wm2'] ?? null),
                            'temperature_c' => $qb->createNamedParameter($reading['temperature_c'] ?? null),
                            'cloud_cover_pct' => $qb->createNamedParameter($reading['cloud_cover_pct'] ?? null),
                        ]);
                    $qb->executeStatement();
                    $imported++;
                } catch (\Exception $e) {
                    // Likely duplicate timestamp
                    $skipped++;
                }
            }

            return new JSONResponse([
                'imported' => $imported,
                'skipped' => $skipped,
                'total' => count($readings),
            ]);
        } catch (\OCP\AppFramework\Db\DoesNotExistException $e) {
            return new JSONResponse(
                ['error' => 'Installation not found'],
                Http::STATUS_NOT_FOUND
            );
        } catch (\Exception $e) {
            $this->logger->error('Failed to import readings', ['exception' => $e]);
            return new JSONResponse(
                ['error' => 'Failed to import readings'],
                Http::STATUS_INTERNAL_SERVER_ERROR
            );
        }
    }

    /**
     * Sum production for a period.
     */
    private function sumProduction(int $installationId, DateTime $start, DateTime $end): float
    {
        $qb = $this->db->getQueryBuilder();
        $qb->select($qb->createFunction('SUM(production_kwh)'))
            ->from('filantropia_readings')
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId)))
            ->andWhere($qb->expr()->gte('timestamp', $qb->createNamedParameter($start->format('Y-m-d H:i:s'))))
            ->andWhere($qb->expr()->lte('timestamp', $qb->createNamedParameter($end->format('Y-m-d H:i:s'))));

        $result = $qb->executeQuery();
        $total = (float) $result->fetchOne();
        $result->closeCursor();

        return $total;
    }
}
