<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Controller;

use OCA\FilantropiaSolar\AppInfo\Application;
use OCA\FilantropiaSolar\Db\EnergyReadingMapper;
use OCA\FilantropiaSolar\Db\Installation;
use OCA\FilantropiaSolar\Db\InstallationMapper;
use OCA\FilantropiaSolar\Service\StationLifecycle;
use OCP\AppFramework\ApiController;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\Attribute\NoCSRFRequired;
use OCP\AppFramework\Http\Attribute\PublicPage;
use OCP\AppFramework\Http\JSONResponse;
use OCP\Http\Client\IClientService;
use OCP\IConfig;
use OCP\IRequest;
use Psr\Log\LoggerInterface;

/**
 * Public read-only API for external consumers (e.g. the Odoo public site).
 *
 * Authenticated by a bearer token stored in app config ('public_api_token'),
 * decoupled from the Nextcloud user session.
 *
 * MVP-3: exposes Planned + Running stations only (never Virtual / soft-removed).
 * Falls back to dataset source listing when lifecycle columns are not migrated yet.
 */
class PublicApiController extends ApiController
{
	/** ML service URL (internal Docker network). */
	private const ML_SERVICE_URL = 'http://filantropia-ml:8501';

	public function __construct(
		IRequest $request,
		private readonly InstallationMapper $mapper,
		private readonly EnergyReadingMapper $readingMapper,
		private readonly IConfig $config,
		private readonly IClientService $clientService,
		private readonly LoggerInterface $logger,
	) {
		parent::__construct(Application::APP_ID, $request);
	}

	/**
	 * List public stations (Existing + Planned).
	 *
	 * GET /api/public/v1/stations
	 */
	#[PublicPage]
	#[NoCSRFRequired]
	public function stations(): JSONResponse
	{
		if (!$this->authorized()) {
			return new JSONResponse(['error' => 'unauthorized'], Http::STATUS_UNAUTHORIZED);
		}

		$rows = $this->loadPublicStations();
		$stations = array_map(fn (Installation $i): array => $this->toPublicStationArray($i), $rows);

		return new JSONResponse([
			'success' => true,
			'stations' => $stations,
			'count' => count($stations),
		]);
	}

	/**
	 * Public aggregate dashboard figures (computed from DB, not ML).
	 *
	 * GET /api/public/v1/dashboard
	 */
	#[PublicPage]
	#[NoCSRFRequired]
	public function dashboard(): JSONResponse
	{
		if (!$this->authorized()) {
			return new JSONResponse(['error' => 'unauthorized'], Http::STATUS_UNAUTHORIZED);
		}

		$rows = $this->loadPublicStations();
		$totalCapacity = 0.0;
		$totalSeriesSavings = 0.0;
		$hasAnySeries = false;
		$locations = [];
		$planned = 0;
		$existing = 0;
		foreach ($rows as $i) {
			$totalCapacity += (float) $i->getCapacityKwp();
			$locations[$i->getLocation()] = true;
			$category = $this->publicCategoryOf($i);
			if ($category === StationLifecycle::PUBLIC_PLANNED) {
				$planned++;
			} elseif ($category === StationLifecycle::PUBLIC_EXISTING) {
				$existing++;
			}
			$stats = $this->seriesStatsFor($i);
			if ($stats['has_series_data']) {
				$hasAnySeries = true;
				$totalSeriesSavings += $stats['total_savings_eur'];
			}
		}

		$payload = [
			'success' => true,
			'station_count' => count($rows),
			'total_capacity_kwp' => round($totalCapacity, 2),
			'locations' => array_keys($locations),
			'planned_count' => $planned,
			'existing_count' => $existing,
		];
		if ($hasAnySeries) {
			$payload['total_money_saved_eur'] = round($totalSeriesSavings, 2);
			$payload['savings_is_indicative'] = false;
			$payload['savings_source'] = 'nc_readings';
		}

		return new JSONResponse($payload);
	}

	/**
	 * Live production/savings estimate for a candidate (virtual) station.
	 * Proxies the ML service. Used by the Odoo public quote flow.
	 *
	 * POST /api/public/v1/estimate  { latitude, longitude, capacity_kwp, location? }
	 */
	#[PublicPage]
	#[NoCSRFRequired]
	public function estimate(): JSONResponse
	{
		if (!$this->authorized()) {
			return new JSONResponse(['error' => 'unauthorized'], Http::STATUS_UNAUTHORIZED);
		}

		$latitude = (float) $this->request->getParam('latitude', 0);
		$longitude = (float) $this->request->getParam('longitude', 0);
		$capacityKwp = (float) $this->request->getParam('capacity_kwp', 0);
		$location = (string) $this->request->getParam('location', '');

		if ($capacityKwp <= 0) {
			return new JSONResponse(['error' => 'capacity_kwp must be positive'], Http::STATUS_BAD_REQUEST);
		}

		try {
			$client = $this->clientService->newClient();
			$response = $client->post(self::ML_SERVICE_URL . '/estimate', [
				'json' => [
					'latitude' => $latitude,
					'longitude' => $longitude,
					'capacity_kwp' => $capacityKwp,
					'location' => $location,
				],
				'timeout' => 30,
			]);
			$data = json_decode((string) $response->getBody(), true);
			return new JSONResponse(['success' => true, 'estimate' => $data]);
		} catch (\Throwable $e) {
			$this->logger->error('Public estimate proxy failed', ['exception' => $e]);
			return new JSONResponse(['success' => false, 'error' => 'estimate unavailable'], Http::STATUS_BAD_GATEWAY);
		}
	}

	/**
	 * Prefer lifecycle-filtered public stations; fall back to dataset-only if
	 * MVP-1 columns are missing (pre-upgrade).
	 *
	 * @return Installation[]
	 */
	private function loadPublicStations(): array
	{
		try {
			return $this->mapper->findPublicStations();
		} catch (\Throwable $e) {
			$this->logger->warning('findPublicStations failed; returning empty (dataset is not public fleet)', [
				'exception' => $e,
			]);
			return [];
		}
	}

	/**
	 * @return array<string, mixed>
	 */
	private function toPublicStationArray(Installation $i): array
	{
		$category = $this->publicCategoryOf($i);
		$stats = $this->seriesStatsFor($i);
		$short = $i->getShortDescription();
		$website = $this->normalizeWebsite($i->getWebsite());

		return [
			'id' => $i->getInstallationId(),
			'name' => $i->getName(),
			'location' => $i->getLocation(),
			'latitude' => (float) $i->getLatitude(),
			'longitude' => (float) $i->getLongitude(),
			'capacity_kwp' => (float) $i->getCapacityKwp(),
			'from_date' => $i->getFromDate()?->format('Y-m-d'),
			'to_date' => $i->getToDate()?->format('Y-m-d'),
			'public_category' => $category,
			'lifecycle_state' => $this->stateOf($i),
			'website' => $website,
			'short_description' => $short !== null && $short !== '' ? $short : null,
			'description' => $short !== null && $short !== '' ? $short : null,
			'total_production_kwh' => $stats['total_production_kwh'],
			'total_savings_eur' => $stats['total_savings_eur'],
			'money_saved_eur' => $stats['money_saved_eur'],
			'has_series_data' => $stats['has_series_data'],
			'savings_is_indicative' => $stats['savings_is_indicative'],
			'grid_price_kwh' => $stats['grid_price_kwh'],
		];
	}

	/**
	 * Series-backed savings when readings exist; else indicative annual estimate.
	 *
	 * @return array{
	 *     total_production_kwh: float,
	 *     total_savings_eur: float,
	 *     money_saved_eur: float,
	 *     has_series_data: bool,
	 *     savings_is_indicative: bool,
	 *     grid_price_kwh: float
	 * }
	 */
	private function seriesStatsFor(Installation $i): array
	{
		$dbId = (int) $i->getId();
		$price = $i->getGridPriceKwh() !== null && $i->getGridPriceKwh() !== ''
			? (float) $i->getGridPriceKwh()
			: (float) Application::DEFAULT_GRID_PRICE;
		$capacity = (float) $i->getCapacityKwp();

		$production = 0.0;
		$count = 0;
		if ($dbId > 0) {
			try {
				$production = $this->readingMapper->sumProductionAll($dbId);
				$count = $this->readingMapper->countByInstallation($dbId);
			} catch (\Throwable $e) {
				$this->logger->warning('Public series stats failed', ['id' => $dbId, 'exception' => $e]);
			}
		}

		if ($count > 0) {
			$seriesSavings = round($production * $price, 4);

			return [
				'total_production_kwh' => round($production, 4),
				'total_savings_eur' => $seriesSavings,
				'money_saved_eur' => $seriesSavings,
				'has_series_data' => true,
				'savings_is_indicative' => false,
				'grid_price_kwh' => $price,
			];
		}

		// Indicative annual savings (Portugal reference yield) until series exist
		$indicative = round($capacity * 1400.0 * $price, 2);

		return [
			'total_production_kwh' => 0.0,
			'total_savings_eur' => 0.0,
			'money_saved_eur' => $indicative,
			'has_series_data' => false,
			'savings_is_indicative' => true,
			'grid_price_kwh' => $price,
		];
	}

	private function stateOf(Installation $i): string
	{
		$state = $i->getLifecycleState();
		if ($state === null || $state === '') {
			return StationLifecycle::defaultStateForNew($i->getIsVirtual(), $i->getSource());
		}

		return $state;
	}

	private function publicCategoryOf(Installation $i): string
	{
		return StationLifecycle::publicCategory($this->stateOf($i), $i->getSoftRemoved());
	}

	/**
	 * Ensure public website URLs are absolute (scheme-prefixed).
	 */
	private function normalizeWebsite(?string $website): ?string
	{
		$website = trim((string) $website);
		if ($website === '') {
			return null;
		}
		if (!preg_match('#^https?://#i', $website)) {
			$website = 'https://' . $website;
		}

		return $website;
	}

	/**
	 * Verify the request bearer token against the configured public API token.
	 */
	private function authorized(): bool
	{
		$expected = (string) $this->config->getAppValue(Application::APP_ID, 'public_api_token', '');
		if ($expected === '') {
			$this->logger->warning('FilantropiaSolar public_api_token is not configured; rejecting public API request');
			return false;
		}

		$header = (string) $this->request->getHeader('Authorization');
		$token = str_starts_with($header, 'Bearer ') ? substr($header, 7) : '';

		return $token !== '' && hash_equals($expected, $token);
	}
}
