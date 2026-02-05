<?php

declare(strict_types=1);

/**
 * PHPUnit Bootstrap for FilantropiaSolar Tests
 *
 * Sets up autoloading and mocks for Nextcloud dependencies.
 */

// Composer autoloader
$composerAutoload = __DIR__ . '/../vendor/autoload.php';
if (file_exists($composerAutoload)) {
    require_once $composerAutoload;
}

// App namespace autoloader
spl_autoload_register(function (string $class): void {
    $prefix = 'OCA\\FilantropiaSolar\\';
    $baseDir = __DIR__ . '/../lib/';

    $len = strlen($prefix);
    if (strncmp($prefix, $class, $len) !== 0) {
        return;
    }

    $relativeClass = substr($class, $len);
    $file = $baseDir . str_replace('\\', '/', $relativeClass) . '.php';

    if (file_exists($file)) {
        require $file;
    }
});

// Mock Nextcloud OCP interfaces for unit testing
// These allow tests to run without a full Nextcloud installation

if (!interface_exists('OCP\IDBConnection')) {
    interface_alias_mock('OCP\IDBConnection');
}

if (!interface_exists('OCP\IRequest')) {
    interface_alias_mock('OCP\IRequest');
}

if (!interface_exists('OCP\Http\Client\IClientService')) {
    interface_alias_mock('OCP\Http\Client\IClientService');
}

if (!interface_exists('OCP\ICacheFactory')) {
    interface_alias_mock('OCP\ICacheFactory');
}

if (!interface_exists('OCP\ICache')) {
    interface_alias_mock('OCP\ICache');
}

if (!interface_exists('Psr\Log\LoggerInterface')) {
    require_once __DIR__ . '/mocks/LoggerInterface.php';
}

/**
 * Create a mock interface if it doesn't exist.
 */
function interface_alias_mock(string $interface): void
{
    $parts = explode('\\', $interface);
    $className = array_pop($parts);
    $namespace = implode('\\', $parts);

    $code = "namespace {$namespace}; interface {$className} {}";
    eval($code);
}
