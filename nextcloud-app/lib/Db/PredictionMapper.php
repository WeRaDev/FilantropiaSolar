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
 * Prediction Mapper
 *
 * Handles database operations for Prediction entities.
 *
 * @extends QBMapper<Prediction>
 */
class PredictionMapper extends QBMapper
{
    public function __construct(IDBConnection $db)
    {
        parent::__construct($db, 'fs_predictions', Prediction::class);
    }

    /**
     * Find prediction by ID.
     *
     * @throws DoesNotExistException
     * @throws MultipleObjectsReturnedException
     */
    public function find(int $id): Prediction
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select('*')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('id', $qb->createNamedParameter($id, IQueryBuilder::PARAM_INT)));

        return $this->findEntity($qb);
    }

    /**
     * Find predictions for an installation within a date range.
     *
     * @return Prediction[]
     */
    public function findByInstallation(int $installationId, ?DateTime $startDate = null, ?DateTime $endDate = null): array
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select('*')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId, IQueryBuilder::PARAM_INT)));

        if ($startDate !== null) {
            $qb->andWhere($qb->expr()->gte('prediction_date', $qb->createNamedParameter($startDate->format('Y-m-d'))));
        }

        if ($endDate !== null) {
            $qb->andWhere($qb->expr()->lte('prediction_date', $qb->createNamedParameter($endDate->format('Y-m-d'))));
        }

        $qb->orderBy('prediction_date', 'ASC')
            ->addOrderBy('hour', 'ASC');

        return $this->findEntities($qb);
    }

    /**
     * Find predictions for the next N days.
     *
     * @return Prediction[]
     */
    public function findForecast(int $installationId, int $days = 7): array
    {
        $startDate = new DateTime('today');
        $endDate = (new DateTime())->modify("+{$days} days");
        return $this->findByInstallation($installationId, $startDate, $endDate);
    }

    /**
     * Find prediction for specific date and hour.
     *
     * @throws DoesNotExistException
     * @throws MultipleObjectsReturnedException
     */
    public function findByDateHour(int $installationId, DateTime $date, int $hour): Prediction
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select('*')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId, IQueryBuilder::PARAM_INT)))
            ->andWhere($qb->expr()->eq('prediction_date', $qb->createNamedParameter($date->format('Y-m-d'))))
            ->andWhere($qb->expr()->eq('hour', $qb->createNamedParameter($hour, IQueryBuilder::PARAM_INT)));

        return $this->findEntity($qb);
    }

    /**
     * Upsert prediction (insert or update if exists).
     */
    public function upsert(Prediction $prediction): Prediction
    {
        try {
            // Try to find existing
            $existing = $this->findByDateHour(
                $prediction->getInstallationId(),
                $prediction->getPredictionDate(),
                $prediction->getHour()
            );

            // Update existing
            $existing->setPredictedKwh($prediction->getPredictedKwh());
            $existing->setConfidence($prediction->getConfidence());
            $existing->setModelVersion($prediction->getModelVersion());
            $existing->setCreatedAt(new DateTime());

            return $this->update($existing);
        } catch (DoesNotExistException $e) {
            // Insert new
            $prediction->setCreatedAt(new DateTime());
            return $this->insert($prediction);
        }
    }

    /**
     * Bulk upsert predictions.
     *
     * @param Prediction[] $predictions
     * @return int Number of processed predictions
     */
    public function upsertBatch(array $predictions): int
    {
        $processed = 0;

        foreach ($predictions as $prediction) {
            try {
                $this->upsert($prediction);
                $processed++;
            } catch (\Exception $e) {
                // Log and continue
                continue;
            }
        }

        return $processed;
    }

    /**
     * Get sum of predicted energy for a date range.
     */
    public function sumPredicted(int $installationId, DateTime $startDate, DateTime $endDate): float
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select($qb->createFunction('COALESCE(SUM(predicted_kwh), 0)'))
            ->from($this->getTableName())
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId, IQueryBuilder::PARAM_INT)))
            ->andWhere($qb->expr()->gte('prediction_date', $qb->createNamedParameter($startDate->format('Y-m-d'))))
            ->andWhere($qb->expr()->lte('prediction_date', $qb->createNamedParameter($endDate->format('Y-m-d'))));

        $result = $qb->executeQuery();
        $sum = (float) $result->fetchOne();
        $result->closeCursor();

        return $sum;
    }

    /**
     * Delete old predictions (older than N days).
     */
    public function deleteOlderThan(int $days = 30): int
    {
        $cutoff = (new DateTime())->modify("-{$days} days");

        $qb = $this->db->getQueryBuilder();

        $qb->delete($this->getTableName())
            ->where($qb->expr()->lt('prediction_date', $qb->createNamedParameter($cutoff->format('Y-m-d'))));

        return $qb->executeStatement();
    }

    /**
     * Delete all predictions for an installation.
     */
    public function deleteByInstallation(int $installationId): int
    {
        $qb = $this->db->getQueryBuilder();

        $qb->delete($this->getTableName())
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId, IQueryBuilder::PARAM_INT)));

        return $qb->executeStatement();
    }

    /**
     * Get average confidence for recent predictions.
     */
    public function getAverageConfidence(int $installationId, int $days = 7): float
    {
        $startDate = new DateTime('today');
        $endDate = (new DateTime())->modify("+{$days} days");

        $qb = $this->db->getQueryBuilder();

        $qb->select($qb->createFunction('COALESCE(AVG(confidence), 0)'))
            ->from($this->getTableName())
            ->where($qb->expr()->eq('installation_id', $qb->createNamedParameter($installationId, IQueryBuilder::PARAM_INT)))
            ->andWhere($qb->expr()->gte('prediction_date', $qb->createNamedParameter($startDate->format('Y-m-d'))))
            ->andWhere($qb->expr()->lte('prediction_date', $qb->createNamedParameter($endDate->format('Y-m-d'))));

        $result = $qb->executeQuery();
        $avg = (float) $result->fetchOne();
        $result->closeCursor();

        return $avg;
    }
}
