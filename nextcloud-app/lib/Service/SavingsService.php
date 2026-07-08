<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Service;

use DateTime;
use OCA\FilantropiaSolar\AppInfo\Application;
use OCA\FilantropiaSolar\Db\Installation;
use OCA\FilantropiaSolar\Db\InstallationMapper;
use OCP\IDBConnection;
use Psr\Log\LoggerInterface;

/**
 * Savings Service
 *
 * Calculates cost savings vs grid electricity prices.
 * Logic inherited from Python v1.2.x with DEFAULT_GRID_PRICE = 0.15 EUR/kWh.
 */
class SavingsService
{
    /**
     * Default grid electricity price in EUR/kWh.
     * Inherited from Python Application constant.
     */
    private const DEFAULT_GRID_PRICE_EUR_KWH = 0.15;

    public function __construct(
        private readonly IDBConnection $db,
        private readonly InstallationMapper $installationMapper,
        private readonly LoggerInterface $logger,
    ) {
    }

    /**
     * Calculate savings for given energy production.
     *
     * @param float $productionKwh Energy produced in kWh
     * @param float|null $gridPricePerKwh Grid price in EUR/kWh (default: 0.15)
     * @return float Savings in EUR
     */
    public function calculateSavings(float $productionKwh, ?float $gridPricePerKwh = null): float
    {
        $price = $gridPricePerKwh ?? self::DEFAULT_GRID_PRICE_EUR_KWH;
        return $productionKwh * $price;
    }

    /**
     * Calculate savings for a specific period.
     *
     * @param int $installationId Installation ID
     * @param DateTime $start Start date
     * @param DateTime $end End date
     * @return array{production_kwh: float, savings_eur: float, period_days: int, avg_daily_kwh: float}
     */
    public function calculatePeriodSavings(int $installationId, DateTime $start, DateTime $end): array
    {
        try {
            // Get installation for grid price
            $installation = $this->installationMapper->find($installationId);
            $gridPrice = $installation->getGridPriceFloat();

            // Sum production for period
            $totalProduction = $this->sumProductionForPeriod($installationId, $start, $end);
            $periodDays = max(1, $start->diff($end)->days);

            return [
                'production_kwh' => $totalProduction,
                'savings_eur' => $this->calculateSavings($totalProduction, $gridPrice),
                'period_days' => $periodDays,
                'avg_daily_kwh' => $totalProduction / $periodDays,
            ];
        } catch (\Exception $e) {
            $this->logger->error('Failed to calculate period savings', [
                'installationId' => $installationId,
                'exception' => $e,
            ]);
            return [
                'production_kwh' => 0.0,
                'savings_eur' => 0.0,
                'period_days' => 0,
                'avg_daily_kwh' => 0.0,
            ];
        }
    }

    /**
     * Calculate total savings for a user across all installations.
     *
     * @param string $userId User ID
     * @param DateTime|null $since Since date (default: all time)
     * @return array{total_production_kwh: float, total_savings_eur: float, installations_count: int}
     */
    public function calculateUserTotalSavings(string $userId, ?DateTime $since = null): array
    {
        try {
            $installations = $this->installationMapper->findAllByUser($userId);
            $totalProduction = 0.0;
            $totalSavings = 0.0;

            foreach ($installations as $installation) {
                $production = $this->sumProductionForInstallation(
                    $installation->getId(),
                    $since
                );
                $savings = $this->calculateSavings($production, $installation->getGridPriceFloat());

                $totalProduction += $production;
                $totalSavings += $savings;
            }

            return [
                'total_production_kwh' => $totalProduction,
                'total_savings_eur' => $totalSavings,
                'installations_count' => count($installations),
            ];
        } catch (\Exception $e) {
            $this->logger->error('Failed to calculate user total savings', [
                'userId' => $userId,
                'exception' => $e,
            ]);
            return [
                'total_production_kwh' => 0.0,
                'total_savings_eur' => 0.0,
                'installations_count' => 0,
            ];
        }
    }

    /**
     * Calculate monthly savings breakdown.
     *
     * @param int $installationId Installation ID
     * @param int $year Year to calculate
     * @return array<int, array{month: int, production_kwh: float, savings_eur: float}>
     */
    public function calculateMonthlySavings(int $installationId, int $year): array
    {
        try {
            $installation = $this->installationMapper->find($installationId);
            $gridPrice = $installation->getGridPriceFloat();

            $qb = $this->db->getQueryBuilder();
            $qb->select(
                $qb->createFunction('MONTH(timestamp) as month'),
                $qb->createFunction('SUM(production_kwh) as total_production')
            )
                ->from('filantropia_readings')
                ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId)))
                ->andWhere($qb->expr()->eq($qb->createFunction('YEAR(timestamp)'), $qb->createNamedParameter($year)))
                ->groupBy('month')
                ->orderBy('month');

            $result = $qb->executeQuery();
            $rows = $result->fetchAll();
            $result->closeCursor();

            $monthly = [];
            foreach ($rows as $row) {
                $production = (float) $row['total_production'];
                $monthly[] = [
                    'month' => (int) $row['month'],
                    'production_kwh' => $production,
                    'savings_eur' => $this->calculateSavings($production, $gridPrice),
                ];
            }

            return $monthly;
        } catch (\Exception $e) {
            $this->logger->error('Failed to calculate monthly savings', [
                'installationId' => $installationId,
                'year' => $year,
                'exception' => $e,
            ]);
            return [];
        }
    }

    /**
     * Sum production for a period.
     */
    private function sumProductionForPeriod(int $installationId, DateTime $start, DateTime $end): float
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

    /**
     * Sum production for an installation (optionally since a date).
     */
    private function sumProductionForInstallation(int $installationId, ?DateTime $since = null): float
    {
        $qb = $this->db->getQueryBuilder();
        $qb->select($qb->createFunction('SUM(production_kwh)'))
            ->from('filantropia_readings')
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId)));

        if ($since) {
            $qb->andWhere($qb->expr()->gte('timestamp', $qb->createNamedParameter($since->format('Y-m-d H:i:s'))));
        }

        $result = $qb->executeQuery();
        $total = (float) $result->fetchOne();
        $result->closeCursor();

        return $total;
    }
}
