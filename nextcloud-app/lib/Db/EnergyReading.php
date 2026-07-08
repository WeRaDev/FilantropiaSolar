<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Db;

use DateTime;
use JsonSerializable;
use OCP\AppFramework\Db\Entity;

/**
 * EnergyReading Entity
 *
 * Represents an hourly energy reading for a PV installation.
 *
 * @method int getInstallationId()
 * @method void setInstallationId(int $installationId)
 * @method DateTime getTimestamp()
 * @method void setTimestamp(DateTime $timestamp)
 * @method string|null getProductionKwh()
 * @method void setProductionKwh(?string $productionKwh)
 * @method string|null getConsumptionKwh()
 * @method void setConsumptionKwh(?string $consumptionKwh)
 * @method string|null getSolarRadiationWm2()
 * @method void setSolarRadiationWm2(?string $solarRadiationWm2)
 * @method string|null getTemperatureC()
 * @method void setTemperatureC(?string $temperatureC)
 * @method int|null getCloudCoverPct()
 * @method void setCloudCoverPct(?int $cloudCoverPct)
 */
class EnergyReading extends Entity implements JsonSerializable
{
    protected int $installationId = 0;
    protected DateTime $timestamp;
    protected ?string $productionKwh = null;
    protected ?string $consumptionKwh = null;
    protected ?string $solarRadiationWm2 = null;
    protected ?string $temperatureC = null;
    protected ?int $cloudCoverPct = null;

    public function __construct()
    {
        $this->addType('installationId', 'integer');
        $this->addType('timestamp', 'datetime');
        $this->addType('productionKwh', 'string');
        $this->addType('consumptionKwh', 'string');
        $this->addType('solarRadiationWm2', 'string');
        $this->addType('temperatureC', 'string');
        $this->addType('cloudCoverPct', 'integer');
    }

    /**
     * Get production as float in kWh.
     */
    public function getProductionFloat(): float
    {
        return (float) ($this->productionKwh ?? 0);
    }

    /**
     * Get consumption as float in kWh.
     */
    public function getConsumptionFloat(): float
    {
        return (float) ($this->consumptionKwh ?? 0);
    }

    /**
     * Get solar radiation as float in W/m2.
     */
    public function getRadiationFloat(): float
    {
        return (float) ($this->solarRadiationWm2 ?? 0);
    }

    /**
     * Get temperature as float in Celsius.
     */
    public function getTemperatureFloat(): float
    {
        return (float) ($this->temperatureC ?? 0);
    }

    /**
     * Serialize to JSON for API responses.
     */
    public function jsonSerialize(): array
    {
        return [
            'id' => $this->id,
            'installation_id' => $this->installationId,
            'timestamp' => $this->timestamp->format('c'),
            'production_kwh' => $this->productionKwh !== null ? (float) $this->productionKwh : null,
            'consumption_kwh' => $this->consumptionKwh !== null ? (float) $this->consumptionKwh : null,
            'solar_radiation_wm2' => $this->solarRadiationWm2 !== null ? (float) $this->solarRadiationWm2 : null,
            'temperature_c' => $this->temperatureC !== null ? (float) $this->temperatureC : null,
            'cloud_cover_pct' => $this->cloudCoverPct,
        ];
    }
}
