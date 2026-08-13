<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\BackgroundJob;

use OCA\FilantropiaSolar\Service\SeriesSimulationService;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\BackgroundJob\TimedJob;
use Psr\Log\LoggerInterface;

/**
 * Every 12 hours, simulate the previous 12 complete UTC hours for Running ops stations.
 * Only empty hours receive simulated rows; measured is immutable.
 */
class SeriesRollForwardJob extends TimedJob
{
	private const INTERVAL_SECONDS = 12 * 60 * 60;
	private const WINDOW_HOURS = 12;

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
		$this->logger->info('SeriesRollForwardJob: starting');
		$stations = $this->seriesService->findRunningOpsStations();
		$totalInserted = 0;
		foreach ($stations as $station) {
			try {
				$result = $this->seriesService->rollForwardStation($station, self::WINDOW_HOURS);
				$totalInserted += $result['inserted'];
				$this->logger->info('SeriesRollForwardJob: station done', [
					'id' => $station->getId(),
					'name' => $station->getName(),
					'result' => $result,
				]);
			} catch (\Throwable $e) {
				$this->logger->warning('SeriesRollForwardJob: station failed', [
					'id' => $station->getId(),
					'exception' => $e,
				]);
			}
		}
		$this->logger->info('SeriesRollForwardJob: completed', [
			'stations' => count($stations),
			'inserted' => $totalInserted,
		]);
	}
}
