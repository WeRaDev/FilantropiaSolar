<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Migration;

use Closure;
use OCP\DB\ISchemaWrapper;
use OCP\DB\Types;
use OCP\Migration\IOutput;
use OCP\Migration\SimpleMigrationStep;

/**
 * Initial database schema for FilantropiaSolar v3.0.0
 *
 * Creates tables for:
 * - oc_filantropia_installations: PV installation registry
 * - oc_filantropia_readings: Hourly energy production/consumption data
 * - oc_filantropia_predictions: ML prediction results
 */
class Version300000Date20260115 extends SimpleMigrationStep
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

        // Create installations table
        if (!$schema->hasTable('fs_installations')) {
            $table = $schema->createTable('fs_installations');

            $table->addColumn('id', Types::BIGINT, [
                'autoincrement' => true,
                'notnull' => true,
            ]);
            $table->addColumn('user_id', Types::STRING, [
                'notnull' => true,
                'length' => 64,
            ]);
            $table->addColumn('name', Types::STRING, [
                'notnull' => true,
                'length' => 255,
            ]);
            $table->addColumn('serial_number', Types::STRING, [
                'notnull' => false,
                'length' => 64,
            ]);
            $table->addColumn('location', Types::STRING, [
                'notnull' => true,
                'length' => 255,
            ]);
            $table->addColumn('latitude', Types::DECIMAL, [
                'notnull' => true,
                'precision' => 10,
                'scale' => 8,
            ]);
            $table->addColumn('longitude', Types::DECIMAL, [
                'notnull' => true,
                'precision' => 11,
                'scale' => 8,
            ]);
            $table->addColumn('capacity_kwp', Types::DECIMAL, [
                'notnull' => true,
                'precision' => 10,
                'scale' => 2,
            ]);
            $table->addColumn('connection_power_kwn', Types::DECIMAL, [
                'notnull' => false,
                'precision' => 10,
                'scale' => 2,
            ]);
            $table->addColumn('grid_price_kwh', Types::DECIMAL, [
                'notnull' => false,
                'precision' => 8,
                'scale' => 4,
                'default' => '0.15',
            ]);
            $table->addColumn('installation_date', Types::DATE, [
                'notnull' => false,
            ]);
            $table->addColumn('created_at', Types::DATETIME, [
                'notnull' => true,
            ]);
            $table->addColumn('updated_at', Types::DATETIME, [
                'notnull' => true,
            ]);
            $table->addColumn('is_virtual', Types::BOOLEAN, [
                'notnull' => false,
                'default' => 0,
            ]);

            $table->setPrimaryKey(['id']);
            $table->addIndex(['user_id'], 'fs_inst_user_idx');
            $table->addIndex(['location'], 'fs_inst_loc_idx');
        }

        // Create energy readings table
        if (!$schema->hasTable('fs_readings')) {
            $table = $schema->createTable('fs_readings');

            $table->addColumn('id', Types::BIGINT, [
                'autoincrement' => true,
                'notnull' => true,
            ]);
            $table->addColumn('installation_id', Types::BIGINT, [
                'notnull' => true,
            ]);
            $table->addColumn('timestamp', Types::DATETIME, [
                'notnull' => true,
            ]);
            $table->addColumn('production_kwh', Types::DECIMAL, [
                'notnull' => false,
                'precision' => 10,
                'scale' => 4,
            ]);
            $table->addColumn('consumption_kwh', Types::DECIMAL, [
                'notnull' => false,
                'precision' => 10,
                'scale' => 4,
            ]);
            $table->addColumn('solar_radiation_wm2', Types::DECIMAL, [
                'notnull' => false,
                'precision' => 8,
                'scale' => 2,
            ]);
            $table->addColumn('temperature_c', Types::DECIMAL, [
                'notnull' => false,
                'precision' => 5,
                'scale' => 2,
            ]);
            $table->addColumn('cloud_cover_pct', Types::SMALLINT, [
                'notnull' => false,
            ]);

            $table->setPrimaryKey(['id']);
            $table->addIndex(['installation_id'], 'fs_read_inst_idx');
            $table->addIndex(['timestamp'], 'fs_read_time_idx');
            $table->addUniqueIndex(['installation_id', 'timestamp'], 'fs_read_unique');
        }

        // Create predictions table
        if (!$schema->hasTable('fs_predictions')) {
            $table = $schema->createTable('fs_predictions');

            $table->addColumn('id', Types::BIGINT, [
                'autoincrement' => true,
                'notnull' => true,
            ]);
            $table->addColumn('installation_id', Types::BIGINT, [
                'notnull' => true,
            ]);
            $table->addColumn('prediction_date', Types::DATE, [
                'notnull' => true,
            ]);
            $table->addColumn('hour', Types::SMALLINT, [
                'notnull' => true,
            ]);
            $table->addColumn('predicted_kwh', Types::DECIMAL, [
                'notnull' => false,
                'precision' => 10,
                'scale' => 4,
            ]);
            $table->addColumn('confidence', Types::DECIMAL, [
                'notnull' => false,
                'precision' => 4,
                'scale' => 3,
            ]);
            $table->addColumn('model_version', Types::STRING, [
                'notnull' => false,
                'length' => 32,
            ]);
            $table->addColumn('created_at', Types::DATETIME, [
                'notnull' => true,
            ]);

            $table->setPrimaryKey(['id']);
            $table->addIndex(['installation_id'], 'fs_pred_inst_idx');
            $table->addUniqueIndex(
                ['installation_id', 'prediction_date', 'hour'],
                'fs_pred_unique'
            );
        }

        return $schema;
    }
}
