<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Service;

use DateInterval;
use DateTime;
use DateTimeImmutable;
use DateTimeZone;
use OCA\FilantropiaSolar\Db\EnergyReadingMapper;
use OCA\FilantropiaSolar\Db\Installation;
use OCA\FilantropiaSolar\Db\InstallationMapper;
use OCP\Http\Client\IClientService;
use OCP\IConfig;
use Psr\Log\LoggerInterface;

/**
 * Gap-fill NC series from ML hourly simulation (Europe/Lisbon hour buckets).
 * Measured hours are immutable; simulated only fills empty hours.
 */
class SeriesSimulationService
{
	private const DEFAULT_ML_URL = 'http://filantropia-ml:8501';
	private const TIMEOUT_SECONDS = 120;
	public const PROVENANCE_MEASURED = 'measured';
	public const PROVENANCE_SIMULATED = 'simulated';

	public function __construct(
		private readonly IClientService $clientService,
		private readonly IConfig $config,
		private readonly InstallationMapper $installationMapper,
		private readonly EnergyReadingMapper $readingMapper,
		private readonly LoggerInterface $logger,
	) {
	}

	private function getMlServiceUrl(): string
	{
		return $this->config->getAppValue(
			'filantropia_solar',
			'ml_service_url',
			self::DEFAULT_ML_URL,
		);
	}

	/**
	 * Last complete Europe/Lisbon hour start (e.g. 13:00 when now is 13:42 Lisbon).
	 * @deprecated name kept for callers; uses AppTimezone::lastCompleteHour()
	 */
	public function lastCompleteHourUtc(?DateTimeImmutable $now = null): DateTimeImmutable
	{
		return AppTimezone::lastCompleteHour($now);
	}

	/** Alias preferred name. */
	public function lastCompleteHour(?DateTimeImmutable $now = null): DateTimeImmutable
	{
		return AppTimezone::lastCompleteHour($now);
	}

	/**
	 * Operation / series start for backfill window (installation date when set).
	 * Prefer installation_date over installed_at so Edit "dataset start" wins.
	 */
	public function operationStart(Installation $station): DateTimeImmutable
	{
		$candidates = [
			$station->getInstallationDate(),
			$station->getInstalledAt(),
			$station->getFromDate(),
			$station->getCreatedAt(),
		];
		foreach ($candidates as $dt) {
			if ($dt instanceof DateTime) {
				return DateTimeImmutable::createFromMutable($dt)
					->setTimezone(AppTimezone::zone())
					->setTime(0, 0, 0);
			}
		}

		return AppTimezone::now()->setTime(0, 0, 0);
	}

	/**
	 * Drop simulated hours before installation/operation start. Measured rows stay.
	 *
	 * @return int Number of deleted simulated rows
	 */
	public function pruneSimulatedBeforeOperationStart(Installation $station): int
	{
		$dbId = (int) $station->getId();
		if ($dbId <= 0) {
			return 0;
		}

		$start = $this->operationStart($station);
		try {
			return $this->readingMapper->deleteSimulatedBefore($dbId, $start);
		} catch (\Throwable $e) {
			$this->logger->warning('pruneSimulatedBeforeOperationStart failed', [
				'id' => $dbId,
				'exception' => $e,
			]);

			return 0;
		}
	}

	/**
	 * @return Installation[] Running ops stations (not soft-removed, not dataset).
	 */
	public function findRunningOpsStations(): array
	{
		$stations = $this->installationMapper->findByLifecycleStates(
			[StationLifecycle::RUNNING],
			includeSoftRemoved: false,
		);

		return array_values(array_filter(
			$stations,
			static fn (Installation $s): bool => ($s->getSource() ?: '') !== 'dataset',
		));
	}

	/** Max days per backfill chunk (keeps ML + NC within job timeout). */
	public const BACKFILL_CHUNK_DAYS = 7;

	/** First Europe/Lisbon hour inclusive for automatic series fill (05:00). */
	public const PRODUCTION_HOUR_START = 5;

	/** Last Europe/Lisbon hour inclusive for automatic series fill (22:00). */
	public const PRODUCTION_HOUR_END = 22;

	/**
	 * Historical gap-fill for one Running station (chunked).
	 *
	 * Walks install→now in {@see BACKFILL_CHUNK_DAYS}-day windows and fills the
	 * first window that still has missing hours. Repeated job runs eventually
	 * cover the full history without a multi-year single ML request.
	 *
	 * @return array{requested:int, inserted:int, skipped_existing:int, skipped_measured:int, chunk_start:?string, chunk_end:?string, complete:bool}
	 */
	public function backfillStation(Installation $station, int $chunkDays = self::BACKFILL_CHUNK_DAYS): array
	{
		$empty = [
			'requested' => 0,
			'inserted' => 0,
			'skipped_existing' => 0,
			'skipped_measured' => 0,
			'chunk_start' => null,
			'chunk_end' => null,
			'complete' => true,
		];

		$start = $this->operationStart($station)->setTime(0, 0, 0);
		$end = $this->lastCompleteHourUtc();
		if ($start > $end) {
			return $empty;
		}

		$chunkDays = max(1, $chunkDays);
		$cursor = $start;
		while ($cursor <= $end) {
			$windowEnd = $cursor
				->add(new DateInterval('P' . $chunkDays . 'D'))
				->sub(new DateInterval('PT1H'));
			if ($windowEnd > $end) {
				$windowEnd = $end;
			}

			$missing = $this->missingHours((int) $station->getId(), $cursor, $windowEnd);
			if ($missing !== []) {
				$result = $this->fillRange($station, $cursor, $windowEnd);
				$nextStart = $windowEnd->add(new DateInterval('PT1H'));

				return [
					'requested' => $result['requested'],
					'inserted' => $result['inserted'],
					'skipped_existing' => $result['skipped_existing'],
					'skipped_measured' => $result['skipped_measured'],
					'chunk_start' => $cursor->format('c'),
					'chunk_end' => $windowEnd->format('c'),
					// More history may remain after this chunk.
					'complete' => $nextStart > $end,
				];
			}

			$cursor = $cursor->add(new DateInterval('P' . $chunkDays . 'D'));
		}

		return $empty;
	}

	/**
	 * Rolling window gap-fill (default last 12 complete hours).
	 *
	 * @return array{requested:int, inserted:int, skipped_existing:int, skipped_measured:int}
	 */
	public function rollForwardStation(Installation $station, int $hours = 12): array
	{
		$end = $this->lastCompleteHourUtc();
		$start = $end->sub(new DateInterval('PT' . max(1, $hours - 1) . 'H'));

		return $this->fillRange($station, $start, $end);
	}

	/**
	 * @return array{requested:int, inserted:int, skipped_existing:int, skipped_measured:int}
	 */
	public function fillRange(
		Installation $station,
		DateTimeImmutable $startUtc,
		DateTimeImmutable $endUtc,
	): array {
		$dbId = (int) $station->getId();
		if ($dbId <= 0) {
			return ['requested' => 0, 'inserted' => 0, 'skipped_existing' => 0, 'skipped_measured' => 0];
		}

		$missing = $this->missingHours($dbId, $startUtc, $endUtc);
		if ($missing === []) {
			return ['requested' => 0, 'inserted' => 0, 'skipped_existing' => 0, 'skipped_measured' => 0];
		}

		$hours = $this->requestHourlySimulation($station, $startUtc, $endUtc);
		if ($hours === []) {
			$this->logger->warning('SeriesSimulationService: empty ML response', [
				'installation_id' => $dbId,
			]);

			return [
				'requested' => count($missing),
				'inserted' => 0,
				'skipped_existing' => 0,
				'skipped_measured' => 0,
			];
		}

		$byTs = [];
		foreach ($hours as $row) {
			$ts = $this->normalizeHourKey((string) ($row['timestamp'] ?? ''));
			if ($ts === null) {
				continue;
			}
			$byTs[$ts] = $row;
		}

		$inserted = 0;
		$skippedExisting = 0;
		$skippedMeasured = 0;
		foreach ($missing as $hourKey) {
			$row = $byTs[$hourKey] ?? null;
			if ($row === null) {
				continue;
			}
			$production = (float) ($row['production_kwh'] ?? 0);
			$result = $this->readingMapper->insertSimulatedIfEmpty(
				$dbId,
				DateTime::createFromFormat('Y-m-d H:i:s', $hourKey, AppTimezone::zone()) ?: new DateTime($hourKey, AppTimezone::zone()),
				$production,
				isset($row['temperature_c']) ? (float) $row['temperature_c'] : (isset($row['temperature']) ? (float) $row['temperature'] : null),
				isset($row['cloud_cover_pct']) ? (int) $row['cloud_cover_pct'] : (isset($row['cloud_cover']) ? (int) $row['cloud_cover'] : null),
				isset($row['solar_radiation_wm2']) ? (float) $row['solar_radiation_wm2'] : (isset($row['shortwave_radiation']) ? (float) $row['shortwave_radiation'] : null),
			);
			if ($result === 'inserted') {
				$inserted++;
			} elseif ($result === 'measured') {
				$skippedMeasured++;
			} else {
				$skippedExisting++;
			}
		}

		return [
			'requested' => count($missing),
			'inserted' => $inserted,
			'skipped_existing' => $skippedExisting,
			'skipped_measured' => $skippedMeasured,
		];
	}

	/**
	 * Import measured readings (any logged-in user). Never overwritten later by sim.
	 *
	 * @param list<array<string, mixed>> $readings
	 * @return array{imported:int, skipped:int, overwritten_simulated:int}
	 */
	public function importMeasured(int $installationDbId, array $readings): array
	{
		$imported = 0;
		$skipped = 0;
		$overwritten = 0;
		foreach ($readings as $reading) {
			$tsRaw = (string) ($reading['timestamp'] ?? '');
			$ts = $this->normalizeHourKey($tsRaw);
			if ($ts === null) {
				$skipped++;
				continue;
			}
			$dt = DateTime::createFromFormat('Y-m-d H:i:s', $ts, AppTimezone::zone());
			if ($dt === false) {
				$skipped++;
				continue;
			}
			$result = $this->readingMapper->upsertMeasured(
				$installationDbId,
				$dt,
				isset($reading['production_kwh']) ? (float) $reading['production_kwh'] : 0.0,
				isset($reading['consumption_kwh']) ? (float) $reading['consumption_kwh'] : null,
				isset($reading['solar_radiation_wm2']) ? (float) $reading['solar_radiation_wm2'] : null,
				isset($reading['temperature_c']) ? (float) $reading['temperature_c'] : null,
				isset($reading['cloud_cover_pct']) ? (int) $reading['cloud_cover_pct'] : null,
			);
			if ($result === 'inserted' || $result === 'updated') {
				$imported++;
				if ($result === 'updated') {
					$overwritten++;
				}
			} else {
				$skipped++;
			}
		}

		return [
			'imported' => $imported,
			'skipped' => $skipped,
			'overwritten_simulated' => $overwritten,
		];
	}

	/**
	 * @return list<string> hour keys Y-m-d H:i:s Europe/Lisbon missing from series
	 */
	private function missingHours(
		int $installationDbId,
		DateTimeImmutable $startLocal,
		DateTimeImmutable $endLocal,
	): array {
		$startLocal = $startLocal->setTimezone(AppTimezone::zone());
		$endLocal = $endLocal->setTimezone(AppTimezone::zone());
		$existing = $this->readingMapper->listTimestamps(
			$installationDbId,
			DateTime::createFromImmutable($startLocal),
			DateTime::createFromImmutable($endLocal),
		);
		$existingSet = array_fill_keys($existing, true);
		$missing = [];
		$cursor = $startLocal->setTime((int) $startLocal->format('H'), 0, 0);
		$end = $endLocal->setTime((int) $endLocal->format('H'), 0, 0);
		while ($cursor <= $end) {
			$hour = (int) $cursor->format('G');
			// Automatic population only during production window 05:00–22:00 Europe/Lisbon
			if ($hour >= self::PRODUCTION_HOUR_START && $hour <= self::PRODUCTION_HOUR_END) {
				$key = $cursor->format('Y-m-d H:i:s');
				if (!isset($existingSet[$key])) {
					$missing[] = $key;
				}
			}
			$cursor = $cursor->add(new DateInterval('PT1H'));
		}

		return $missing;
	}

	/**
	 * @return list<array<string, mixed>>
	 */
	private function requestHourlySimulation(
		Installation $station,
		DateTimeImmutable $startUtc,
		DateTimeImmutable $endUtc,
	): array {
		try {
			$client = $this->clientService->newClient();
			$response = $client->post(
				$this->getMlServiceUrl() . '/simulate/hourly',
				[
					'timeout' => self::TIMEOUT_SECONDS,
					'json' => [
						'latitude' => (float) $station->getLatitude(),
						'longitude' => (float) $station->getLongitude(),
						'capacity_kwp' => (float) $station->getCapacityKwp(),
						'location' => $station->getLocation() ?: 'Lisbon',
						// ML expects absolute instants; convert Lisbon wall-clock range to UTC
						'start' => $startUtc->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d\TH:i:s\Z'),
						'end' => $endUtc->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d\TH:i:s\Z'),
					],
				],
			);
			$data = json_decode((string) $response->getBody(), true);
			if (!is_array($data)) {
				return [];
			}
			$hours = $data['hours'] ?? $data['hourly_data'] ?? [];

			return is_array($hours) ? $hours : [];
		} catch (\Throwable $e) {
			$this->logger->error('SeriesSimulationService: ML simulate/hourly failed', [
				'exception' => $e,
				'station' => $station->getId(),
			]);

			return [];
		}
	}

	private function normalizeHourKey(string $raw): ?string
	{
		$raw = trim($raw);
		if ($raw === '') {
			return null;
		}
		try {
			// Naive timestamps are treated as Europe/Lisbon wall-clock; Z/offset converted to Lisbon.
			if (preg_match('/[zZ]|[+-]\d{2}:?\d{2}$/', $raw)) {
				$dt = new DateTimeImmutable($raw);
			} else {
				$dt = new DateTimeImmutable($raw, AppTimezone::zone());
			}
			$dt = $dt->setTimezone(AppTimezone::zone())->setTime((int) $dt->format('H'), 0, 0);

			return $dt->format('Y-m-d H:i:s');
		} catch (\Throwable) {
			return null;
		}
	}
}
