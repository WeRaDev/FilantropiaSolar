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

/**
 * Series provenance + station grid connection type (series sim epic).
 *
 * - fs_readings.provenance: measured | simulated (default simulated for legacy rows)
 * - fs_installations.grid_connection_type: on_grid | off_grid (default on_grid)
 * - Seed off-grid: Penedo off-grid, WeRa Global (name match)
 */
class Version320000Date20260813 extends SimpleMigrationStep
{
	public function __construct(
		private readonly IDBConnection $db,
	) {
	}

	public function changeSchema(IOutput $output, Closure $schemaClosure, array $options): ?ISchemaWrapper
	{
		/** @var ISchemaWrapper $schema */
		$schema = $schemaClosure();
		$changed = false;

		if ($schema->hasTable('fs_readings')) {
			$table = $schema->getTable('fs_readings');
			if (!$table->hasColumn('provenance')) {
				$table->addColumn('provenance', Types::STRING, [
					'notnull' => true,
					'length' => 16,
					'default' => 'simulated',
				]);
				$changed = true;
			}
		}

		if ($schema->hasTable('fs_installations')) {
			$table = $schema->getTable('fs_installations');
			if (!$table->hasColumn('grid_connection_type')) {
				$table->addColumn('grid_connection_type', Types::STRING, [
					'notnull' => true,
					'length' => 16,
					'default' => 'on_grid',
				]);
				$changed = true;
			}
		}

		return $changed ? $schema : null;
	}

	public function postSchemaChange(IOutput $output, Closure $schemaClosure, array $options): void
	{
		// Existing reading rows without explicit provenance stay "simulated"
		// until measured upload marks hours as measured (measured always wins).
		/** @var ISchemaWrapper $schema */
		$schema = $schemaClosure();
		if (!$schema->hasTable('fs_installations')) {
			return;
		}

		$offGridNames = [
			'Penedo off-grid',
			'WeRa Global',
		];

		foreach ($offGridNames as $name) {
			$qb = $this->db->getQueryBuilder();
			$qb->update('fs_installations')
				->set('grid_connection_type', $qb->createNamedParameter('off_grid'))
				->where($qb->expr()->eq('name', $qb->createNamedParameter($name)))
				->andWhere($qb->expr()->orX(
					$qb->expr()->neq(
						'grid_connection_type',
						$qb->createNamedParameter('off_grid'),
					),
					$qb->expr()->isNull('grid_connection_type'),
				));
			$updated = $qb->executeStatement();
			if ($updated > 0) {
				$output->info("Seeded grid_connection_type=off_grid for name={$name} ({$updated} row(s))");
			}
		}

		// Also match location containing "Penedo" + off-grid style labels defensively.
		$qb = $this->db->getQueryBuilder();
		$qb->update('fs_installations')
			->set('grid_connection_type', $qb->createNamedParameter('off_grid'))
			->where($qb->expr()->like(
				'name',
				$qb->createNamedParameter('%Penedo%off-grid%'),
				IQueryBuilder::PARAM_STR,
			));
		$qb->executeStatement();
	}
}
