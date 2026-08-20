<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Migration;

use Closure;
use OCP\DB\ISchemaWrapper;
use OCP\DB\Types;
use OCP\Migration\IOutput;
use OCP\Migration\SimpleMigrationStep;

/**
 * public_archived: running stations counted in stats but hidden from public map.
 */
class Version321000Date20260820 extends SimpleMigrationStep
{
	public function changeSchema(IOutput $output, Closure $schemaClosure, array $options): ?ISchemaWrapper
	{
		/** @var ISchemaWrapper $schema */
		$schema = $schemaClosure();
		if (!$schema->hasTable('fs_installations')) {
			return null;
		}
		$table = $schema->getTable('fs_installations');
		if ($table->hasColumn('public_archived')) {
			return null;
		}
		$table->addColumn('public_archived', Types::BOOLEAN, [
			'notnull' => true,
			'default' => 0,
		]);
		$output->info('Added fs_installations.public_archived');

		return $schema;
	}
}
