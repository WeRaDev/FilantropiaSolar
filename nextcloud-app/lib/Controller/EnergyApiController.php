<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Controller;

use DateTime;
use OCA\FilantropiaSolar\AppInfo\Application;
use OCA\FilantropiaSolar\Db\EnergyReadingMapper;
use OCA\FilantropiaSolar\Db\InstallationMapper;
use OCA\FilantropiaSolar\Service\FilantropiaAccess;
use OCA\FilantropiaSolar\Service\SavingsService;
use OCA\FilantropiaSolar\Service\SeriesSimulationService;
use OCP\AppFramework\Db\DoesNotExistException;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\Attribute\NoAdminRequired;
use OCP\AppFramework\Http\Attribute\NoCSRFRequired;
use OCP\AppFramework\Http\JSONResponse;
use OCP\AppFramework\OCSController;
use OCP\Http\Client\IClientService;
use OCP\IDBConnection;
use OCP\IRequest;
use Psr\Log\LoggerInterface;

/**
 * Energy API Controller — NC series (oc_fs_readings) is SoT for ops stations.
 */
class EnergyApiController extends OCSController
{
	private const ML_SERVICE_URL = 'http://filantropia-ml:8501';

	public function __construct(
		IRequest $request,
		private readonly InstallationMapper $mapper,
		private readonly EnergyReadingMapper $readingMapper,
		private readonly SavingsService $savingsService,
		private readonly IClientService $clientService,
		private readonly IDBConnection $db,
		private readonly LoggerInterface $logger,
		private readonly ?string $userId,
		private readonly SeriesSimulationService $seriesService,
		private readonly FilantropiaAccess $access,
	) {
		parent::__construct(Application::APP_ID, $request);
	}

	/**
	 * Get energy readings for an installation from NC series SoT.
	 * Falls back to ML corpus only for pure dataset stations with no NC rows.
	 *
	 * GET /api/v1/installations/{id}/readings?from=&to=&limit=
	 */
	#[NoAdminRequired]
	#[NoCSRFRequired]
	public function readings(string $id, int $limit = 5000): JSONResponse
	{
		$limit = max(1, min(20000, $limit));
		$fromRaw = (string) $this->request->getParam('from', '');
		$toRaw = (string) $this->request->getParam('to', '');

		$station = $this->resolveStation($id);
		if ($station !== null) {
			$dbId = (int) $station->getId();
			$since = null;
			$until = null;
			try {
				if ($fromRaw !== '') {
					$since = new DateTime($fromRaw . (str_contains($fromRaw, ' ') ? '' : ' 00:00:00'));
				}
				if ($toRaw !== '') {
					$until = new DateTime($toRaw . (str_contains($toRaw, ' ') ? '' : ' 23:59:59'));
				}
			} catch (\Throwable) {
				return new JSONResponse(['error' => 'Invalid from/to'], Http::STATUS_BAD_REQUEST);
			}

			$rows = $this->readingMapper->findByInstallation($dbId, $since, $until);
			// If no explicit window and huge series, take last $limit hours
			if ($since === null && $until === null && count($rows) > $limit) {
				$rows = array_slice($rows, -$limit);
			} elseif (count($rows) > $limit) {
				$rows = array_slice($rows, 0, $limit);
			}

			$cap = (float) $station->getCapacityKwp();
			$price = $station->getGridPriceKwh() !== null && $station->getGridPriceKwh() !== ''
				? (float) $station->getGridPriceKwh()
				: (float) Application::DEFAULT_GRID_PRICE;
			$factor = $station->getSelfConsumptionFactor();
			out = [];
			foreach ($rows as $r) {
                                $ts = $r->getTimestamp();
                                $prod = $r->getProductionFloat();
                                $tempRaw = $r->getTemperatureC();
                                $radRaw = $r->getSolarRadiationWm2();
                                $consRaw = $r->getConsumptionKwh();
                                $out[] = [
                                        'timestamp' => $ts instanceof DateTime ? $ts->format('Y-m-d H:i:s') : (string) $ts,
                                        'production_kwh' => $prod,
                                        'consumption_kwh' => $consRaw !== null && $consRaw !== '' ? (float) $consRaw : null,
                                        'temperature_c' => $tempRaw !== null && $tempRaw !== '' ? (float) $tempRaw : null,
                                        'cloud_cover_pct' => $r->getCloudCoverPct(),
                                        'solar_radiation_wm2' => $radRaw !== null && $radRaw !== '' ? (float) $radRaw : null,
                                        'provenance' => $r->getProvenance() ?: 'simulated',
                                        'capacity_kwp' => $cap,
                                        'grid_price_kwh' => $price,
                                        'grid_connection_type' => $station->getGridConnectionType() ?: 'on_grid',
                                        'self_consumption_factor' => $factor,
                                        'savings_eur' => round($prod * $price * $factor, 6),
                                ];
                        }
			$bounds = $this->readingMapper->dateBounds($dbId);
			return new JSONResponse([
				'success' => true,
				'source' => 'nc_readings',
				'installation' => [
					'id' => $station->getId(),
					'name' => $station->getName(),
					'installation_date' => $station->getInstallationDate()?->format('Y-m-d'),
					'capacity_kwp' => $cap,
					'grid_price_kwh' => $price,
					'grid_connection_type' => $station->getGridConnectionType() ?: 'on_grid',
				],
				'series_from_date' => $bounds['from'],
				'series_to_date' => $bounds['to'],
				'readings' => $out,
				'count' => count($out),
			]);
		}

		// Dataset / unknown: optional ML proxy
		try {
			$client = $this->clientService->newClient();
			$url = self::ML_SERVICE_URL . '/data/installations/' . urlencode($id) . '/readings';
			$response = $client->get($url, ['query' => ['limit' => $limit]]);
			$data = json_decode((string) $response->getBody(), true) ?: [];
			$data['source'] = $data['source'] ?? 'ml_corpus';
			return new JSONResponse($data);
		} catch (\Exception $e) {
			$this->logger->error('Failed to fetch readings', ['id' => $id, 'exception' => $e]);
			return new JSONResponse(['success' => true, 'readings' => [], 'count' => 0, 'source' => 'none']);
		}
	}

	#[NoAdminRequired]
	#[NoCSRFRequired]
	public function stats(string $id): JSONResponse
	{
		try {
			$client = $this->clientService->newClient();
			$url = self::ML_SERVICE_URL . '/installations/' . urlencode($id) . '/stats';
			$response = $client->get($url);
			$data = json_decode((string) $response->getBody(), true);
			return new JSONResponse($data);
		} catch (\Exception $e) {
			$this->logger->error('Failed to fetch stats from ML service', ['id' => $id, 'exception' => $e]);
			return new JSONResponse([
				'success' => false,
				'error' => 'Could not fetch statistics',
				'avg_yearly_production_kwh' => 0,
				'efficiency_kwh_kwp' => 0,
				'total_days' => 0,
			]);
		}
	}

	#[NoAdminRequired]
	public function import(int $id): JSONResponse
	{
		if (!$this->access->canUploadMeasured()) {
			return new JSONResponse(['error' => 'Unauthorized'], Http::STATUS_UNAUTHORIZED);
		}
		try {
			try {
				$installation = $this->mapper->find($id);
			} catch (DoesNotExistException $e) {
				return new JSONResponse(['error' => 'Installation not found'], Http::STATUS_NOT_FOUND);
			}
			$data = $this->request->getParams();
			$readings = $data['readings'] ?? [];
			if (empty($readings) || !is_array($readings)) {
				return new JSONResponse(['error' => 'No readings provided'], Http::STATUS_BAD_REQUEST);
			}
			$result = $this->seriesService->importMeasured((int) $installation->getId(), $readings);
			return new JSONResponse([
				'imported' => $result['imported'],
				'skipped' => $result['skipped'],
				'overwritten_simulated' => $result['overwritten_simulated'],
				'total' => count($readings),
				'provenance' => 'measured',
			]);
		} catch (\Exception $e) {
			$this->logger->error('Failed to import readings', ['exception' => $e]);
			return new JSONResponse(['error' => 'Failed to import readings'], Http::STATUS_INTERNAL_SERVER_ERROR);
		}
	}

	private function resolveStation(string $id): ?\OCA\FilantropiaSolar\Db\Installation
	{
		$id = trim($id);
		if ($id === '') {
			return null;
		}
		foreach (['virtual_', 'crm_'] as $prefix) {
			if (str_starts_with($id, $prefix)) {
				$dbId = (int) substr($id, strlen($prefix));
				if ($dbId > 0) {
					try {
						return $this->mapper->find($dbId);
					} catch (DoesNotExistException) {
						return null;
					}
				}
			}
		}
		if (ctype_digit($id)) {
			try {
				return $this->mapper->find((int) $id);
			} catch (DoesNotExistException) {
			}
		}
		return $this->mapper->findByInstallationKey($id);
	}
}
