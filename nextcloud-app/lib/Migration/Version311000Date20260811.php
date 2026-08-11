<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Migration;

use Closure;
use OCP\DB\ISchemaWrapper;
use OCP\DB\QueryBuilder\IQueryBuilder;
use OCP\DB\Types;
use OCP\IDBConnection;
use OCP\Migration\IOutput;
use OCP\Migration\SimpleMigrationStep;
use OCP\Server;

/**
 * MVP-1: station lifecycle model (D3/D4).
 *
 * Adds lifecycle_state, soft_removed, odoo_lead_id, installed_at and backfills
 * existing rows: dataset -> running, virtual/user -> virtual.
 */
class Version311000Date20260811 extends SimpleMigrationStep
{
	/**
	 * @param Closure(): ISchemaWrapper $schemaClosure
	 */
	public function changeSchema(IOutput $output, Closure $schemaClosure, array $options): ?ISchemaWrapper
	{
		/** @var ISchemaWrapper $schema */
		$schema = $schemaClosure();

		if (!$schema->hasTable('fs_installations')) {
			return $schema;
		}

		$table = $schema->getTable('fs_installations');

		if (!$table->hasColumn('lifecycle_state')) {
			$table->addColumn('lifecycle_state', Types::STRING, [
				'notnull' => false,
				'length' => 16,
				'default' => 'running',
			]);
		}

		if (!$table->hasColumn('soft_removed')) {
			$table->addColumn('soft_removed', Types::BOOLEAN, [
				'notnull' => false,
				'default' => 0,
			]);
		}

		if (!$table->hasColumn('odoo_lead_id')) {
			$table->addColumn('odoo_lead_id', Types::INTEGER, [
				'notnull' => false,
			]);
		}

		if (!$table->hasColumn('installed_at')) {
			$table->addColumn('installed_at', Types::DATETIME, [
				'notnull' => false,
			]);
		}

		if (!$table->hasIndex('fs_inst_odoo_lead_uniq')) {
			$table->addUniqueIndex(['odoo_lead_id'], 'fs_inst_odoo_lead_uniq');
		}

		if (!$table->hasIndex('fs_inst_lifecycle_idx')) {
			$table->addIndex(['lifecycle_state', 'soft_removed'], 'fs_inst_lifecycle_idx');
		}

		return $schema;
	}

	public function postSchemaChange(IOutput $output, Closure $schemaClosure, array $options): void
	{
		/** @var IDBConnection $db */
		$db = Server::get(IDBConnection::class);

		// Dataset stations -> running (Existing).
		$qb = $db->getQueryBuilder();
		$qb->update('fs_installations')
			->set('lifecycle_state', $qb->createNamedParameter('running'))
			->set('soft_removed', $qb->createNamedParameter(0, IQueryBuilder::PARAM_INT))
			->where($qb->expr()->eq('source', $qb->createNamedParameter('dataset')));
		$qb->executeStatement();

		// Explicit virtual flag -> virtual.
		$qbV = $db->getQueryBuilder();
		$qbV->update('fs_installations')
			->set('lifecycle_state', $qbV->createNamedParameter('virtual'))
			->set('soft_removed', $qbV->createNamedParameter(0, IQueryBuilder::PARAM_INT))
			->where($qbV->expr()->eq('is_virtual', $qbV->createNamedParameter(1, IQueryBuilder::PARAM_INT)));
		$qbV->executeStatement();

		// User-owned rows -> virtual (CRM/user created).
		$qbU = $db->getQueryBuilder();
		$qbU->update('fs_installations')
			->set('lifecycle_state', $qbU->createNamedParameter('virtual'))
			->set('soft_removed', $qbU->createNamedParameter(0, IQueryBuilder::PARAM_INT))
			->where($qbU->expr()->eq('source', $qbU->createNamedParameter('user')));
		$qbU->executeStatement();

		// CRM-origin rows already planned stay if set later; null state -> running.
		$qb3 = $db->getQueryBuilder();
		$qb3->update('fs_installations')
			->set('lifecycle_state', $qb3->createNamedParameter('running'))
			->where($qb3->expr()->isNull('lifecycle_state'));
		$qb3->executeStatement();

		$qb4 = $db->getQueryBuilder();
		$qb4->update('fs_installations')
			->set('soft_removed', $qb4->createNamedParameter(0, IQueryBuilder::PARAM_INT))
			->where($qb4->expr()->isNull('soft_removed'));
		$qb4->executeStatement();

		$output->info('Backfilled lifecycle_state and soft_removed on fs_installations');
	}
}
