<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Db;

use DateTime;
use OCP\AppFramework\Db\DoesNotExistException;
use OCP\AppFramework\Db\MultipleObjectsReturnedException;
use OCP\AppFramework\Db\QBMapper;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\IDBConnection;

/**
 * EnergyReading Mapper
 *
 * Handles database operations for EnergyReading entities.
 *
 * @extends QBMapper<EnergyReading>
 */
class EnergyReadingMapper extends QBMapper
{
    public function __construct(IDBConnection $db)
    {
        parent::__construct($db, 'fs_readings', EnergyReading::class);
    }

    /**
     * Find reading by ID.
     *
     * @throws DoesNotExistException
     * @throws MultipleObjectsReturnedException
     */
    public function find(int $id): EnergyReading
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select('*')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('id', $qb->createNamedParameter($id, IQueryBuilder::PARAM_INT)));

        return $this->findEntity($qb);
    }

    /**
     * Find readings for an installation within a time range.
     *
     * @return EnergyReading[]
     */
    public function findByInstallation(int $installationId, ?DateTime $since = null, ?DateTime $until = null): array
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select('*')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId, IQueryBuilder::PARAM_INT)));

        if ($since !== null) {
            $qb->andWhere($qb->expr()->gte('timestamp', $qb->createNamedParameter($since->format('Y-m-d H:i:s'))));
        }

        if ($until !== null) {
            $qb->andWhere($qb->expr()->lte('timestamp', $qb->createNamedParameter($until->format('Y-m-d H:i:s'))));
        }

        $qb->orderBy('timestamp', 'ASC');

        return $this->findEntities($qb);
    }

    /**
     * Find readings for the last N hours.
     *
     * @return EnergyReading[]
     */
    public function findRecent(int $installationId, int $hours = 24): array
    {
        $since = (new DateTime())->modify("-{$hours} hours");
        return $this->findByInstallation($installationId, $since);
    }

    /**
     * Sum production for an installation within a time range.
     */
    /**
     * Sum all production for an installation (entire series).
     */
    public function sumProductionAll(int $installationId): float
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select($qb->createFunction('COALESCE(SUM(production_kwh), 0)'))
            ->from($this->getTableName())
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId, IQueryBuilder::PARAM_INT)));

        $result = $qb->executeQuery();
        $sum = (float) $result->fetchOne();
        $result->closeCursor();

        return $sum;
    }

    /**
     * Count reading rows for an installation.
     */
    public function countByInstallation(int $installationId): int
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select($qb->createFunction('COUNT(*)'))
            ->from($this->getTableName())
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId, IQueryBuilder::PARAM_INT)));

        $result = $qb->executeQuery();
        $count = (int) $result->fetchOne();
        $result->closeCursor();

        return $count;
    }

    public function sumProduction(int $installationId, DateTime $since, DateTime $until): float
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select($qb->createFunction('COALESCE(SUM(production_kwh), 0)'))
            ->from($this->getTableName())
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId, IQueryBuilder::PARAM_INT)))
            ->andWhere($qb->expr()->gte('timestamp', $qb->createNamedParameter($since->format('Y-m-d H:i:s'))))
            ->andWhere($qb->expr()->lte('timestamp', $qb->createNamedParameter($until->format('Y-m-d H:i:s'))));

        $result = $qb->executeQuery();
        $sum = (float) $result->fetchOne();
        $result->closeCursor();

        return $sum;
    }

    /**
     * Sum consumption for an installation within a time range.
     */
    public function sumConsumption(int $installationId, DateTime $since, DateTime $until): float
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select($qb->createFunction('COALESCE(SUM(consumption_kwh), 0)'))
            ->from($this->getTableName())
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId, IQueryBuilder::PARAM_INT)))
            ->andWhere($qb->expr()->gte('timestamp', $qb->createNamedParameter($since->format('Y-m-d H:i:s'))))
            ->andWhere($qb->expr()->lte('timestamp', $qb->createNamedParameter($until->format('Y-m-d H:i:s'))));

        $result = $qb->executeQuery();
        $sum = (float) $result->fetchOne();
        $result->closeCursor();

        return $sum;
    }

    /**
     * Get latest reading for an installation.
     *
     * @throws DoesNotExistException
     */
    public function findLatest(int $installationId): EnergyReading
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select('*')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId, IQueryBuilder::PARAM_INT)))
            ->orderBy('timestamp', 'DESC')
            ->setMaxResults(1);

        return $this->findEntity($qb);
    }

    /**
     * Insert batch of readings efficiently.
     *
     * @param EnergyReading[] $readings
     * @return int Number of inserted rows
     */
    public function insertBatch(array $readings): int
    {
        $inserted = 0;

        foreach ($readings as $reading) {
            try {
                $this->insert($reading);
                $inserted++;
            } catch (\Exception $e) {
                // Skip duplicates (same installation_id + timestamp)
                continue;
            }
        }

        return $inserted;
    }

    /**
     * Delete readings older than a certain date.
     */
    public function deleteOlderThan(DateTime $cutoff): int
    {
        $qb = $this->db->getQueryBuilder();

        $qb->delete($this->getTableName())
            ->where($qb->expr()->lt('timestamp', $qb->createNamedParameter($cutoff->format('Y-m-d H:i:s'))));

        return $qb->executeStatement();
    }

    /**
     * Delete all readings for an installation.
     */
    public function deleteByInstallation(int $installationId): int
    {
        $qb = $this->db->getQueryBuilder();

        $qb->delete($this->getTableName())
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId, IQueryBuilder::PARAM_INT)));

        return $qb->executeStatement();
    }

    /**
     * Whether any measured readings exist for the installation (Active vs Offline).
     */
    public function hasMeasuredData(int $installationId): bool
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select($qb->createFunction('COUNT(*)'))
            ->from($this->getTableName())
            ->where($qb->expr()->eq(
                'installation_id',
                $qb->createNamedParameter($installationId, IQueryBuilder::PARAM_INT),
            ))
            ->andWhere($qb->expr()->eq(
                'provenance',
                $qb->createNamedParameter(EnergyReading::PROVENANCE_MEASURED),
            ))
            ->setMaxResults(1);

        $result = $qb->executeQuery();
        $count = (int) $result->fetchOne();
        $result->closeCursor();

        return $count > 0;
    }

    /**
     * Production for the latest row by timestamp (may be older than last complete hour).
     */
    public function findLatestProduction(int $installationId): ?float
    {
        try {
            $latest = $this->findLatest($installationId);
        } catch (DoesNotExistException $e) {
            return null;
        }

        return $latest->getProductionFloat();
    }

    /**
     * Production for the last complete UTC hour bucket only.
     * Returns 0.0 when the hour exists with zero production; null when missing.
     */
    public function findLastCompleteHourProduction(int $installationId, ?\DateTimeInterface $now = null): ?float
    {
        $nowUtc = $now
            ? \DateTimeImmutable::createFromInterface($now)->setTimezone(new \DateTimeZone('UTC'))
            : new \DateTimeImmutable('now', new \DateTimeZone('UTC'));
        $lastComplete = $nowUtc->setTime((int) $nowUtc->format('H'), 0, 0)
            ->sub(new \DateInterval('PT1H'));
        $ts = DateTime::createFromImmutable($lastComplete);
        $row = $this->findByInstallationAndTimestamp($installationId, $ts);
        if ($row === null) {
            return null;
        }

        return $row->getProductionFloat();
    }

    /**
     * @return list<string> timestamps formatted Y-m-d H:i:s
     */
    public function listTimestamps(int $installationId, DateTime $since, DateTime $until): array
    {
        $qb = $this->db->getQueryBuilder();
        $qb->select('timestamp')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId, IQueryBuilder::PARAM_INT)))
            ->andWhere($qb->expr()->gte('timestamp', $qb->createNamedParameter($since->format('Y-m-d H:i:s'))))
            ->andWhere($qb->expr()->lte('timestamp', $qb->createNamedParameter($until->format('Y-m-d H:i:s'))))
            ->orderBy('timestamp', 'ASC');

        $result = $qb->executeQuery();
        $out = [];
        while ($row = $result->fetch()) {
            $ts = $row['timestamp'] ?? null;
            if ($ts instanceof \DateTimeInterface) {
                $out[] = $ts->format('Y-m-d H:i:s');
            } elseif (is_string($ts) && $ts !== '') {
                // Normalize to hour floor string
                try {
                    $dt = new DateTime($ts);
                    $out[] = $dt->format('Y-m-d H:00:00');
                } catch (\Throwable) {
                    $out[] = substr($ts, 0, 13) . ':00:00';
                }
            }
        }
        $result->closeCursor();

        return $out;
    }

    /**
     * Counts by provenance for admin visibility.
     *
     * @return array{measured:int, simulated:int, total:int}
     */
    public function countByProvenance(int $installationId): array
    {
        $qb = $this->db->getQueryBuilder();
        $qb->select('provenance')
            ->selectAlias($qb->createFunction('COUNT(*)'), 'cnt')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId, IQueryBuilder::PARAM_INT)))
            ->groupBy('provenance');

        $result = $qb->executeQuery();
        $measured = 0;
        $simulated = 0;
        while ($row = $result->fetch()) {
            $p = (string) ($row['provenance'] ?? EnergyReading::PROVENANCE_SIMULATED);
            $c = (int) ($row['cnt'] ?? 0);
            if ($p === EnergyReading::PROVENANCE_MEASURED) {
                $measured += $c;
            } else {
                $simulated += $c;
            }
        }
        $result->closeCursor();

        return [
            'measured' => $measured,
            'simulated' => $simulated,
            'total' => $measured + $simulated,
        ];
    }

    /**
     * Insert simulated reading only if hour is empty.
     *
     * @return 'inserted'|'exists'|'measured'
     */
    public function insertSimulatedIfEmpty(
        int $installationId,
        DateTime $timestamp,
        float $productionKwh,
        ?float $temperatureC = null,
        ?int $cloudCoverPct = null,
        ?float $solarRadiationWm2 = null,
    ): string {
        $existing = $this->findByInstallationAndTimestamp($installationId, $timestamp);
        if ($existing !== null) {
            $prov = $existing->getProvenance() ?: EnergyReading::PROVENANCE_SIMULATED;
            return $prov === EnergyReading::PROVENANCE_MEASURED ? 'measured' : 'exists';
        }

        $reading = new EnergyReading();
        $reading->setInstallationId($installationId);
        $reading->setTimestamp($timestamp);
        $reading->setProductionKwh((string) $productionKwh);
        $reading->setProvenance(EnergyReading::PROVENANCE_SIMULATED);
        if ($temperatureC !== null) {
            $reading->setTemperatureC((string) $temperatureC);
        }
        if ($cloudCoverPct !== null) {
            $reading->setCloudCoverPct($cloudCoverPct);
        }
        if ($solarRadiationWm2 !== null) {
            $reading->setSolarRadiationWm2((string) $solarRadiationWm2);
        }
        try {
            $this->insert($reading);
            return 'inserted';
        } catch (\Exception $e) {
            // race / unique
            $again = $this->findByInstallationAndTimestamp($installationId, $timestamp);
            if ($again !== null && ($again->getProvenance() ?: '') === EnergyReading::PROVENANCE_MEASURED) {
                return 'measured';
            }
            return 'exists';
        }
    }

    /**
     * Upsert measured reading. Overwrites simulated; never blocked.
     *
     * @return 'inserted'|'updated'|'failed'
     */
    public function upsertMeasured(
        int $installationId,
        DateTime $timestamp,
        float $productionKwh,
        ?float $consumptionKwh = null,
        ?float $solarRadiationWm2 = null,
        ?float $temperatureC = null,
        ?int $cloudCoverPct = null,
    ): string {
        $existing = $this->findByInstallationAndTimestamp($installationId, $timestamp);
        if ($existing === null) {
            $reading = new EnergyReading();
            $reading->setInstallationId($installationId);
            $reading->setTimestamp($timestamp);
            $reading->setProductionKwh((string) $productionKwh);
            $reading->setProvenance(EnergyReading::PROVENANCE_MEASURED);
            if ($consumptionKwh !== null) {
                $reading->setConsumptionKwh((string) $consumptionKwh);
            }
            if ($solarRadiationWm2 !== null) {
                $reading->setSolarRadiationWm2((string) $solarRadiationWm2);
            }
            if ($temperatureC !== null) {
                $reading->setTemperatureC((string) $temperatureC);
            }
            if ($cloudCoverPct !== null) {
                $reading->setCloudCoverPct($cloudCoverPct);
            }
            try {
                $this->insert($reading);
                return 'inserted';
            } catch (\Exception $e) {
                $existing = $this->findByInstallationAndTimestamp($installationId, $timestamp);
                if ($existing === null) {
                    return 'failed';
                }
            }
        }

        if ($existing === null) {
            return 'failed';
        }

        $existing->setProductionKwh((string) $productionKwh);
        $existing->setProvenance(EnergyReading::PROVENANCE_MEASURED);
        if ($consumptionKwh !== null) {
            $existing->setConsumptionKwh((string) $consumptionKwh);
        }
        if ($solarRadiationWm2 !== null) {
            $existing->setSolarRadiationWm2((string) $solarRadiationWm2);
        }
        if ($temperatureC !== null) {
            $existing->setTemperatureC((string) $temperatureC);
        }
        if ($cloudCoverPct !== null) {
            $existing->setCloudCoverPct($cloudCoverPct);
        }
        $this->update($existing);

        return 'updated';
    }

    public function findByInstallationAndTimestamp(int $installationId, DateTime $timestamp): ?EnergyReading
    {
        $qb = $this->db->getQueryBuilder();
        $qb->select('*')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId, IQueryBuilder::PARAM_INT)))
            ->andWhere($qb->expr()->eq('timestamp', $qb->createNamedParameter($timestamp->format('Y-m-d H:i:s'))))
            ->setMaxResults(1);

        try {
            return $this->findEntity($qb);
        } catch (DoesNotExistException $e) {
            return null;
        } catch (MultipleObjectsReturnedException $e) {
            $entities = $this->findEntities($qb);
            return $entities[0] ?? null;
        }
    }

    /**
     * True if the last complete UTC hour bucket has provenance=measured.
     */
    public function hasMeasuredLastCompleteHour(int $installationId, ?\DateTimeInterface $now = null): bool
    {
        $nowUtc = $now
            ? \DateTimeImmutable::createFromInterface($now)->setTimezone(new \DateTimeZone('UTC'))
            : new \DateTimeImmutable('now', new \DateTimeZone('UTC'));
        $lastComplete = $nowUtc->setTime((int) $nowUtc->format('H'), 0, 0)
            ->sub(new \DateInterval('PT1H'));
        $ts = $lastComplete->format('Y-m-d H:i:s');

        $qb = $this->db->getQueryBuilder();
        $qb->select($qb->createFunction('COUNT(*)'))
            ->from($this->getTableName())
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId, IQueryBuilder::PARAM_INT)))
            ->andWhere($qb->expr()->eq('timestamp', $qb->createNamedParameter($ts)))
            ->andWhere($qb->expr()->eq(
                'provenance',
                $qb->createNamedParameter(EnergyReading::PROVENANCE_MEASURED),
            ))
            ->setMaxResults(1);

        $result = $qb->executeQuery();
        $count = (int) $result->fetchOne();
        $result->closeCursor();

        return $count > 0;
    }

    /**
     * Min/max reading timestamps for calendar bounds (Y-m-d).
     *
     * @return array{from: ?string, to: ?string}
     */
    public function dateBounds(int $installationId): array
    {
        $qb = $this->db->getQueryBuilder();
        $qb->selectAlias($qb->createFunction('MIN(timestamp)'), 'min_ts')
            ->selectAlias($qb->createFunction('MAX(timestamp)'), 'max_ts')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId, IQueryBuilder::PARAM_INT)));

        $result = $qb->executeQuery();
        $row = $result->fetch();
        $result->closeCursor();
        if (!$row || empty($row['min_ts'])) {
            return ['from' => null, 'to' => null];
        }
        $min = (string) $row['min_ts'];
        $max = (string) $row['max_ts'];

        return [
            'from' => substr($min, 0, 10),
            'to' => substr($max, 0, 10),
        ];
    }

    /**
     * Provenance mix for a time window.
     *
     * @return array{measured:int, simulated:int, total:int}
     */
    public function countByProvenanceInRange(int $installationId, DateTime $since, DateTime $until): array
    {
        $qb = $this->db->getQueryBuilder();
        $qb->select('provenance')
            ->selectAlias($qb->createFunction('COUNT(*)'), 'cnt')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId, IQueryBuilder::PARAM_INT)))
            ->andWhere($qb->expr()->gte('timestamp', $qb->createNamedParameter($since->format('Y-m-d H:i:s'))))
            ->andWhere($qb->expr()->lte('timestamp', $qb->createNamedParameter($until->format('Y-m-d H:i:s'))))
            ->groupBy('provenance');

        $result = $qb->executeQuery();
        $measured = 0;
        $simulated = 0;
        while ($row = $result->fetch()) {
            $p = (string) ($row['provenance'] ?? EnergyReading::PROVENANCE_SIMULATED);
            $c = (int) ($row['cnt'] ?? 0);
            if ($p === EnergyReading::PROVENANCE_MEASURED) {
                $measured += $c;
            } else {
                $simulated += $c;
            }
        }
        $result->closeCursor();

        return [
            'measured' => $measured,
            'simulated' => $simulated,
            'total' => $measured + $simulated,
        ];
    }

}
