<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Migration;

use Closure;
use OCP\DB\ISchemaWrapper;
use OCP\DB\Types;
use OCP\Migration\IOutput;
use OCP\Migration\SimpleMigrationStep;

/**
 * Migration to add is_virtual column to fs_installations table.
 *
 * This is needed for virtual (simulated) installations created by users.
 */
class Version300001Date20260205 extends SimpleMigrationStep
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

        // Add is_virtual column to installations table if it doesn't exist
        if ($schema->hasTable('fs_installations')) {
            $table = $schema->getTable('fs_installations');

            if (!$table->hasColumn('is_virtual')) {
                $table->addColumn('is_virtual', Types::BOOLEAN, [
                    'notnull' => false,
                    'default' => 0,
                ]);
            }
        }

        return $schema;
    }
}
