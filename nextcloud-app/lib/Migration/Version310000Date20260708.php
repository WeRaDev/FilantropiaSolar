<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Migration;

use Closure;
use OCP\DB\ISchemaWrapper;
use OCP\DB\Types;
use OCP\Migration\IOutput;
use OCP\Migration\SimpleMigrationStep;

/**
 * Add support for global (dataset-owned) stations.
 *
 * Makes user_id nullable and adds source/from_date/to_date/error_flag/
 * nearest_location columns so the imported Mendeley dataset can live in
 * MariaDB as the canonical station list alongside user-created stations.
 */
class Version310000Date20260708 extends SimpleMigrationStep
{
    /**
     * @param IOutput $output
     * @param Closure(): ISchemaWrapper $schemaClosure
     * @param array $options
     * @return null|ISchemaWrapper
     */
    public function changeSchema(IOutput $output, Closure $schemaClosure, array $options): ?ISchemaWrapper
    {
        /** @var ISchemaWrapper $schema */
        $schema = $schemaClosure();

        if (!$schema->hasTable('fs_installations')) {
            return $schema;
        }

        $table = $schema->getTable('fs_installations');

        // Dataset stations have no owning user.
        if ($table->hasColumn('user_id')) {
            $table->getColumn('user_id')->setNotnull(false);
        }

        if (!$table->hasColumn('source')) {
            $table->addColumn('source', Types::STRING, [
                'notnull' => false,
                'length' => 16,
                'default' => 'user',
            ]);
        }

        if (!$table->hasColumn('from_date')) {
            $table->addColumn('from_date', Types::DATETIME, ['notnull' => false]);
        }

        if (!$table->hasColumn('to_date')) {
            $table->addColumn('to_date', Types::DATETIME, ['notnull' => false]);
        }

        if (!$table->hasColumn('error_flag')) {
            $table->addColumn('error_flag', Types::BOOLEAN, ['notnull' => false, 'default' => 0]);
        }

        if (!$table->hasColumn('nearest_location')) {
            $table->addColumn('nearest_location', Types::STRING, ['notnull' => false, 'length' => 64]);
        }

        return $schema;
    }
}
