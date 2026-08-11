<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Controller;

use DateTime;
use OCA\FilantropiaSolar\AppInfo\Application;
use OCA\FilantropiaSolar\Db\Installation;
use OCA\FilantropiaSolar\Db\InstallationMapper;
use OCA\FilantropiaSolar\Service\StationLifecycle;
use OCP\AppFramework\ApiController;
use OCP\AppFramework\Http;
use OCP\AppFramework\Http\Attribute\NoCSRFRequired;
use OCP\AppFramework\Http\Attribute\PublicPage;
use OCP\AppFramework\Http\JSONResponse;
use OCP\IConfig;
use OCP\IRequest;
use Psr\Log\LoggerInterface;

/**
 * Token-authenticated lifecycle write API for Odoo CRM glue (MVP-2 / D1, D4, D7).
 *
 * Routes under /api/lifecycle/v1/* — see docs/architecture/nc-odoo-lifecycle-api.openapi.yaml
 */
class LifecycleApiController extends ApiController
{
	public function __construct(
		IRequest $request,
		private readonly InstallationMapper $mapper,
		private readonly IConfig $config,
		private readonly LoggerInterface $logger,
	) {
		parent::__construct(Application::APP_ID, $request);
	}

	/**
	 * POST /api/lifecycle/v1/stations/virtual
	 */
	#[PublicPage]
	#[NoCSRFRequired]
	public function createVirtual(): JSONResponse
	{
		if (!$this->authorized()) {
			return $this->error('unauthorized', Http::STATUS_UNAUTHORIZED, 'unauthorized');
		}

		$payload = $this->jsonBody();
		$odooLeadId = (int) ($payload['odoo_lead_id'] ?? $this->request->getParam('odoo_lead_id', 0));
		$name = trim((string) ($payload['name'] ?? $this->request->getParam('name', '')));
		$latitude = (float) ($payload['latitude'] ?? $this->request->getParam('latitude', 0));
		$longitude = (float) ($payload['longitude'] ?? $this->request->getParam('longitude', 0));
		$capacityKwp = (float) ($payload['capacity_kwp'] ?? $this->request->getParam('capacity_kwp', 0));
		$locationLabel = trim((string) ($payload['location_label'] ?? $this->request->getParam('location_label', '')));
		$orgName = trim((string) ($payload['organization_name'] ?? $this->request->getParam('organization_name', '')));
		$gridPrice = $payload['grid_price_kwh'] ?? $this->request->getParam('grid_price_kwh', null);

		if ($odooLeadId <= 0) {
			return $this->error('odoo_lead_id is required and must be positive', Http::STATUS_BAD_REQUEST, 'validation_error');
		}
		if ($name === '') {
			return $this->error('name is required', Http::STATUS_BAD_REQUEST, 'validation_error');
		}
		if ($capacityKwp <= 0) {
			return $this->error('capacity_kwp must be positive', Http::STATUS_BAD_REQUEST, 'validation_error');
		}

		$existing = $this->mapper->findByOdooLeadId($odooLeadId);
		if ($existing !== null) {
			return new JSONResponse([
				'success' => true,
				'station' => $this->toLifecycleArray($existing),
				'idempotent' => true,
			]);
		}

		try {
			$station = new Installation();
			$station->setName($name);
			$station->setLocation($locationLabel !== '' ? $locationLabel : 'crm');
			$station->setLatitude((string) $latitude);
			$station->setLongitude((string) $longitude);
			$station->setCapacityKwp((string) $capacityKwp);
			$station->setSerialNumber('lead' . $odooLeadId);
			$station->setSource('crm');
			$station->setUserId(null);
			$station->applyLifecycleState(StationLifecycle::VIRTUAL);
			$station->setSoftRemoved(false);
			$station->setOdooLeadId($odooLeadId);
			if ($gridPrice !== null && $gridPrice !== '') {
				$station->setGridPriceKwh((string) $gridPrice);
			} else {
				$station->setGridPriceKwh((string) Application::DEFAULT_GRID_PRICE);
			}
			if ($orgName !== '') {
				$station->setNearestLocation($orgName);
			}
			$now = new DateTime();
			$station->setCreatedAt($now);
			$station->setUpdatedAt($now);

			$created = $this->mapper->insert($station);
			$this->logger->info('Lifecycle virtual station created', [
				'odoo_lead_id' => $odooLeadId,
				'installation_id' => $created->getInstallationId(),
			]);

			return new JSONResponse([
				'success' => true,
				'station' => $this->toLifecycleArray($created),
				'idempotent' => false,
			], Http::STATUS_CREATED);
		} catch (\Throwable $e) {
			// Race: unique odoo_lead_id — return existing
			$again = $this->mapper->findByOdooLeadId($odooLeadId);
			if ($again !== null) {
				return new JSONResponse([
					'success' => true,
					'station' => $this->toLifecycleArray($again),
					'idempotent' => true,
				]);
			}
			$this->logger->error('Lifecycle virtual create failed', ['exception' => $e]);
			return $this->error('failed to create virtual station', Http::STATUS_INTERNAL_SERVER_ERROR, 'create_failed');
		}
	}

	/**
	 * POST /api/lifecycle/v1/stations/{installationId}/promote-planned
	 */
	#[PublicPage]
	#[NoCSRFRequired]
	public function promotePlanned(string $installationId): JSONResponse
	{
		if (!$this->authorized()) {
			return $this->error('unauthorized', Http::STATUS_UNAUTHORIZED, 'unauthorized');
		}

		$station = $this->mapper->findByInstallationKey($installationId);
		if ($station === null) {
			return $this->error('station not found', Http::STATUS_NOT_FOUND, 'not_found');
		}

		$state = $this->stateOf($station);
		if (!StationLifecycle::canPromoteToPlanned($state, $station->getSoftRemoved())) {
			return $this->error(
				'illegal transition to planned from ' . $state,
				Http::STATUS_CONFLICT,
				'illegal_transition',
			);
		}

		if ($state !== StationLifecycle::PLANNED) {
			$station->applyLifecycleState(StationLifecycle::PLANNED);
			$station->setUpdatedAt(new DateTime());
			$station = $this->mapper->update($station);
			$this->logger->info('Lifecycle promote planned', [
				'installation_id' => $station->getInstallationId(),
			]);
		}

		return new JSONResponse([
			'success' => true,
			'station' => $this->toLifecycleArray($station),
		]);
	}

	/**
	 * POST /api/lifecycle/v1/stations/{installationId}/mark-installed
	 */
	#[PublicPage]
	#[NoCSRFRequired]
	public function markInstalled(string $installationId): JSONResponse
	{
		if (!$this->authorized()) {
			return $this->error('unauthorized', Http::STATUS_UNAUTHORIZED, 'unauthorized');
		}

		$station = $this->mapper->findByInstallationKey($installationId);
		if ($station === null) {
			return $this->error('station not found', Http::STATUS_NOT_FOUND, 'not_found');
		}

		$state = $this->stateOf($station);
		if (!StationLifecycle::canMarkInstalled($state, $station->getSoftRemoved())) {
			return $this->error(
				'illegal transition to running from ' . $state,
				Http::STATUS_CONFLICT,
				'illegal_transition',
			);
		}

		$payload = $this->jsonBody();
		$installedAtRaw = $payload['installed_at'] ?? $this->request->getParam('installed_at');
		if ($state !== StationLifecycle::RUNNING) {
			$station->applyLifecycleState(StationLifecycle::RUNNING);
			try {
				$station->setInstalledAt(
					$installedAtRaw ? new DateTime((string) $installedAtRaw) : new DateTime(),
				);
			} catch (\Throwable) {
				$station->setInstalledAt(new DateTime());
			}
			$station->setUpdatedAt(new DateTime());
			$station = $this->mapper->update($station);
			$this->logger->info('Lifecycle mark installed', [
				'installation_id' => $station->getInstallationId(),
				'actor' => $payload['actor'] ?? null,
			]);
		}

		return new JSONResponse([
			'success' => true,
			'station' => $this->toLifecycleArray($station),
		]);
	}

	/**
	 * POST /api/lifecycle/v1/stations/{installationId}/soft-remove
	 */
	#[PublicPage]
	#[NoCSRFRequired]
	public function softRemove(string $installationId): JSONResponse
	{
		if (!$this->authorized()) {
			return $this->error('unauthorized', Http::STATUS_UNAUTHORIZED, 'unauthorized');
		}

		$station = $this->mapper->findByInstallationKey($installationId);
		if ($station === null) {
			return $this->error('station not found', Http::STATUS_NOT_FOUND, 'not_found');
		}

		if (!$station->getSoftRemoved()) {
			$station->setSoftRemoved(true);
			$station->setUpdatedAt(new DateTime());
			$station = $this->mapper->update($station);
			$this->logger->info('Lifecycle soft-remove', [
				'installation_id' => $station->getInstallationId(),
			]);
		}

		return new JSONResponse([
			'success' => true,
			'station' => $this->toLifecycleArray($station),
		]);
	}

	/**
	 * GET /api/lifecycle/v1/stations/{installationId}
	 */
	#[PublicPage]
	#[NoCSRFRequired]
	public function show(string $installationId): JSONResponse
	{
		if (!$this->authorized()) {
			return $this->error('unauthorized', Http::STATUS_UNAUTHORIZED, 'unauthorized');
		}

		$station = $this->mapper->findByInstallationKey($installationId);
		if ($station === null) {
			return $this->error('station not found', Http::STATUS_NOT_FOUND, 'not_found');
		}

		return new JSONResponse([
			'success' => true,
			'station' => $this->toLifecycleArray($station),
		]);
	}

	/**
	 * @return array<string, mixed>
	 */
	private function toLifecycleArray(Installation $station): array
	{
		$state = $this->stateOf($station);
		$soft = $station->getSoftRemoved();

		return [
			'id' => $station->getId(),
			'installation_id' => $station->getInstallationId(),
			'lifecycle_state' => $state,
			'running_mode' => StationLifecycle::runningMode($state, false),
			'is_public' => StationLifecycle::isPublic($state, $soft),
			'public_category' => StationLifecycle::publicCategory($state, $soft),
			'soft_removed' => $soft,
			'odoo_lead_id' => $station->getOdooLeadId(),
			'capacity_kwp' => (float) $station->getCapacityKwp(),
			'latitude' => (float) $station->getLatitude(),
			'longitude' => (float) $station->getLongitude(),
			'name' => $station->getName(),
			'location' => $station->getLocation(),
			'source' => $station->getSource(),
			'installed_at' => $station->getInstalledAt()?->format('c'),
		];
	}

	private function stateOf(Installation $station): string
	{
		$state = $station->getLifecycleState();
		if ($state === null || $state === '') {
			return StationLifecycle::defaultStateForNew($station->getIsVirtual(), $station->getSource());
		}

		return $state;
	}

	/**
	 * @return array<string, mixed>
	 */
	private function jsonBody(): array
	{
		$params = $this->request->getParams();
		if (is_array($params) && $params !== []) {
			// Drop framework routing keys when present
			unset($params['_route']);
			return $params;
		}
		$raw = file_get_contents('php://input');
		if ($raw === false || $raw === '') {
			return [];
		}
		$data = json_decode($raw, true);

		return is_array($data) ? $data : [];
	}

	private function authorized(): bool
	{
		$expected = (string) $this->config->getAppValue(Application::APP_ID, 'lifecycle_api_token', '');
		if ($expected === '') {
			// Fall back to public_api_token for single-token deploys
			$expected = (string) $this->config->getAppValue(Application::APP_ID, 'public_api_token', '');
		}
		if ($expected === '') {
			$this->logger->warning('FilantropiaSolar lifecycle/public API token not configured');
			return false;
		}

		$header = (string) $this->request->getHeader('Authorization');
		$token = str_starts_with($header, 'Bearer ') ? substr($header, 7) : '';

		return $token !== '' && hash_equals($expected, $token);
	}

	private function error(string $message, int $status, string $code = 'error'): JSONResponse
	{
		return new JSONResponse([
			'success' => false,
			'error' => $message,
			'code' => $code,
		], $status);
	}
}
