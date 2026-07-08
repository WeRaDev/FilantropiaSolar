<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Service;

use DateTime;
use OCA\FilantropiaSolar\Db\Installation;
use OCA\FilantropiaSolar\Db\InstallationMapper;
use OCA\FilantropiaSolar\Db\Prediction;
use OCA\FilantropiaSolar\Db\PredictionMapper;
use OCP\Http\Client\IClientService;
use OCP\IConfig;
use Psr\Log\LoggerInterface;

/**
 * Prediction Service
 *
 * Handles communication with the ML microservice for energy predictions.
 */
class PredictionService
{
    private const DEFAULT_ML_URL = 'http://filantropia-ml:8501';
    private const TIMEOUT_SECONDS = 30;

    public function __construct(
        private readonly IClientService $clientService,
        private readonly IConfig $config,
        private readonly InstallationMapper $installationMapper,
        private readonly PredictionMapper $predictionMapper,
        private readonly WeatherService $weatherService,
        private readonly LoggerInterface $logger,
    ) {
    }

    /**
     * Get ML service URL from config or use default.
     */
    private function getMlServiceUrl(): string
    {
        return $this->config->getAppValue(
            'filantropia_solar',
            'ml_service_url',
            self::DEFAULT_ML_URL
        );
    }

    /**
     * Check if ML service is healthy.
     */
    public function isHealthy(): bool
    {
        try {
            $client = $this->clientService->newClient();
            $response = $client->get(
                $this->getMlServiceUrl() . '/health',
                ['timeout' => 5]
            );

            $data = json_decode($response->getBody(), true);
            return ($data['status'] ?? '') === 'healthy';
        } catch (\Exception $e) {
            $this->logger->warning('ML service health check failed', ['exception' => $e]);
            return false;
        }
    }

    /**
     * Get ML service status information.
     */
    public function getServiceStatus(): array
    {
        try {
            $client = $this->clientService->newClient();
            $response = $client->get(
                $this->getMlServiceUrl() . '/health',
                ['timeout' => 5]
            );

            return json_decode($response->getBody(), true);
        } catch (\Exception $e) {
            return [
                'status' => 'unreachable',
                'error' => $e->getMessage(),
            ];
        }
    }

    /**
     * Generate predictions for an installation.
     *
     * @param int $installationId Installation ID
     * @param int $days Number of days to predict (default 7)
     * @return Prediction[] Generated predictions
     */
    public function generatePredictions(int $installationId, int $days = 7): array
    {
        try {
            $installation = $this->installationMapper->find($installationId);
        } catch (\Exception $e) {
            $this->logger->error('Installation not found for prediction', ['id' => $installationId]);
            throw new \RuntimeException('Installation not found');
        }

        // Get weather data for the prediction period
        $weatherData = $this->getWeatherDataForPrediction($installation, $days);

        if (empty($weatherData)) {
            $this->logger->warning('No weather data available for prediction', ['id' => $installationId]);
            return [];
        }

        // Call ML service
        $mlResponse = $this->callMlService($installation, $weatherData);

        if ($mlResponse === null) {
            return [];
        }

        // Store predictions in database
        return $this->storePredictions($installationId, $mlResponse);
    }

    /**
     * Get weather data for prediction period (combine historical and simulated).
     */
    private function getWeatherDataForPrediction(Installation $installation, int $days): array
    {
        $weatherData = [];
        $lat = (float) $installation->getLatitude();
        $lon = (float) $installation->getLongitude();
        $location = $this->weatherService->findNearestLocation($lat, $lon);

        $startDate = new DateTime('today');
        $endDate = (clone $startDate)->modify("+{$days} days");

        // Try to get real weather forecast first
        try {
            $forecast = $this->weatherService->getForecast($lat, $lon, $days);
            if (!empty($forecast)) {
                return $this->formatWeatherForMl($forecast);
            }
        } catch (\Exception $e) {
            $this->logger->warning('Weather forecast failed, using simulation', ['exception' => $e]);
        }

        // Fall back to weather simulation
        try {
            $simulated = $this->simulateWeather($location, $startDate, $endDate);
            return $simulated;
        } catch (\Exception $e) {
            $this->logger->error('Weather simulation failed', ['exception' => $e]);
            return [];
        }
    }

    /**
     * Call ML microservice /simulate-weather endpoint.
     */
    private function simulateWeather(string $location, DateTime $startDate, DateTime $endDate): array
    {
        try {
            $client = $this->clientService->newClient();
            $response = $client->post(
                $this->getMlServiceUrl() . '/simulate-weather',
                [
                    'timeout' => self::TIMEOUT_SECONDS,
                    'json' => [
                        'location' => $location,
                        'start_date' => $startDate->format('Y-m-d'),
                        'end_date' => $endDate->format('Y-m-d'),
                    ],
                ]
            );

            return json_decode($response->getBody(), true) ?? [];
        } catch (\Exception $e) {
            $this->logger->error('ML weather simulation failed', ['exception' => $e]);
            return [];
        }
    }

    /**
     * Format weather service data for ML service.
     */
    private function formatWeatherForMl(array $forecast): array
    {
        $formatted = [];
        foreach ($forecast as $entry) {
            $formatted[] = [
                'timestamp' => $entry['timestamp'] ?? $entry['time'] ?? '',
                'temperature_2m' => $entry['temperature'] ?? $entry['temperature_2m'] ?? 0,
                'relative_humidity_2m' => $entry['humidity'] ?? $entry['relative_humidity_2m'] ?? 0,
                'cloud_cover' => $entry['cloud_cover'] ?? 0,
                'wind_speed_10m' => $entry['wind_speed'] ?? $entry['wind_speed_10m'] ?? 0,
                'shortwave_radiation' => $entry['radiation'] ?? $entry['shortwave_radiation'] ?? 0,
            ];
        }
        return $formatted;
    }

    /**
     * Call ML microservice /predict endpoint.
     */
    private function callMlService(Installation $installation, array $weatherData): ?array
    {
        try {
            $client = $this->clientService->newClient();
            $response = $client->post(
                $this->getMlServiceUrl() . '/predict',
                [
                    'timeout' => self::TIMEOUT_SECONDS,
                    'json' => [
                        'installation_id' => $installation->getInstallationId(),
                        'weather_data' => $weatherData,
                        'capacity_kwp' => (float) $installation->getCapacityKwp(),
                    ],
                ]
            );

            return json_decode($response->getBody(), true);
        } catch (\Exception $e) {
            $this->logger->error('ML prediction failed', [
                'installation_id' => $installation->getId(),
                'exception' => $e,
            ]);
            return null;
        }
    }

    /**
     * Store ML predictions in database.
     *
     * @return Prediction[]
     */
    private function storePredictions(int $installationId, array $mlResponse): array
    {
        $predictions = [];
        $rawPredictions = $mlResponse['predictions'] ?? [];
        $modelVersion = $mlResponse['model_used'] ?? 'unknown';

        foreach ($rawPredictions as $raw) {
            try {
                $timestamp = new DateTime($raw['timestamp']);
                $date = clone $timestamp;
                $date->setTime(0, 0, 0);
                $hour = (int) $timestamp->format('H');

                $prediction = new Prediction();
                $prediction->setInstallationId($installationId);
                $prediction->setPredictionDate($date);
                $prediction->setHour($hour);
                $prediction->setPredictedKwh((string) ($raw['predicted_kwh'] ?? 0));
                $prediction->setConfidence((string) ($raw['confidence'] ?? 0.8));
                $prediction->setModelVersion($modelVersion);

                $stored = $this->predictionMapper->upsert($prediction);
                $predictions[] = $stored;
            } catch (\Exception $e) {
                $this->logger->warning('Failed to store prediction', ['exception' => $e]);
                continue;
            }
        }

        $this->logger->info('Stored predictions', [
            'installation_id' => $installationId,
            'count' => count($predictions),
        ]);

        return $predictions;
    }

    /**
     * Get cached predictions for an installation.
     *
     * @return Prediction[]
     */
    public function getCachedPredictions(int $installationId, int $days = 7): array
    {
        return $this->predictionMapper->findForecast($installationId, $days);
    }

    /**
     * Check if predictions need refresh (older than threshold).
     */
    public function needsRefresh(int $installationId, int $maxAgeHours = 6): bool
    {
        try {
            $predictions = $this->predictionMapper->findForecast($installationId, 1);

            if (empty($predictions)) {
                return true;
            }

            $latestCreated = $predictions[0]->getCreatedAt();
            $ageHours = (time() - $latestCreated->getTimestamp()) / 3600;

            return $ageHours > $maxAgeHours;
        } catch (\Exception $e) {
            return true;
        }
    }

    /**
     * Generate predictions for all installations that need refresh.
     */
    public function refreshAllPredictions(): int
    {
        $refreshed = 0;
        $installations = $this->installationMapper->findAll();

        foreach ($installations as $installation) {
            if ($this->needsRefresh($installation->getId())) {
                try {
                    $this->generatePredictions($installation->getId());
                    $refreshed++;
                } catch (\Exception $e) {
                    $this->logger->warning('Failed to refresh predictions', [
                        'installation_id' => $installation->getId(),
                        'exception' => $e,
                    ]);
                }
            }
        }

        return $refreshed;
    }
}
