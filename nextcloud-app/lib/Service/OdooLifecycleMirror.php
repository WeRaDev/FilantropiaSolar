<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Service;

use OCA\FilantropiaSolar\AppInfo\Application;
use OCA\FilantropiaSolar\Db\Installation;
use OCP\IConfig;
use Psr\Log\LoggerInterface;

/**
 * Best-effort push of station lifecycle snapshots to Odoo CRM webhook.
 */
class OdooLifecycleMirror
{
	public function __construct(
		private readonly IConfig $config,
		private readonly LoggerInterface $logger,
	) {
	}

	public function notify(Installation $station): void
	{
		// Training corpus is not part of the CRM mirror.
		if (($station->getSource() ?: '') === 'dataset') {
			return;
		}

		$url = (string) $this->config->getAppValue(Application::APP_ID, 'odoo_lifecycle_webhook_url', '');
		if ($url === '') {
			$url = 'http://filantropia-odoo:8069/filantropia/nc/lifecycle/http';
		}
		$token = (string) $this->config->getAppValue(Application::APP_ID, 'lifecycle_api_token', '');
		if ($token === '') {
			$token = (string) $this->config->getAppValue(Application::APP_ID, 'public_api_token', '');
		}
		if ($token === '') {
			$this->logger->debug('Odoo lifecycle webhook skipped: no token configured');
			return;
		}

		$state = $station->getLifecycleState();
		if ($state === null || $state === '') {
			$state = StationLifecycle::defaultStateForNew(
				(bool) $station->getIsVirtual(),
				(string) ($station->getSource() ?: ''),
			);
		}
		$soft = (bool) $station->getSoftRemoved();

		$payload = json_encode([
			'success' => true,
			'station' => [
				'id' => $station->getId(),
				'installation_id' => $station->getInstallationId(),
				'lifecycle_state' => $state,
				'running_mode' => StationLifecycle::runningMode($state, false),
				'is_public' => StationLifecycle::isPublic($state, $soft),
				'public_category' => StationLifecycle::publicCategory($state, $soft),
				'soft_removed' => $soft,
				'odoo_lead_id' => $station->getOdooLeadId(),
				'capacity_kwp' => (float) $station->getCapacityKwp(),
				'grid_price_kwh' => $station->getGridPriceKwh() !== null && $station->getGridPriceKwh() !== ''
					? (float) $station->getGridPriceKwh()
					: null,
				'grid_connection_type' => $station->getGridConnectionType() ?: 'on_grid',
				'latitude' => (float) $station->getLatitude(),
				'longitude' => (float) $station->getLongitude(),
				'name' => $station->getName(),
				'location' => $station->getLocation(),
				'source' => $station->getSource(),
				'installed_at' => $station->getInstalledAt()?->format('c'),
				'website' => $station->getWebsite(),
				'short_description' => $station->getShortDescription(),
			],
		]);
		if ($payload === false) {
			return;
		}

		try {
			$ctx = stream_context_create([
				'http' => [
					'method' => 'POST',
					'header' => "Content-Type: application/json\r\nAuthorization: Bearer {$token}\r\n",
					'content' => $payload,
					'timeout' => 5,
					'ignore_errors' => true,
				],
			]);
			@file_get_contents($url, false, $ctx);
		} catch (\Throwable $e) {
			$this->logger->warning('Odoo lifecycle webhook failed', ['exception' => $e]);
		}
	}
}
