<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Db;

use DateTime;
use JsonSerializable;
use OCP\AppFramework\Db\Entity;

/**
 * Prediction Entity
 *
 * Represents an ML-generated energy prediction for a PV installation.
 *
 * @method int getInstallationId()
 * @method void setInstallationId(int $installationId)
 * @method DateTime getPredictionDate()
 * @method void setPredictionDate(DateTime $predictionDate)
 * @method int getHour()
 * @method void setHour(int $hour)
 * @method string|null getPredictedKwh()
 * @method void setPredictedKwh(?string $predictedKwh)
 * @method string|null getConfidence()
 * @method void setConfidence(?string $confidence)
 * @method string|null getModelVersion()
 * @method void setModelVersion(?string $modelVersion)
 * @method DateTime getCreatedAt()
 * @method void setCreatedAt(DateTime $createdAt)
 */
class Prediction extends Entity implements JsonSerializable
{
    protected int $installationId = 0;
    protected DateTime $predictionDate;
    protected int $hour = 0;
    protected ?string $predictedKwh = null;
    protected ?string $confidence = null;
    protected ?string $modelVersion = null;
    protected DateTime $createdAt;

    public function __construct()
    {
        $this->addType('installationId', 'integer');
        $this->addType('predictionDate', 'datetime');
        $this->addType('hour', 'integer');
        $this->addType('predictedKwh', 'string');
        $this->addType('confidence', 'string');
        $this->addType('modelVersion', 'string');
        $this->addType('createdAt', 'datetime');
    }

    /**
     * Get predicted energy as float in kWh.
     */
    public function getPredictedFloat(): float
    {
        return (float) ($this->predictedKwh ?? 0);
    }

    /**
     * Get confidence as float (0-1).
     */
    public function getConfidenceFloat(): float
    {
        return (float) ($this->confidence ?? 0);
    }

    /**
     * Get full timestamp combining date and hour.
     */
    public function getFullTimestamp(): DateTime
    {
        $dt = clone $this->predictionDate;
        $dt->setTime($this->hour, 0, 0);
        return $dt;
    }

    /**
     * Serialize to JSON for API responses.
     */
    public function jsonSerialize(): array
    {
        return [
            'id' => $this->id,
            'installation_id' => $this->installationId,
            'prediction_date' => $this->predictionDate->format('Y-m-d'),
            'hour' => $this->hour,
            'timestamp' => $this->getFullTimestamp()->format('c'),
            'predicted_kwh' => $this->predictedKwh !== null ? (float) $this->predictedKwh : null,
            'confidence' => $this->confidence !== null ? (float) $this->confidence : null,
            'model_version' => $this->modelVersion,
            'created_at' => $this->createdAt->format('c'),
        ];
    }
}
