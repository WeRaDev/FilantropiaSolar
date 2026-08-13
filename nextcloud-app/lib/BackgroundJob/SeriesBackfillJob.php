<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\BackgroundJob;

use OCA\FilantropiaSolar\Service\SeriesSimulationService;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\BackgroundJob\TimedJob;
use Psr\Log\LoggerInterface;

/**
 * Initial / catch-up series backfill for Running ops stations.
 * Interval 24h so long-running fleets eventually fill from install→now;
 * measured hours are never overwritten.
 */
class SeriesBackfillJob extends TimedJob
{
	private const INTERVAL_SECONDS = 24 * 60 * 60;

	public function __construct(
		ITimeFactory $time,
		private readonly SeriesSimulationService $seriesService,
		private readonly LoggerInterface $logger,
	) {
		parent::__construct($time);
		$this->setInterval(self::INTERVAL_SECONDS);
	}

	protected function run(mixed $argument): void
	{
		$this->logger->info('SeriesBackfillJob: starting');
		$stations = $this->seriesService->findRunningOpsStations();
		$totalInserted = 0;
		$incomplete = 0;
		foreach ($stations as $station) {
			try {
				// One chunk per station per run (see SeriesSimulationService::BACKFILL_CHUNK_DAYS).
				$result = $this->seriesService->backfillStation($station);
				$totalInserted += $result['inserted'];
				if (empty($result['complete'])) {
					$incomplete++;
				}
				$this->logger->info('SeriesBackfillJob: station chunk done', [
					'id' => $station->getId(),
					'name' => $station->getName(),
					'result' => $result,
				]);
			} catch (\Throwable $e) {
				$this->logger->warning('SeriesBackfillJob: station failed', [
					'id' => $station->getId(),
					'exception' => $e,
				]);
			}
		}
		$this->logger->info('SeriesBackfillJob: completed', [
			'stations' => count($stations),
			'inserted' => $totalInserted,
			'incomplete_stations' => $incomplete,
		]);
	}
}
