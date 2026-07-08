<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\BackgroundJob;

use OCA\FilantropiaSolar\Service\PredictionService;
use OCP\AppFramework\Utility\ITimeFactory;
use OCP\BackgroundJob\TimedJob;
use Psr\Log\LoggerInterface;

/**
 * Prediction Job
 *
 * Background job that periodically refreshes ML predictions for all installations.
 * Runs every 6 hours to ensure predictions stay current.
 */
class PredictionJob extends TimedJob
{
    private const INTERVAL_HOURS = 6;

    public function __construct(
        ITimeFactory $time,
        private readonly PredictionService $predictionService,
        private readonly LoggerInterface $logger,
    ) {
        parent::__construct($time);

        // Run every 6 hours
        $this->setInterval(self::INTERVAL_HOURS * 60 * 60);
    }

    /**
     * Execute the background job.
     */
    protected function run(mixed $argument): void
    {
        $this->logger->info('PredictionJob: Starting prediction refresh');

        // Check if ML service is available
        if (!$this->predictionService->isHealthy()) {
            $this->logger->warning('PredictionJob: ML service is not available, skipping');
            return;
        }

        try {
            // Refresh predictions for all installations that need it
            $refreshed = $this->predictionService->refreshAllPredictions();

            $this->logger->info('PredictionJob: Completed', [
                'installations_refreshed' => $refreshed,
            ]);
        } catch (\Exception $e) {
            $this->logger->error('PredictionJob: Failed', [
                'exception' => $e,
            ]);
        }
    }
}
