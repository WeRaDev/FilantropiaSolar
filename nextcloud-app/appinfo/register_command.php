<?php

declare(strict_types=1);

/**
 * Register occ commands for the FilantropiaSolar app.
 *
 * Nextcloud 28's IRegistrationContext has no registerCommand(); occ loads this
 * file and passes the console $application, so commands are added here with
 * their dependencies resolved from the server container.
 */

use OCA\FilantropiaSolar\Command\ImportDataset;
use OCA\FilantropiaSolar\Db\InstallationMapper;
use OCP\Http\Client\IClientService;
use OCP\Server;

/** @var \Symfony\Component\Console\Application $application */
$application->add(new ImportDataset(
    Server::get(InstallationMapper::class),
    Server::get(IClientService::class),
));
