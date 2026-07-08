<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Command;

use DateTime;
use OCA\FilantropiaSolar\Db\Installation;
use OCA\FilantropiaSolar\Db\InstallationMapper;
use OCP\Http\Client\IClientService;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Input\InputOption;
use Symfony\Component\Console\Output\OutputInterface;

/**
 * Import the Mendeley PV dataset (station metadata) into MariaDB as global
 * (dataset-owned) stations, making Nextcloud the canonical station list.
 *
 * The metadata is pulled from the ML service (which already parses the Excel),
 * so the Nextcloud container does not need the dataset files mounted. The
 * upsert is idempotent, keyed on serial_number for source='dataset'.
 *
 * Usage: occ filantropia_solar:import-dataset [--ml-url=URL]
 */
class ImportDataset extends Command
{
    private const ML_SERVICE_URL = 'http://filantropia-ml:8501';

    public function __construct(
        private readonly InstallationMapper $mapper,
        private readonly IClientService $clientService,
    ) {
        parent::__construct();
    }

    protected function configure(): void
    {
        $this->setName('filantropia_solar:import-dataset')
            ->setDescription('Import Mendeley PV dataset stations from the ML service into MariaDB as global stations')
            ->addOption(
                'ml-url',
                null,
                InputOption::VALUE_OPTIONAL,
                'Base URL of the ML service',
                self::ML_SERVICE_URL,
            );
    }

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        $mlUrl = rtrim((string) $input->getOption('ml-url'), '/');
        $output->writeln("Fetching dataset installations from {$mlUrl}/data/installations ...");

        try {
            $client = $this->clientService->newClient();
            $response = $client->get($mlUrl . '/data/installations', ['timeout' => 30]);
            $data = json_decode((string) $response->getBody(), true);
        } catch (\Throwable $e) {
            $output->writeln('<error>Failed to reach ML service: ' . $e->getMessage() . '</error>');
            return 1;
        }

        $installations = $data['installations'] ?? [];
        if (!is_array($installations) || count($installations) === 0) {
            $output->writeln('<error>No installations returned by the ML service.</error>');
            return 1;
        }

        $created = 0;
        $updated = 0;

        foreach ($installations as $inst) {
            $serial = (string) ($inst['serial_number'] ?? $inst['id'] ?? '');
            if ($serial === '') {
                continue;
            }

            $existing = $this->mapper->findDatasetBySerial($serial);
            $entity = $existing ?? new Installation();

            $entity->setUserId(null);
            $entity->setSource('dataset');
            $entity->setIsVirtual(false);
            $entity->setName((string) ($inst['name'] ?? ('PV Plant ' . $serial)));
            $entity->setLocation((string) ($inst['location'] ?? 'Unknown'));
            $entity->setNearestLocation(isset($inst['location']) ? (string) $inst['location'] : null);
            $entity->setLatitude((string) ($inst['latitude'] ?? '0'));
            $entity->setLongitude((string) ($inst['longitude'] ?? '0'));
            $entity->setCapacityKwp((string) ($inst['capacity_kwp'] ?? '0'));
            $entity->setConnectionPowerKwn(
                isset($inst['connection_power_kwn']) ? (string) $inst['connection_power_kwn'] : null
            );
            $entity->setSerialNumber($serial);
            $entity->setGridPriceKwh('0.15');
            $entity->setErrorFlag((bool) ($inst['error_flag'] ?? false));

            if (!empty($inst['from_date'])) {
                $entity->setFromDate(new DateTime((string) $inst['from_date']));
            }
            if (!empty($inst['to_date'])) {
                $entity->setToDate(new DateTime((string) $inst['to_date']));
            }

            $now = new DateTime();
            if ($existing) {
                $entity->setUpdatedAt($now);
                $this->mapper->update($entity);
                $updated++;
            } else {
                $entity->setCreatedAt($now);
                $entity->setUpdatedAt($now);
                $this->mapper->insert($entity);
                $created++;
            }

            $output->writeln("  - {$serial} ({$entity->getLocation()}, {$entity->getCapacityKwp()} kWp)");
        }

        $output->writeln("<info>Import complete: {$created} created, {$updated} updated.</info>");
        return 0;
    }
}
