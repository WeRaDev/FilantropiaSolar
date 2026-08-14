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
     * Get unique location labels.
     *
     * @param string|null $userId When set, limit to that user; null = all rows (ops jobs).
     * @return string[]
     */
    public function getUniqueLocations(?string $userId = null): array
    {
        $qb = $this->db->getQueryBuilder();

        $qb->selectDistinct('location')
            ->from($this->getTableName())
            ->orderBy('location', 'ASC');

        if ($userId !== null && $userId !== '') {
            $qb->where($qb->expr()->eq('user_id', $qb->createNamedParameter($userId)));
        }

        $result = $qb->executeQuery();
        $locations = $result->fetchAll(\PDO::FETCH_COLUMN);
        $result->closeCursor();

        return array_values(array_filter(
            array_map(static fn ($v) => is_string($v) ? trim($v) : '', $locations ?: []),
            static fn (string $v): bool => $v !== '',
        ));
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


    /**
     * Ops dashboard stations: everything except Mendeley training corpus (source=dataset).
     * Includes fleet, user, crm, and any future non-dataset sources.
     *
     * @return Installation[]
     */
    public function findOpsStations(): array
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select('*')
            ->from($this->getTableName())
            ->where($qb->expr()->neq('source', $qb->createNamedParameter('dataset')))
            ->orderBy('location', 'ASC')
            ->addOrderBy('name', 'ASC');

        return $this->findEntities($qb);
    }

    /**
     * Public map/list: Planned + Running, not soft-removed, never Virtual.
     *
     * @return Installation[]
     */
    public function findPublicStations(): array
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select('*')
            ->from($this->getTableName())
            ->where($qb->expr()->in(
                'lifecycle_state',
                $qb->createNamedParameter(['planned', 'running'], IQueryBuilder::PARAM_STR_ARRAY),
            ))
            ->andWhere($qb->expr()->orX(
                $qb->expr()->eq('soft_removed', $qb->createNamedParameter(0, IQueryBuilder::PARAM_INT)),
                $qb->expr()->isNull('soft_removed'),
            ))
            // Mendeley training corpus is never public fleet (M0)
            ->andWhere($qb->expr()->neq('source', $qb->createNamedParameter('dataset')))
            ->orderBy('location', 'ASC')
            ->addOrderBy('name', 'ASC');

        return $this->findEntities($qb);
    }

    /**
     * Find by Odoo CRM lead id (idempotent virtual create).
     */
    public function findByOdooLeadId(int $odooLeadId): ?Installation
    {
        $qb = $this->db->getQueryBuilder();

        $qb->select('*')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('odoo_lead_id', $qb->createNamedParameter($odooLeadId, IQueryBuilder::PARAM_INT)))
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
     * Resolve station by public installation_id (location_serial) or numeric DB id.
     */
    public function findByInstallationKey(string $installationId): ?Installation
    {
        $installationId = trim($installationId);
        if ($installationId === '') {
            return null;
        }

        // Numeric DB primary key
        if (ctype_digit($installationId)) {
            try {
                return $this->find((int) $installationId);
            } catch (DoesNotExistException $e) {
                // fall through to location_serial match
            } catch (MultipleObjectsReturnedException $e) {
                return null;
            }
        }

        // location_serial form: "{location}_{serial}" — serial may contain underscores
        $pos = strpos($installationId, '_');
        if ($pos === false) {
            return null;
        }
        $location = substr($installationId, 0, $pos);
        $serial = substr($installationId, $pos + 1);
        if ($location === '' || $serial === '') {
            return null;
        }

        $qb = $this->db->getQueryBuilder();
        $qb->select('*')
            ->from($this->getTableName())
            ->where($qb->expr()->eq('location', $qb->createNamedParameter($location)))
            ->andWhere($qb->expr()->eq('serial_number', $qb->createNamedParameter($serial)))
            ->setMaxResults(1);

        try {
            return $this->findEntity($qb);
        } catch (DoesNotExistException $e) {
            // getInstallationId() falls back to "{location}_{id}" when serial is null.
            if (ctype_digit($serial)) {
                try {
                    $byId = $this->find((int) $serial);
                    if ($byId->getLocation() === $location) {
                        $sn = $byId->getSerialNumber();
                        if ($sn === null || $sn === '') {
                            return $byId;
                        }
                    }
                } catch (DoesNotExistException $e2) {
                    return null;
                } catch (MultipleObjectsReturnedException $e2) {
                    return null;
                }
            }
            return null;
        } catch (MultipleObjectsReturnedException $e) {
            return $this->findEntities($qb)[0];
        }
    }

    /**
     * Find stations by lifecycle state (optional soft-removed filter).
     *
     * @param list<string> $states
     * @return Installation[]
     */
    public function findByLifecycleStates(array $states, bool $includeSoftRemoved = false): array
    {
        if ($states === []) {
            return [];
        }

        $qb = $this->db->getQueryBuilder();

        $qb->select('*')
            ->from($this->getTableName())
            ->where($qb->expr()->in(
                'lifecycle_state',
                $qb->createNamedParameter(array_values($states), IQueryBuilder::PARAM_STR_ARRAY),
            ));

        if (!$includeSoftRemoved) {
            $qb->andWhere($qb->expr()->orX(
                $qb->expr()->eq('soft_removed', $qb->createNamedParameter(0, IQueryBuilder::PARAM_INT)),
                $qb->expr()->isNull('soft_removed'),
            ));
        }

        $qb->orderBy('location', 'ASC')->addOrderBy('name', 'ASC');

        return $this->findEntities($qb);
    }
}
