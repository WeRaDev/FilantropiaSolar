<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Migration;

use Closure;
use OCP\DB\ISchemaWrapper;
use OCP\DB\Types;
use OCP\Migration\IOutput;
use OCP\Migration\SimpleMigrationStep;

/**
 * Add website + short_description for station info/edit (MVP-4 UI).
 */
class Version312000Date20260812 extends SimpleMigrationStep
{
	public function changeSchema(IOutput $output, Closure $schemaClosure, array $options): ?ISchemaWrapper
	{
		/** @var ISchemaWrapper $schema */
		$schema = $schemaClosure();
		if (!$schema->hasTable('fs_installations')) {
			return null;
		}

		$table = $schema->getTable('fs_installations');
		if (!$table->hasColumn('website')) {
			$table->addColumn('website', Types::STRING, [
				'notnull' => false,
				'length' => 512,
				'default' => null,
			]);
		}
		if (!$table->hasColumn('short_description')) {
			$table->addColumn('short_description', Types::TEXT, [
				'notnull' => false,
				'default' => null,
			]);
		}

		return $schema;
	}
}
