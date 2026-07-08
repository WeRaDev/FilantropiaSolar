<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Controller;

use OCA\FilantropiaSolar\AppInfo\Application;
use OCA\FilantropiaSolar\Db\InstallationMapper;
use OCA\FilantropiaSolar\Service\PredictionService;
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
 * Provides endpoints for ML-based energy predictions.
 */
class PredictionApiController extends OCSController
{
    /** ML Service URL (internal Docker network) */
    private const ML_SERVICE_URL = 'http://filantropia-ml:8501';

    public function __construct(
        IRequest $request,
        private readonly PredictionService $predictionService,
        private readonly InstallationMapper $installationMapper,
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
     * Generate period analysis (21-day prediction).
     *
     * Proxies to ML service /predict/period endpoint.
     *
     * @NoAdminRequired
     * @NoCSRFRequired
     * @return JSONResponse
     */
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function period(): JSONResponse
    {
        try {
            // Get request body
            $input = file_get_contents('php://input');
            $requestData = json_decode($input, true);

            if (!$requestData) {
                return new JSONResponse(
                    ['success' => false, 'error' => 'Invalid request body'],
                    Http::STATUS_BAD_REQUEST
                );
            }

            // Validate required fields
            if (empty($requestData['mode'])) {
                return new JSONResponse(
                    ['success' => false, 'error' => 'Mode is required'],
                    Http::STATUS_BAD_REQUEST
                );
            }

            if (empty($requestData['center_date'])) {
                return new JSONResponse(
                    ['success' => false, 'error' => 'Center date is required'],
                    Http::STATUS_BAD_REQUEST
                );
            }

            // Proxy to ML service
            $client = $this->clientService->newClient();
            $response = $client->post(self::ML_SERVICE_URL . '/predict/period', [
                'headers' => [
                    'Content-Type' => 'application/json',
                ],
                'body' => json_encode($requestData),
            ]);

            $data = json_decode($response->getBody(), true);
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
}
