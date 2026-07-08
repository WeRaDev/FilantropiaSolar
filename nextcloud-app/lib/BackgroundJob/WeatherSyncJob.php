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
            // Get unique locations from all installations
            $locations = $this->mapper->getUniqueLocations();

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
     * Sync weather data for a specific location.
     */
    private function syncLocationWeather(string $location): void
    {
        $now = new DateTime();
        $start = (clone $now)->modify('-24 hours');
        $end = (clone $now)->modify('+7 days');

        // Fetch weather data
        $weatherData = $this->weatherService->getHourlyWeather(
            $location,
            $start,
            $end,
            preferHistorical: false
        );

        if ($weatherData === null) {
            throw new \RuntimeException("Failed to fetch weather for {$location}");
        }

        // Store in cache table (optional - for faster access)
        // The WeatherService already caches internally, but we could
        // persist to a dedicated table for historical analysis

        $this->logger->debug('Synced weather for location', [
            'location' => $location,
            'hours' => count($weatherData['hourly'] ?? []),
        ]);
    }
}
