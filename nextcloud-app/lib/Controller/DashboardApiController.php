<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Controller;

use OCA\FilantropiaSolar\AppInfo\Application;
use OCA\FilantropiaSolar\Db\InstallationMapper;
use OCA\FilantropiaSolar\Service\SavingsService;
use OCA\FilantropiaSolar\Service\WeatherService;
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
 * Dashboard API Controller
 *
 * Provides aggregated statistics and overview data for the dashboard view.
 */
class DashboardApiController extends OCSController
{
    /** ML Service URL (internal Docker network) */
    private const ML_SERVICE_URL = 'http://filantropia-ml:8501';

    public function __construct(
        IRequest $request,
        private readonly InstallationMapper $mapper,
        private readonly SavingsService $savingsService,
        private readonly WeatherService $weatherService,
        private readonly IClientService $clientService,
        private readonly LoggerInterface $logger,
        private readonly IDBConnection $db,
        private readonly ?string $userId,
    ) {
        parent::__construct(Application::APP_ID, $request);
    }

    /**
     * Get dashboard overview data (proxied from ML service).
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     * @return JSONResponse
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function overview(): JSONResponse
    {
        try {
            // Proxy to ML service which has the Mendeley dataset
            $client = $this->clientService->newClient();
            $response = $client->get(self::ML_SERVICE_URL . '/data/dashboard');
            $data = json_decode($response->getBody(), true);

            return new JSONResponse($data);
        } catch (\Exception $e) {
            $this->logger->error('Failed to fetch dashboard from ML service', ['exception' => $e]);

            // Fallback to database
            try {
                $installations = $this->mapper->findAllByUser($this->userId);
                $totalCount = count($installations);
                $totalCapacity = 0.0;

                foreach ($installations as $installation) {
                    $totalCapacity += (float) $installation->getCapacityKwp();
                }

                return new JSONResponse([
                    'overview' => [
                        'total_capacity_kwp' => round($totalCapacity, 2),
                        'online_count' => $totalCount,
                        'total_count' => $totalCount,
                        'monthly_generation_kwh' => 0,
                        'total_savings_eur' => 0,
                    ],
                    'location_stats' => [],
                    'recent_activity' => [],
                ]);
            } catch (\Exception $dbEx) {
                return new JSONResponse([
                    'overview' => [
                        'total_capacity_kwp' => 0,
                        'online_count' => 0,
                        'total_count' => 0,
                        'monthly_generation_kwh' => 0,
                        'total_savings_eur' => 0,
                    ],
                    'location_stats' => [],
                    'recent_activity' => [],
                ]);
            }
        }
    }

    /**
     * Get savings breakdown for all installations.
     *
     * @NoAdminRequired
     * @return JSONResponse
     */
    public function savings(): JSONResponse
    {
        try {
            $savingsData = $this->savingsService->calculateUserTotalSavings($this->userId);

            return new JSONResponse([
                'savings' => $savingsData,
            ]);
        } catch (\Exception $e) {
            return new JSONResponse(
                ['error' => 'Failed to load savings data'],
                Http::STATUS_INTERNAL_SERVER_ERROR
            );
        }
    }

    /**
     * Get monthly generation total.
     */
    private function getMonthlyGeneration(): float
    {
        try {
            $startOfMonth = (new \DateTime('first day of this month'))->format('Y-m-d 00:00:00');
            $now = (new \DateTime())->format('Y-m-d H:i:s');

            $qb = $this->db->getQueryBuilder();
            $qb->select($qb->createFunction('SUM(r.production_kwh) as total'))
                ->from('filantropia_readings', 'r')
                ->innerJoin('r', 'filantropia_installations', 'i', $qb->expr()->eq('r.installation_id', 'i.id'))
                ->where($qb->expr()->eq('i.user_id', $qb->createNamedParameter($this->userId)))
                ->andWhere($qb->expr()->gte('r.timestamp', $qb->createNamedParameter($startOfMonth)))
                ->andWhere($qb->expr()->lte('r.timestamp', $qb->createNamedParameter($now)));

            $result = $qb->executeQuery();
            $total = (float) $result->fetchOne();
            $result->closeCursor();

            return $total;
        } catch (\Exception $e) {
            return 0.0;
        }
    }

    /**
     * Get statistics grouped by location.
     */
    private function getLocationStats(array $installations): array
    {
        $locations = $this->weatherService->getAvailableLocations();
        $stats = [];

        // Group installations by nearest location
        $grouped = [];
        foreach ($installations as $installation) {
            $lat = (float) $installation->getLatitude();
            $lon = (float) $installation->getLongitude();
            $nearest = $this->weatherService->findNearestLocation($lat, $lon);

            if (!isset($grouped[$nearest])) {
                $grouped[$nearest] = [
                    'name' => $nearest,
                    'count' => 0,
                    'capacity_kwp' => 0.0,
                    'lat' => $locations[$nearest]['lat'] ?? null,
                    'lon' => $locations[$nearest]['lon'] ?? null,
                ];
            }

            $grouped[$nearest]['count']++;
            $grouped[$nearest]['capacity_kwp'] += (float) $installation->getCapacityKwp();
        }

        // Calculate performance (placeholder - would need actual production data)
        foreach ($grouped as $name => $data) {
            $grouped[$name]['capacity_kwp'] = round($data['capacity_kwp'], 2);
            $grouped[$name]['performance'] = 0.85; // Placeholder
            $stats[] = $grouped[$name];
        }

        return $stats;
    }

    /**
     * Get recent activity log.
     */
    private function getRecentActivity(): array
    {
        // Placeholder - would integrate with actual activity tracking
        // For now, return empty array
        return [];
    }
}
