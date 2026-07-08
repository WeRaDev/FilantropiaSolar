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
}
