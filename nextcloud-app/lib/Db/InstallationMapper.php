<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Db;

use OCP\AppFramework\Db\DoesNotExistException;
use OCP\AppFramework\Db\MultipleObjectsReturnedException;
use OCP\AppFramework\Db\QBMapper;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\IDBConnection;

/**
 * Installation Mapper
 *
 * Handles database operations for Installation entities.
 *
 * @extends QBMapper<Installation>
 */
class InstallationMapper extends QBMapper
{
    public function __construct(IDBConnection $db)
    {
        parent::__construct($db, 'fs_installations', Installation::class);
    }

    /**
     * Find installation by ID.
     *
     * @throws DoesNotExistException
     * @throws MultipleObjectsReturnedException
     */
    public function find(int $id): Installation
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select('*')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('id', $qb->createNamedParameter($id, IQueryBuilder::PARAM_INT)));

        return $this->findEntity($qb);
    }

    /**
     * Find installation by ID for specific user.
     *
     * @throws DoesNotExistException
     * @throws MultipleObjectsReturnedException
     */
    public function findByUser(int $id, string $userId): Installation
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select('*')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('id', $qb->createNamedParameter($id, IQueryBuilder::PARAM_INT)))
            ->andWhere($qb->expr()->eq('user_id', $qb->createNamedParameter($userId)));

        return $this->findEntity($qb);
    }

    /**
     * Find all installations for a user.
     *
     * @return Installation[]
     */
    public function findAllByUser(string $userId): array
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select('*')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('user_id', $qb->createNamedParameter($userId)))
            ->orderBy('name', 'ASC');

        return $this->findEntities($qb);
    }

    /**
     * Find all installations (admin view).
     *
     * @return Installation[]
     */
    public function findAll(): array
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select('*')
            ->from($this->getTableName())
            ->orderBy('location', 'ASC')
            ->addOrderBy('name', 'ASC');

        return $this->findEntities($qb);
    }

    /**
     * Find installations by location.
     *
     * @return Installation[]
     */
    public function findByLocation(string $location): array
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select('*')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('location', $qb->createNamedParameter($location)))
            ->orderBy('name', 'ASC');

        return $this->findEntities($qb);
    }

    /**
     * Count installations for a user.
     */
    public function countByUser(string $userId): int
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select($qb->createFunction('COUNT(*)'))
            ->from($this->getTableName())
            ->where($qb->expr()->eq('user_id', $qb->createNamedParameter($userId)));

        $result = $qb->executeQuery();
        $count = (int) $result->fetchOne();
        $result->closeCursor();

        return $count;
    }

    /**
     * Get total capacity for a user (sum of all installations).
     */
    public function getTotalCapacity(string $userId): float
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select($qb->createFunction('SUM(capacity_kwp)'))
            ->from($this->getTableName())
            ->where($qb->expr()->eq('user_id', $qb->createNamedParameter($userId)));

        $result = $qb->executeQuery();
        $total = (float) $result->fetchOne();
        $result->closeCursor();

        return $total;
    }

    /**
     * Get unique locations for a user.
     *
     * @return string[]
     */
    public function getUniqueLocations(string $userId): array
    {
        $qb = $this->db->getQueryBuilder();

        $qb->selectDistinct('location')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('user_id', $qb->createNamedParameter($userId)))
            ->orderBy('location', 'ASC');

        $result = $qb->executeQuery();
        $locations = $result->fetchAll(\PDO::FETCH_COLUMN);
        $result->closeCursor();

        return $locations;
    }

    /**
     * Delete all installations for a user (used when user is deleted).
     */
    public function deleteByUser(string $userId): void
    {
        $qb = $this->db->getQueryBuilder();

        $qb->delete($this->getTableName())
            ->where($qb->expr()->eq('user_id', $qb->createNamedParameter($userId)));

        $qb->executeStatement();
    }

    /**
     * Find all installations by source ('dataset' or 'user').
     *
     * @return Installation[]
     */
    public function findAllBySource(string $source): array
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select('*')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('source', $qb->createNamedParameter($source)))
            ->orderBy('location', 'ASC')
            ->addOrderBy('name', 'ASC');

        return $this->findEntities($qb);
    }

    /**
     * Find a dataset (global) installation by serial number, or null.
     */
    public function findDatasetBySerial(string $serial): ?Installation
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select('*')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('source', $qb->createNamedParameter('dataset')))
            ->andWhere($qb->expr()->eq('serial_number', $qb->createNamedParameter($serial)))
            ->setMaxResults(1);

        try {
            return $this->findEntity($qb);
        } catch (DoesNotExistException $e) {
            return null;
        } catch (MultipleObjectsReturnedException $e) {
            return $this->findEntities($qb)[0];
        }
    }

    /**
     * Find a dataset (global) installation by DB id, or null.
     */
    public function findDatasetById(int $id): ?Installation
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select('*')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('id', $qb->createNamedParameter($id, IQueryBuilder::PARAM_INT)))
            ->andWhere($qb->expr()->eq('source', $qb->createNamedParameter('dataset')))
            ->setMaxResults(1);

        try {
            return $this->findEntity($qb);
        } catch (DoesNotExistException $e) {
            return null;
        } catch (MultipleObjectsReturnedException $e) {
            return $this->findEntities($qb)[0];
        }
    }

    /**
     * Count installations by source ('dataset' or 'user').
     */
    public function countBySource(string $source): int
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select($qb->createFunction('COUNT(*)'))
            ->from($this->getTableName())
            ->where($qb->expr()->eq('source', $qb->createNamedParameter($source)));

        $result = $qb->executeQuery();
        $count = (int) $result->fetchOne();
        $result->closeCursor();

        return $count;
    }
}
