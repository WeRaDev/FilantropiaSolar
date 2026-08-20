<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Controller;

use DateTime;
use OCA\FilantropiaSolar\AppInfo\Application;
use OCA\FilantropiaSolar\Db\Installation;
use OCA\FilantropiaSolar\Db\InstallationMapper;
use OCA\FilantropiaSolar\Service\OdooLifecycleMirror;
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
		private readonly OdooLifecycleMirror $odooMirror,
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
		$website = trim((string) ($payload['website'] ?? $this->request->getParam('website', '')));
		$shortDescription = trim((string) (
			$payload['short_description']
			?? $payload['shortDescription']
			?? $this->request->getParam('short_description', '')
		));
		$gridPrice = $payload['grid_price_kwh'] ?? $this->request->getParam('grid_price_kwh', null);
		$gridConnection = strtolower(trim((string) (
			$payload['grid_connection_type']
			?? $this->request->getParam('grid_connection_type', '')
		)));
		if (!in_array($gridConnection, ['on_grid', 'off_grid'], true)) {
			$gridConnection = '';
		}

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
			// Refresh public snapshot fields on idempotent replay (CRM re-sync).
			$dirty = false;
			if ($website !== '') {
				$existing->setWebsite($website);
				$dirty = true;
			}
			if ($shortDescription !== '') {
				$existing->setShortDescription($shortDescription);
				$dirty = true;
			}
			if ($locationLabel !== '') {
				$existing->setLocation($locationLabel);
				$dirty = true;
			}
			if ($capacityKwp > 0) {
				$existing->setCapacityKwp((string) $capacityKwp);
				$dirty = true;
			}
			if ($latitude != 0.0 || $longitude != 0.0) {
				$existing->setLatitude((string) $latitude);
				$existing->setLongitude((string) $longitude);
				$dirty = true;
			}
			if ($gridConnection !== '') {
				$existing->setGridConnectionType($gridConnection);
				$dirty = true;
			}
			if ($gridPrice !== null && $gridPrice !== '') {
				$existing->setGridPriceKwh((string) $gridPrice);
				$dirty = true;
			}
			if ($name !== '' && $existing->getName() !== $name) {
				$existing->setName($name);
				$dirty = true;
			}
			if ($dirty) {
				$existing->setUpdatedAt(new DateTime());
				$existing = $this->mapper->update($existing);
			}
			// Keep CRM mirror in sync even on idempotent profile refresh.
			$this->notifyOdooMirror($existing);

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
			if ($gridConnection !== '') {
				$station->setGridConnectionType($gridConnection);
			} else {
				$station->setGridConnectionType(Installation::GRID_ON);
			}
			if ($orgName !== '') {
				$station->setNearestLocation($orgName);
			}
			if ($website !== '') {
				$station->setWebsite($website);
			}
			if ($shortDescription !== '') {
				$station->setShortDescription($shortDescription);
			} elseif ($orgName !== '') {
				// Fallback public blurb from organisation name when form description empty
				$station->setShortDescription($orgName);
			}
			$now = new DateTime();
			$station->setCreatedAt($now);
			$station->setUpdatedAt($now);

			$created = $this->mapper->insert($station);
			$this->logger->info('Lifecycle virtual station created', [
				'odoo_lead_id' => $odooLeadId,
				'installation_id' => $created->getInstallationId(),
			]);
			$this->notifyOdooMirror($created);

			return new JSONResponse([
				'success' => true,
				'station' => $this->toLifecycleArray($created),
				'idempotent' => false,
			], Http::STATUS_CREATED);
		} catch (\Throwable $e) {
			// Race: unique odoo_lead_id — return existing
			$again = $this->mapper->findByOdooLeadId($odooLeadId);
			if ($again !== null) {
				$this->notifyOdooMirror($again);
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

		$this->notifyOdooMirror($station);
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

		$this->notifyOdooMirror($station);
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

		$this->notifyOdooMirror($station);
		return new JSONResponse([
			'success' => true,
			'station' => $this->toLifecycleArray($station),
		]);
	}


	/**
	 * GET /api/lifecycle/v1/stations
	 * Ops list for CRM mirror (includes Virtual; excludes soft-removed by default).
	 *
	 * Mendeley training corpus (source=dataset) is excluded by default so CRM
	 * stays symmetrical with the NC ops dashboard. Pass include_dataset=1 only
	 * for diagnostics.
	 */
	#[PublicPage]
	#[NoCSRFRequired]
	public function index(): JSONResponse
	{
		if (!$this->authorized()) {
			return $this->error('unauthorized', Http::STATUS_UNAUTHORIZED, 'unauthorized');
		}

		$includeSoft = filter_var(
			$this->request->getParam('include_soft_removed', '0'),
			FILTER_VALIDATE_BOOLEAN,
		);
		$includeDataset = filter_var(
			$this->request->getParam('include_dataset', '0'),
			FILTER_VALIDATE_BOOLEAN,
		);
		$stations = $includeDataset
			? $this->mapper->findAll()
			: $this->mapper->findOpsStations();
		$out = [];
		foreach ($stations as $station) {
			if (!$includeSoft && $station->getSoftRemoved()) {
				continue;
			}
			// Defense in depth if include_dataset was true but a row is still dataset-only ops view.
			if (!$includeDataset && ($station->getSource() ?: '') === 'dataset') {
				continue;
			}
			$out[] = $this->toLifecycleArray($station);
		}

		return new JSONResponse([
			'success' => true,
			'count' => count($out),
			'stations' => $out,
			'includes_dataset' => $includeDataset,
		]);
	}

	/**
	 * POST /api/lifecycle/v1/stations/{installationId}/bind-lead
	 *
	 * Attach CRM lead id to an existing ops station (fleet/user/crm) so the
	 * mirror is bidirectional by primary key as well as installation_id.
	 */
	#[PublicPage]
	#[NoCSRFRequired]
	public function bindLead(string $installationId): JSONResponse
	{
		if (!$this->authorized()) {
			return $this->error('unauthorized', Http::STATUS_UNAUTHORIZED, 'unauthorized');
		}

		$payload = $this->jsonBody();
		$odooLeadId = (int) ($payload['odoo_lead_id'] ?? $this->request->getParam('odoo_lead_id', 0));
		if ($odooLeadId <= 0) {
			return $this->error('odoo_lead_id is required and must be positive', Http::STATUS_BAD_REQUEST, 'validation_error');
		}

		$station = $this->mapper->findByInstallationKey($installationId);
		if ($station === null) {
			return $this->error('station not found', Http::STATUS_NOT_FOUND, 'not_found');
		}
		if (($station->getSource() ?: '') === 'dataset') {
			return $this->error('dataset stations are not part of the CRM mirror', Http::STATUS_CONFLICT, 'dataset_excluded');
		}

		$current = $station->getOdooLeadId();
		if ($current !== null && (int) $current === $odooLeadId) {
			return new JSONResponse([
				'success' => true,
				'station' => $this->toLifecycleArray($station),
				'idempotent' => true,
			]);
		}
		if ($current !== null && (int) $current !== $odooLeadId) {
			return $this->error(
				'station already bound to a different odoo_lead_id',
				Http::STATUS_CONFLICT,
				'already_bound',
			);
		}

		$existing = $this->mapper->findByOdooLeadId($odooLeadId);
		if ($existing !== null && (int) $existing->getId() !== (int) $station->getId()) {
			return $this->error(
				'odoo_lead_id already linked to another station',
				Http::STATUS_CONFLICT,
				'lead_already_linked',
			);
		}

		$station->setOdooLeadId($odooLeadId);
		$station->setUpdatedAt(new DateTime());
		$station = $this->mapper->update($station);
		$this->logger->info('Lifecycle bind odoo_lead_id', [
			'installation_id' => $station->getInstallationId(),
			'odoo_lead_id' => $odooLeadId,
		]);

		return new JSONResponse([
			'success' => true,
			'station' => $this->toLifecycleArray($station),
			'idempotent' => false,
		]);
	}


	/**
	 * POST /api/lifecycle/v1/stations/{installationId}/profile
	 *
	 * Update public station snapshot fields from CRM (name, location, coords,
	 * capacity, website, short_description). Does not change lifecycle_state.
	 */
	#[PublicPage]
	#[NoCSRFRequired]
	public function updateProfile(string $installationId): JSONResponse
	{
		if (!$this->authorized()) {
			return $this->error('unauthorized', Http::STATUS_UNAUTHORIZED, 'unauthorized');
		}

		$station = $this->mapper->findByInstallationKey($installationId);
		if ($station === null) {
			return $this->error('station not found', Http::STATUS_NOT_FOUND, 'not_found');
		}
		if (($station->getSource() ?: '') === 'dataset') {
			return $this->error('dataset stations are not part of the CRM mirror', Http::STATUS_CONFLICT, 'dataset_excluded');
		}

		$payload = $this->jsonBody();
		$dirty = false;

		if (array_key_exists('name', $payload)) {
			$name = trim((string) $payload['name']);
			if ($name !== '') {
				$station->setName($name);
				$dirty = true;
			}
		}
		if (array_key_exists('location_label', $payload) || array_key_exists('location', $payload)) {
			$loc = trim((string) ($payload['location_label'] ?? $payload['location'] ?? ''));
			if ($loc !== '') {
				$station->setLocation($loc);
				$dirty = true;
			}
		}
		if (array_key_exists('latitude', $payload) || array_key_exists('longitude', $payload)) {
			$lat = (float) ($payload['latitude'] ?? $station->getLatitude());
			$lng = (float) ($payload['longitude'] ?? $station->getLongitude());
			$station->setLatitude((string) $lat);
			$station->setLongitude((string) $lng);
			$dirty = true;
		}
		if (array_key_exists('capacity_kwp', $payload)) {
			$cap = (float) $payload['capacity_kwp'];
			if ($cap > 0) {
				$station->setCapacityKwp((string) $cap);
				$dirty = true;
			}
		}
		if (array_key_exists('website', $payload)) {
			$website = trim((string) $payload['website']);
			$station->setWebsite($website !== '' ? $website : null);
			$dirty = true;
		}
		if (array_key_exists('short_description', $payload) || array_key_exists('shortDescription', $payload)) {
			$short = trim((string) ($payload['short_description'] ?? $payload['shortDescription'] ?? ''));
			$station->setShortDescription($short !== '' ? $short : null);
			$dirty = true;
		}
		if (array_key_exists('grid_price_kwh', $payload) && $payload['grid_price_kwh'] !== null && $payload['grid_price_kwh'] !== '') {
			$station->setGridPriceKwh((string) $payload['grid_price_kwh']);
			$dirty = true;
		}
		if (array_key_exists('grid_connection_type', $payload)) {
			$gct = strtolower(trim((string) $payload['grid_connection_type']));
			if (in_array($gct, ['on_grid', 'off_grid'], true)) {
				$station->setGridConnectionType($gct);
				$dirty = true;
			}
		}

		if ($dirty) {
			$station->setUpdatedAt(new DateTime());
			$station = $this->mapper->update($station);
			$this->logger->info('Lifecycle profile updated', [
				'installation_id' => $station->getInstallationId(),
				'actor' => $payload['actor'] ?? null,
			]);
		}

		$this->notifyOdooMirror($station);
		return new JSONResponse([
			'success' => true,
			'station' => $this->toLifecycleArray($station),
			'idempotent' => !$dirty,
		]);
	}

	/**
	 * POST /api/lifecycle/v1/stations/{installationId}/set-lifecycle
	 *
	 * Explicit lifecycle set for CRM mirror demotions and admin corrections
	 * (virtual | planned | running). Promotion-only endpoints remain for
	 * upward transitions; this allows Running → Planned/Virtual.
	 */
	#[PublicPage]
	#[NoCSRFRequired]
	public function setLifecycle(string $installationId): JSONResponse
	{
		if (!$this->authorized()) {
			return $this->error('unauthorized', Http::STATUS_UNAUTHORIZED, 'unauthorized');
		}

		$station = $this->mapper->findByInstallationKey($installationId);
		if ($station === null) {
			return $this->error('station not found', Http::STATUS_NOT_FOUND, 'not_found');
		}
		if (($station->getSource() ?: '') === 'dataset') {
			return $this->error('dataset stations are not part of the CRM mirror', Http::STATUS_CONFLICT, 'dataset_excluded');
		}

		$payload = $this->jsonBody();
		$target = strtolower(trim((string) (
			$payload['lifecycle_state']
			?? $this->request->getParam('lifecycle_state', '')
		)));
		if (!StationLifecycle::isValidState($target)) {
			return $this->error('Invalid lifecycle_state', Http::STATUS_BAD_REQUEST, 'validation_error');
		}
		if (!StationLifecycle::canSetLifecycleState($target, $station->getSoftRemoved())) {
			return $this->error(
				'Cannot change lifecycle while soft-removed',
				Http::STATUS_CONFLICT,
				'illegal_transition',
			);
		}

		$prev = $this->stateOf($station);
		if ($prev !== $target) {
			$station->applyLifecycleState($target);
			if ($target === StationLifecycle::RUNNING && $station->getInstalledAt() === null) {
				$station->setInstalledAt(new DateTime());
			}
			// Demotion away from Running: clear installed_at so public "existing"
			// semantics do not keep a stale install date after Virtual/Planned.
			if ($target !== StationLifecycle::RUNNING) {
				$station->setInstalledAt(null);
			}
			$station->setUpdatedAt(new DateTime());
			$station = $this->mapper->update($station);
			$this->logger->info('Lifecycle set via CRM API', [
				'installation_id' => $station->getInstallationId(),
				'from' => $prev,
				'to' => $target,
				'actor' => $payload['actor'] ?? null,
			]);
		}

		$this->notifyOdooMirror($station);
		return new JSONResponse([
			'success' => true,
			'station' => $this->toLifecycleArray($station),
			'idempotent' => $prev === $target,
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
			'is_public' => StationLifecycle::isPublic($state, $soft, (bool) (isset($station) ? $station->getPublicArchived() : (isset($inst) ? $inst->getPublicArchived() : false))),
			'public_category' => StationLifecycle::publicCategory($state, $soft, (bool) (isset($station) ? $station->getPublicArchived() : (isset($inst) ? $inst->getPublicArchived() : false))),
			'soft_removed' => $soft,
			'odoo_lead_id' => $station->getOdooLeadId(),
			'capacity_kwp' => (float) $station->getCapacityKwp(),
			'grid_connection_type' => $station->getGridConnectionType() ?: 'on_grid',
			'grid_price_kwh' => $station->getGridPriceKwh() !== null && $station->getGridPriceKwh() !== ''
				? (float) $station->getGridPriceKwh()
				: null,
			'latitude' => (float) $station->getLatitude(),
			'longitude' => (float) $station->getLongitude(),
			'name' => $station->getName(),
			'location' => $station->getLocation(),
			'source' => $station->getSource(),
			'installed_at' => $station->getInstalledAt()?->format('c'),
			'website' => $station->getWebsite(),
			'short_description' => $station->getShortDescription(),
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

	
	/**
	 * Best-effort push to Odoo CRM mirror webhook.
	 */
	private function notifyOdooMirror(Installation $station): void
	{
		$this->odooMirror->notify($station);
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
