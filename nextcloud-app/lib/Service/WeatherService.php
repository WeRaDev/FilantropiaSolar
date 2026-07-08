<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Service;

use DateTime;
use OCA\FilantropiaSolar\AppInfo\Application;
use OCP\Http\Client\IClientService;
use OCP\ICache;
use OCP\ICacheFactory;
use Psr\Log\LoggerInterface;

/**
 * Weather Service
 *
 * Integrates with Open-Meteo API for weather data.
 * Portuguese location coordinates inherited from Python v1.2.x WeatherSimulator.
 */
class WeatherService
{
    private const OPENMETEO_FORECAST_URL = 'https://api.open-meteo.com/v1/forecast';
    private const OPENMETEO_ARCHIVE_URL = 'https://archive-api.open-meteo.com/v1/archive';

    /**
     * Portuguese location coordinates.
     * Inherited from Python weather_simulator.py location_coords.
     */
    private const LOCATION_COORDS = [
        'Lisbon' => ['lat' => 38.7223, 'lon' => -9.1393],
        'Setubal' => ['lat' => 38.5244, 'lon' => -8.8882],
        'Faro' => ['lat' => 37.0194, 'lon' => -7.9304],
        'Braga' => ['lat' => 41.5454, 'lon' => -8.4265],
        'Tavira' => ['lat' => 37.1279, 'lon' => -7.6486],
        'Loule' => ['lat' => 37.1376, 'lon' => -8.0197],
    ];

    /**
     * Required hourly weather variables.
     */
    private const HOURLY_VARIABLES = [
        'temperature_2m',
        'relative_humidity_2m',
        'cloud_cover',
        'wind_speed_10m',
        'shortwave_radiation',
    ];

    private ICache $cache;

    public function __construct(
        private readonly IClientService $clientService,
        private readonly ICacheFactory $cacheFactory,
        private readonly LoggerInterface $logger,
    ) {
        $this->cache = $this->cacheFactory->createDistributed('filantropia_solar_weather');
    }

    /**
     * Get available Portuguese locations.
     *
     * @return array<string, array{lat: float, lon: float}>
     */
    public function getAvailableLocations(): array
    {
        return self::LOCATION_COORDS;
    }

    /**
     * Find nearest known location to given coordinates.
     *
     * @param float $lat Latitude
     * @param float $lon Longitude
     * @return string Location name
     */
    public function findNearestLocation(float $lat, float $lon): string
    {
        $minDist = PHP_FLOAT_MAX;
        $nearest = 'Lisbon';

        foreach (self::LOCATION_COORDS as $name => $coords) {
            $dist = $this->haversineDistance($lat, $lon, $coords['lat'], $coords['lon']);
            if ($dist < $minDist) {
                $minDist = $dist;
                $nearest = $name;
            }
        }

        return $nearest;
    }

    /**
     * Get hourly weather data for a location.
     *
     * @param string $location Location name (must be in LOCATION_COORDS)
     * @param DateTime $start Start date
     * @param DateTime $end End date
     * @param bool $preferHistorical Use archive API if date is in past
     * @return array|null Weather data or null on failure
     */
    public function getHourlyWeather(
        string $location,
        DateTime $start,
        DateTime $end,
        bool $preferHistorical = true,
    ): ?array {
        if (!isset(self::LOCATION_COORDS[$location])) {
            $this->logger->warning('Unknown location requested', ['location' => $location]);
            return null;
        }

        $coords = self::LOCATION_COORDS[$location];
        return $this->fetchWeatherData($coords['lat'], $coords['lon'], $start, $end, $preferHistorical);
    }

    /**
     * Get hourly weather data by coordinates.
     *
     * @param float $lat Latitude
     * @param float $lon Longitude
     * @param DateTime $start Start date
     * @param DateTime $end End date
     * @param bool $preferHistorical Use archive API if date is in past
     * @return array|null Weather data or null on failure
     */
    public function getHourlyWeatherByCoords(
        float $lat,
        float $lon,
        DateTime $start,
        DateTime $end,
        bool $preferHistorical = true,
    ): ?array {
        return $this->fetchWeatherData($lat, $lon, $start, $end, $preferHistorical);
    }

    /**
     * Fetch weather data from Open-Meteo API.
     */
    private function fetchWeatherData(
        float $lat,
        float $lon,
        DateTime $start,
        DateTime $end,
        bool $preferHistorical,
    ): ?array {
        $now = new DateTime();
        $useArchive = $preferHistorical && $end <= $now;
        $baseUrl = $useArchive ? self::OPENMETEO_ARCHIVE_URL : self::OPENMETEO_FORECAST_URL;
        $source = $useArchive ? 'archive' : 'forecast';

        // Check cache
        $cacheKey = sprintf(
            'weather_%s_%.4f_%.4f_%s_%s',
            $source,
            $lat,
            $lon,
            $start->format('Ymd'),
            $end->format('Ymd')
        );

        $cached = $this->cache->get($cacheKey);
        if ($cached !== null) {
            // For forecast, check freshness (max 3 hours old)
            if ($source === 'forecast') {
                $cachedAt = $cached['_cached_at'] ?? 0;
                if ((time() - $cachedAt) > 3 * 3600) {
                    $cached = null; // Stale, refetch
                }
            }
            if ($cached !== null) {
                unset($cached['_cached_at']);
                return $cached;
            }
        }

        try {
            $client = $this->clientService->newClient();
            $response = $client->get($baseUrl, [
                'query' => [
                    'latitude' => $lat,
                    'longitude' => $lon,
                    'hourly' => implode(',', self::HOURLY_VARIABLES),
                    'start_date' => $start->format('Y-m-d'),
                    'end_date' => $end->format('Y-m-d'),
                    'timezone' => 'auto',
                ],
                'timeout' => 20,
            ]);

            if ($response->getStatusCode() !== 200) {
                $this->logger->warning('Open-Meteo API error', [
                    'status' => $response->getStatusCode(),
                ]);
                return null;
            }

            $data = json_decode($response->getBody(), true);
            $normalized = $this->normalizeWeatherData($data);

            if ($normalized) {
                // Cache with timestamp
                $normalized['_cached_at'] = time();
                $this->cache->set($cacheKey, $normalized, $useArchive ? 86400 : 3600);
                unset($normalized['_cached_at']);
            }

            return $normalized;

        } catch (\Exception $e) {
            $this->logger->error('Failed to fetch weather data', [
                'lat' => $lat,
                'lon' => $lon,
                'exception' => $e,
            ]);
            return null;
        }
    }

    /**
     * Normalize Open-Meteo response to standard format.
     */
    private function normalizeWeatherData(array $data): ?array
    {
        if (!isset($data['hourly']['time'])) {
            return null;
        }

        $hourly = $data['hourly'];
        $times = $hourly['time'];
        $result = [];

        foreach ($times as $i => $time) {
            $entry = ['timestamp' => $time];
            foreach (self::HOURLY_VARIABLES as $var) {
                $value = $hourly[$var][$i] ?? null;
                // Apply sanity bounds
                $entry[$var] = match ($var) {
                    'relative_humidity_2m', 'cloud_cover' => $value !== null ? max(0, min(100, $value)) : null,
                    'wind_speed_10m', 'shortwave_radiation' => $value !== null ? max(0, $value) : null,
                    default => $value,
                };
            }
            $result[] = $entry;
        }

        return [
            'location' => [
                'latitude' => $data['latitude'] ?? null,
                'longitude' => $data['longitude'] ?? null,
                'timezone' => $data['timezone'] ?? null,
            ],
            'hourly' => $result,
        ];
    }

    /**
     * Calculate Haversine distance between two coordinates in km.
     */
    private function haversineDistance(float $lat1, float $lon1, float $lat2, float $lon2): float
    {
        $earthRadius = 6371; // km

        $dLat = deg2rad($lat2 - $lat1);
        $dLon = deg2rad($lon2 - $lon1);

        $a = sin($dLat / 2) * sin($dLat / 2) +
             cos(deg2rad($lat1)) * cos(deg2rad($lat2)) *
             sin($dLon / 2) * sin($dLon / 2);

        $c = 2 * atan2(sqrt($a), sqrt(1 - $a));

        return $earthRadius * $c;
    }
}
