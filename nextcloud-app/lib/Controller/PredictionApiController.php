<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Controller;

use DateInterval;
use DateTime;
use DateTimeImmutable;
use DateTimeZone;
use OCA\FilantropiaSolar\AppInfo\Application;
use OCA\FilantropiaSolar\Db\EnergyReading;
use OCA\FilantropiaSolar\Db\EnergyReadingMapper;
use OCA\FilantropiaSolar\Db\InstallationMapper;
use OCA\FilantropiaSolar\Service\PredictionService;
use OCA\FilantropiaSolar\Service\AppTimezone;
use OCA\FilantropiaSolar\Service\SeriesSimulationService;
use OCA\FilantropiaSolar\Service\StationLifecycle;
use OCA\FilantropiaSolar\Service\WeatherService;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\Attribute\NoAdminRequired;
use OCP\AppFramework\Http\Attribute\NoCSRFRequired;
use OCP\AppFramework\Http\JSONResponse;
use OCP\AppFramework\OCSController;
use OCP\Http\Client\IClientService;
use OCP\IRequest;
use Psr\Log\LoggerInterface;

/**
 * Prediction API Controller
 *
 * Provides endpoints for ML-based energy predictions and NC historical series.
 */
class PredictionApiController extends OCSController
{
    /** ML Service URL (internal Docker network) */
    private const ML_SERVICE_URL = 'http://filantropia-ml:8501';

    public function __construct(
        IRequest $request,
        private readonly PredictionService $predictionService,
        private readonly InstallationMapper $installationMapper,
        private readonly EnergyReadingMapper $readingMapper,
        private readonly WeatherService $weatherService,
        private readonly SeriesSimulationService $seriesSimulationService,
        private readonly IClientService $clientService,
        private readonly LoggerInterface $logger,
        private readonly ?string $userId,
    ) {
        parent::__construct(Application::APP_ID, $request);
    }

    /**
     * Get energy forecast for an installation.
     *
     * @NoAdminRequired
     * @param int $id Installation ID
     * @param int $days Number of days to forecast (default 7)
     * @return JSONResponse
     */
    #[NoAdminRequired]
    public function forecast(int $id, int $days = 7): JSONResponse
    {
        try {
            // Verify ownership
            $installation = $this->installationMapper->find($id);
            if ($installation->getUserId() !== $this->userId) {
                return new JSONResponse(
                    ['error' => 'Not found'],
                    Http::STATUS_NOT_FOUND
                );
            }

            // Check for cached predictions first
            $predictions = $this->predictionService->getCachedPredictions($id, $days);

            // If no predictions or stale, try to generate new ones
            if (empty($predictions) || $this->predictionService->needsRefresh($id)) {
                // Check if ML service is available
                if ($this->predictionService->isHealthy()) {
                    $predictions = $this->predictionService->generatePredictions($id, $days);
                }
            }

            // Calculate summary statistics
            $totalPredicted = 0.0;
            $avgConfidence = 0.0;

            foreach ($predictions as $p) {
                $totalPredicted += $p->getPredictedFloat();
                $avgConfidence += $p->getConfidenceFloat();
            }

            if (count($predictions) > 0) {
                $avgConfidence /= count($predictions);
            }

            return new JSONResponse([
                'forecast' => $predictions,
                'summary' => [
                    'total_predicted_kwh' => round($totalPredicted, 2),
                    'average_confidence' => round($avgConfidence, 3),
                    'days' => $days,
                    'hours' => count($predictions),
                ],
                'ml_status' => $this->predictionService->getServiceStatus(),
            ]);
        } catch (\OCP\AppFramework\Db\DoesNotExistException $e) {
            return new JSONResponse(
                ['error' => 'Installation not found'],
                Http::STATUS_NOT_FOUND
            );
        } catch (\Exception $e) {
            $this->logger->error('Failed to get forecast', ['exception' => $e]);
            return new JSONResponse(
                ['error' => 'Failed to generate forecast'],
                Http::STATUS_INTERNAL_SERVER_ERROR
            );
        }
    }

    /**
     * Trigger new prediction generation for an installation.
     *
     * @NoAdminRequired
     * @param int $id Installation ID
     * @return JSONResponse
     */
    #[NoAdminRequired]
    public function trigger(int $id): JSONResponse
    {
        try {
            // Verify ownership
            $installation = $this->installationMapper->find($id);
            if ($installation->getUserId() !== $this->userId) {
                return new JSONResponse(
                    ['error' => 'Not found'],
                    Http::STATUS_NOT_FOUND
                );
            }

            // Check ML service health
            if (!$this->predictionService->isHealthy()) {
                return new JSONResponse([
                    'success' => false,
                    'error' => 'ML service is not available',
                    'ml_status' => $this->predictionService->getServiceStatus(),
                ], Http::STATUS_SERVICE_UNAVAILABLE);
            }

            // Generate predictions
            $predictions = $this->predictionService->generatePredictions($id);

            return new JSONResponse([
                'success' => true,
                'predictions_generated' => count($predictions),
                'message' => count($predictions) > 0
                    ? 'Predictions generated successfully'
                    : 'No predictions could be generated',
            ]);
        } catch (\OCP\AppFramework\Db\DoesNotExistException $e) {
            return new JSONResponse(
                ['error' => 'Installation not found'],
                Http::STATUS_NOT_FOUND
            );
        } catch (\Exception $e) {
            $this->logger->error('Failed to trigger prediction', ['exception' => $e]);
            return new JSONResponse(
                ['error' => 'Failed to trigger prediction: ' . $e->getMessage()],
                Http::STATUS_INTERNAL_SERVER_ERROR
            );
        }
    }

    /**
     * Get ML service health status.
     *
     * @NoAdminRequired
     * @return JSONResponse
     */
    #[NoAdminRequired]
    public function health(): JSONResponse
    {
        return new JSONResponse([
            'ml_service' => $this->predictionService->getServiceStatus(),
        ]);
    }

    
    /**
     * Generate period analysis.
     *
     * Historical mode for ops stations: NC fs_readings SoT + weather overlay.
     * Predicted / simulated / custom / dataset historical: proxy ML /predict/period.
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function period(): JSONResponse
    {
        try {
            $input = file_get_contents('php://input');
            $requestData = json_decode($input ?: '[]', true);
            if (!is_array($requestData)) {
                $requestData = $this->request->getParams();
            }
            if (!$requestData) {
                return new JSONResponse(
                    ['success' => false, 'error' => 'Invalid request body'],
                    Http::STATUS_BAD_REQUEST
                );
            }

            $mode = (string) ($requestData['mode'] ?? '');
            $centerDate = (string) ($requestData['center_date'] ?? '');
            $days = (int) ($requestData['days'] ?? 1);
            if ($mode === '' || $centerDate === '') {
                return new JSONResponse(
                    ['success' => false, 'error' => 'Mode and center_date are required'],
                    Http::STATUS_BAD_REQUEST
                );
            }

            // Ops historical: serve NC series (never ML Excel) when station resolves in DB
            // and is not a pure Mendeley dataset-only request without NC rows.
            if ($mode === 'historical') {
                $nc = $this->buildNcHistoricalPeriod($requestData, $centerDate, max(1, $days));
                if ($nc !== null) {
                    return new JSONResponse($nc);
                }
            }

            // Predicted/sim: enrich body from NC station so ML never depends on Excel ids
            if (in_array($mode, ['simulated', 'custom', 'predicted'], true)) {
                $requestData = $this->enrichPredictedRequest($requestData);
                // Prefer explicit custom/sim path (not corpus lookup)
                if (($requestData['mode'] ?? '') !== 'custom') {
                    $requestData['mode'] = 'simulated';
                }
            }

            $client = $this->clientService->newClient();
            $response = $client->post(self::ML_SERVICE_URL . '/predict/period', [
                'headers' => ['Content-Type' => 'application/json'],
                'body' => json_encode($requestData),
                'timeout' => 120,
            ]);
            $data = json_decode((string) $response->getBody(), true) ?: [];

            // Retry once as custom if ML still says installation not found
            if (
                empty($data['success'])
                && in_array($mode, ['simulated', 'custom', 'predicted'], true)
            ) {
                $retry = $requestData;
                $retry['mode'] = 'custom';
                if (empty($retry['capacity_kwp'])) {
                    $retry['capacity_kwp'] = 5.0;
                }
                if (empty($retry['location'])) {
                    $retry['location'] = 'Lisbon';
                }
                $response = $client->post(self::ML_SERVICE_URL . '/predict/period', [
                    'headers' => ['Content-Type' => 'application/json'],
                    'body' => json_encode($retry),
                    'timeout' => 120,
                ]);
                $data = json_decode((string) $response->getBody(), true) ?: [];
            }

            // Predicted path: force simulated badge semantics for UI
            if (in_array($mode, ['simulated', 'custom', 'predicted'], true)) {
                $data['mode'] = 'simulated';
                $data['series_label'] = 'SIMULATED';
                $data['data_mode_label'] = 'SIMULATED';
                $data['provenance_mix'] = [
                    'measured' => 0,
                    'simulated' => count($data['hourly_data'] ?? []),
                    'total' => count($data['hourly_data'] ?? []),
                ];
            }
            return new JSONResponse($data);
        } catch (\Exception $e) {
            $this->logger->error('Period prediction failed', ['exception' => $e]);
            return new JSONResponse(
                [
                    'success' => false,
                    'error' => 'Prediction service error: ' . $e->getMessage(),
                ],
                Http::STATUS_INTERNAL_SERVER_ERROR
            );
        }
    }

    /**
     * Build analytics period payload from NC fs_readings (+ weather).
     *
     * @param array<string, mixed> $requestData
     * @return array<string, mixed>|null null if station has no NC series / cannot resolve
     */
    private function buildNcHistoricalPeriod(array $requestData, string $centerDate, int $days): ?array
    {
        $installationId = (string) ($requestData['installation_id'] ?? '');
        $station = null;
        if ($installationId !== '') {
            if (ctype_digit($installationId)) {
                try {
                    $station = $this->installationMapper->find((int) $installationId);
                } catch (\Throwable) {
                    $station = null;
                }
            }
            if ($station === null) {
                $station = $this->installationMapper->findByInstallationKey($installationId);
            }
            // virtual_123
            if ($station === null && str_starts_with($installationId, 'virtual_')) {
                $num = substr($installationId, strlen('virtual_'));
                if (ctype_digit($num)) {
                    try {
                        $station = $this->installationMapper->find((int) $num);
                    } catch (\Throwable) {
                        $station = null;
                    }
                }
            }
        }
        if ($station === null) {
            return null;
        }
        $dbId = (int) $station->getId();
        if ($dbId <= 0) {
            return null;
        }
        // Dataset without any NC rows: fall through to ML Excel path.
        if (($station->getSource() ?: '') === 'dataset'
            && $this->readingMapper->countByInstallation($dbId) === 0) {
            return null;
        }

        try {
            $center = new DateTimeImmutable($centerDate, AppTimezone::zone());
        } catch (\Throwable) {
            return [
                'success' => false,
                'error' => 'Invalid center_date',
            ];
        }

        $half = intdiv(max(1, $days), 2);
        if ($days <= 1) {
            $startDay = $center->setTime(0, 0, 0);
            $endDay = $center->setTime(23, 0, 0);
        } else {
            $startDay = $center->sub(new DateInterval('P' . $half . 'D'))->setTime(0, 0, 0);
            $endDay = $center->add(new DateInterval('P' . $half . 'D'))->setTime(23, 0, 0);
        }

        $lastComplete = AppTimezone::lastCompleteHour();
        // Cap end at last complete hour for fill + read of past series
        $fillEnd = $endDay > $lastComplete ? $lastComplete : $endDay;
        $fillStart = $startDay;
        if ($fillStart > $fillEnd) {
            $fillStart = $fillEnd->setTime(0, 0, 0);
        }

        // On-demand gap-fill for Running ops stations so Historical is not empty
        // before SeriesBackfillJob / SeriesRollForwardJob catch up.
        $state = $station->getLifecycleState() ?: '';
        $source = $station->getSource() ?: '';
        if ($state === StationLifecycle::RUNNING && $source !== 'dataset' && !$station->getSoftRemoved()) {
            try {
                // Prefer a short window around the chart first (faster UX).
                $this->seriesSimulationService->fillRange($station, $fillStart, $fillEnd);
            } catch (\Throwable $e) {
                $this->logger->warning('On-demand series fill failed', [
                    'installation_id' => $dbId,
                    'exception' => $e,
                ]);
            }
        }

        $startDt = DateTime::createFromImmutable($startDay);
        $endDt = DateTime::createFromImmutable($endDay);
        $readings = $this->readingMapper->findByInstallation($dbId, $startDt, $endDt);
        $byHour = [];
        foreach ($readings as $r) {
            $ts = $r->getTimestamp();
            if (!$ts instanceof DateTime) {
                continue;
            }
            // Readings are stored as Europe/Lisbon wall-clock hour keys
            $key = AppTimezone::formatHourKey($ts);
            $byHour[$key] = $r;
        }

        // Weather overlay (best-effort)
        $weatherByHour = [];
        $weatherSource = 'none';
        try {
            $wx = $this->weatherService->getHourlyWeatherByCoords(
                (float) $station->getLatitude(),
                (float) $station->getLongitude(),
                $startDt,
                $endDt,
                preferHistorical: true,
            );
            if (is_array($wx) && !empty($wx['hourly'])) {
                $weatherSource = (string) ($wx['source'] ?? 'api');
                $times = $wx['hourly']['time'] ?? [];
                // normalized shape may differ — handle list of entries
            }
            if (is_array($wx)) {
                // WeatherService normalizeWeatherData returns list under hourly entries
                $hourly = $wx['hourly'] ?? $wx;
                if (isset($hourly[0]) && is_array($hourly[0])) {
                    foreach ($hourly as $row) {
                        $t = (string) ($row['timestamp'] ?? $row['time'] ?? '');
                        if ($t === '') {
                            continue;
                        }
                        try {
                            $dt = new DateTimeImmutable($t);
                            $k = AppTimezone::formatHourKey($dt);
                            $weatherByHour[$k] = $row;
                        } catch (\Throwable) {
                            continue;
                        }
                    }
                    $weatherSource = (string) ($wx['source'] ?? $weatherSource ?: 'api');
                } elseif (isset($hourly['time']) && is_array($hourly['time'])) {
                    $n = count($hourly['time']);
                    for ($i = 0; $i < $n; $i++) {
                        try {
                            $dt = new DateTimeImmutable((string) $hourly['time'][$i]);
                            $k = AppTimezone::formatHourKey($dt);
                            $weatherByHour[$k] = [
                                'temperature' => $hourly['temperature_2m'][$i] ?? null,
                                'temperature_2m' => $hourly['temperature_2m'][$i] ?? null,
                                'cloud_cover' => $hourly['cloud_cover'][$i] ?? null,
                                'humidity' => $hourly['relative_humidity_2m'][$i] ?? null,
                                'relative_humidity_2m' => $hourly['relative_humidity_2m'][$i] ?? null,
                                'wind_speed' => $hourly['wind_speed_10m'][$i] ?? null,
                                'wind_speed_10m' => $hourly['wind_speed_10m'][$i] ?? null,
                                'shortwave_radiation' => $hourly['shortwave_radiation'][$i] ?? null,
                            ];
                        } catch (\Throwable) {
                            continue;
                        }
                    }
                    $weatherSource = 'api';
                }
            }
        } catch (\Throwable $e) {
            $this->logger->debug('NC historical weather overlay failed', ['exception' => $e]);
        }

        $hourly = [];
        $cursor = $startDay;
        $endLimit = $endDay;
        $measured = 0;
        $simulated = 0;
        while ($cursor <= $endLimit) {
            $key = $cursor->format('Y-m-d H:00:00');
            $isFuture = $cursor > $lastComplete;
            $reading = $byHour[$key] ?? null;
            $wx = $weatherByHour[$key] ?? [];

            $production = null;
            $provenance = null;
            if (!$isFuture && $reading !== null) {
                $production = $reading->getProductionFloat();
                $provenance = $reading->getProvenance() ?: EnergyReading::PROVENANCE_SIMULATED;
                if ($provenance === EnergyReading::PROVENANCE_MEASURED) {
                    $measured++;
                } else {
                    $simulated++;
                }
            } elseif (!$isFuture && $reading === null) {
                // Past missing hour: leave null (gap-fill job should fill; do not invent here)
                $production = null;
                $provenance = null;
            } else {
                // True future hour: energy empty, weather may still show
                $production = null;
                $provenance = null;
            }

            $hourly[] = [
                'timestamp' => $cursor->format('Y-m-d\\TH:i:s'),
                'hour' => (int) $cursor->format('G'),
                'production_kwh' => $production,
                'provenance' => $provenance,
                'temperature' => isset($wx['temperature']) ? (float) $wx['temperature']
                    : (isset($wx['temperature_2m']) ? (float) $wx['temperature_2m']
                    : ($reading?->getTemperatureFloat() ?: null)),
                'cloud_cover' => isset($wx['cloud_cover']) ? (float) $wx['cloud_cover']
                    : ($reading?->getCloudCoverPct() !== null ? (float) $reading->getCloudCoverPct() : null),
                'humidity' => isset($wx['humidity']) ? (float) $wx['humidity']
                    : (isset($wx['relative_humidity_2m']) ? (float) $wx['relative_humidity_2m'] : null),
                'wind_speed' => isset($wx['wind_speed']) ? (float) $wx['wind_speed']
                    : (isset($wx['wind_speed_10m']) ? (float) $wx['wind_speed_10m'] : null),
                'shortwave_radiation' => isset($wx['shortwave_radiation']) ? (float) $wx['shortwave_radiation']
                    : ($reading?->getRadiationFloat() ?: null),
            ];
            $cursor = $cursor->add(new DateInterval('PT1H'));
        }

        $total = 0.0;
        foreach ($hourly as $h) {
            if ($h['production_kwh'] !== null) {
                $total += (float) $h['production_kwh'];
            }
        }
        $mixTotal = $measured + $simulated;
        if ($measured > 0 && $simulated > 0) {
            $label = sprintf('MIXED (%d measured / %d simulated)', $measured, $simulated);
            $seriesLabel = 'mixed';
        } elseif ($measured > 0) {
            $label = 'HISTORICAL';
            $seriesLabel = 'historical';
        } elseif ($simulated > 0) {
            $label = 'SIMULATED';
            $seriesLabel = 'simulated';
        } else {
            $label = 'NO SERIES DATA';
            $seriesLabel = 'none';
        }

        $bounds = $this->readingMapper->dateBounds($dbId);

        return [
            'success' => true,
            'mode' => 'historical',
            'series_source' => 'nc_readings',
            'series_label' => $seriesLabel,
            'data_mode_label' => $label,
            'weather_source' => $weatherSource,
            'provenance_mix' => [
                'measured' => $measured,
                'simulated' => $simulated,
                'total' => $mixTotal,
            ],
            'series_from_date' => $bounds['from'],
            'series_to_date' => $bounds['to'],
            'installation_info' => [
                'id' => $station->getInstallationId(),
                'name' => $station->getName(),
                'location' => $station->getLocation(),
                'capacity_kwp' => (float) $station->getCapacityKwp(),
                'db_id' => $dbId,
            ],
            'period_statistics' => [
                'total_production_kwh' => round($total, 4),
                'hours' => count($hourly),
                'days' => $days,
            ],
            'hourly_data' => $hourly,
            'daily_data' => [],
        ];
    }

    /**
     * Fill capacity/location/coords from NC station for Predicted/sim requests.
     *
     * @param array<string, mixed> $requestData
     * @return array<string, mixed>
     */
    private function enrichPredictedRequest(array $requestData): array
    {
        $installationId = (string) ($requestData['installation_id'] ?? '');
        $station = null;
        if ($installationId !== '') {
            if (ctype_digit($installationId)) {
                try {
                    $station = $this->installationMapper->find((int) $installationId);
                } catch (\Throwable) {
                    $station = null;
                }
            }
            if ($station === null) {
                try {
                    $station = $this->installationMapper->findByInstallationKey($installationId);
                } catch (\Throwable) {
                    $station = null;
                }
            }
            if ($station === null && str_starts_with($installationId, 'virtual_')) {
                $num = substr($installationId, strlen('virtual_'));
                if (ctype_digit($num)) {
                    try {
                        $station = $this->installationMapper->find((int) $num);
                    } catch (\Throwable) {
                        $station = null;
                    }
                }
            }
        }

        if ($station !== null) {
            if (empty($requestData['capacity_kwp'])) {
                $requestData['capacity_kwp'] = (float) $station->getCapacityKwp();
            }
            if (empty($requestData['location'])) {
                $requestData['location'] = $station->getLocation() ?: 'Lisbon';
            }
            if (!isset($requestData['latitude']) || $requestData['latitude'] === '' || $requestData['latitude'] === null) {
                $requestData['latitude'] = (float) $station->getLatitude();
            }
            if (!isset($requestData['longitude']) || $requestData['longitude'] === '' || $requestData['longitude'] === null) {
                $requestData['longitude'] = (float) $station->getLongitude();
            }
            // Keep NC db id for traceability; ML sim path ignores corpus lookup
            $requestData['installation_id'] = (string) $station->getId();
        }

        if (empty($requestData['capacity_kwp'])) {
            $requestData['capacity_kwp'] = 5.0;
        }
        if (empty($requestData['location'])) {
            $requestData['location'] = 'Lisbon';
        }

        return $requestData;
    }
}
