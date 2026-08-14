<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\BackgroundJob;

use DateTime;
use OCA\FilantropiaSolar\Db\InstallationMapper;
use OCA\FilantropiaSolar\Service\WeatherService;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\BackgroundJob\TimedJob;
use OCP\IDBConnection;
use Psr\Log\LoggerInterface;

/**
 * Weather Sync Background Job
 *
 * Periodically fetches weather data from Open-Meteo for all installation locations.
 * Runs every 3 hours to keep weather data fresh for predictions.
 */
class WeatherSyncJob extends TimedJob
{
    /**
     * Interval between runs in seconds (3 hours).
     */
    private const INTERVAL_SECONDS = 3 * 60 * 60;

    public function __construct(
        ITimeFactory $time,
        private readonly InstallationMapper $mapper,
        private readonly WeatherService $weatherService,
        private readonly IDBConnection $db,
        private readonly LoggerInterface $logger,
    ) {
        parent::__construct($time);
        $this->setInterval(self::INTERVAL_SECONDS);
    }

    /**
     * Execute the background job.
     *
     * @param mixed $argument Unused argument from job scheduler
     */
    protected function run($argument): void
    {
        $this->logger->info('Starting weather sync job');

        try {
            // Unique weather keys: nearest known city per ops station + labelled locations
            $locations = $this->collectWeatherLocations();

            if (empty($locations)) {
                $this->logger->info('No installations to sync weather for');
                return;
            }

            $synced = 0;
            $failed = 0;

            // Sync weather for each location
            foreach ($locations as $location) {
                try {
                    $this->syncLocationWeather($location);
                    $synced++;
                } catch (\Exception $e) {
                    $this->logger->warning('Failed to sync weather for location', [
                        'location' => $location,
                        'error' => $e->getMessage(),
                    ]);
                    $failed++;
                }
            }

            $this->logger->info('Weather sync completed', [
                'synced' => $synced,
                'failed' => $failed,
            ]);

        } catch (\Exception $e) {
            $this->logger->error('Weather sync job failed', [
                'exception' => $e,
            ]);
        }
    }

    /**
     * @return list<string> Known Open-Meteo location names to warm the cache for.
     */
    private function collectWeatherLocations(): array
    {
        $keys = [];
        try {
            foreach ($this->mapper->findOpsStations() as $station) {
                $lat = (float) $station->getLatitude();
                $lon = (float) $station->getLongitude();
                if ($lat != 0.0 || $lon != 0.0) {
                    $keys[$this->weatherService->findNearestLocation($lat, $lon)] = true;
                }
                $label = trim((string) ($station->getLocation() ?: ''));
                if ($label !== '' && isset($this->weatherService->getAvailableLocations()[$label])) {
                    $keys[$label] = true;
                }
            }
        } catch (\Throwable $e) {
            $this->logger->warning('WeatherSyncJob: ops stations scan failed', ['exception' => $e]);
        }

        // Distinct labels from DB (may include custom names — only keep known cities)
        try {
            $known = $this->weatherService->getAvailableLocations();
            foreach ($this->mapper->getUniqueLocations(null) as $label) {
                if (isset($known[$label])) {
                    $keys[$label] = true;
                }
            }
        } catch (\Throwable $e) {
            $this->logger->warning('WeatherSyncJob: unique locations failed', ['exception' => $e]);
        }

        if ($keys === []) {
            // Always warm Lisbon as baseline
            $keys['Lisbon'] = true;
        }

        return array_keys($keys);
    }

    /**
     * Sync weather data for a specific location.
     */
    private function syncLocationWeather(string $location): void
    {
        $now = new DateTime();
        $start = (clone $now)->modify('-24 hours');
        $end = (clone $now)->modify('+7 days');

        // Fetch weather data (forecast API for mixed past/future window)
        $weatherData = $this->weatherService->getHourlyWeather(
            $location,
            $start,
            $end,
            preferHistorical: false
        );

        if ($weatherData === null) {
            throw new \RuntimeException("Failed to fetch weather for {$location}");
        }

        // WeatherService caches the response; this job warms that cache.
        $hourly = $weatherData['hourly'] ?? [];
        $hours = is_array($hourly) ? count($hourly) : 0;

        $this->logger->debug('Synced weather for location', [
            'location' => $location,
            'hours' => $hours,
        ]);
    }
}
