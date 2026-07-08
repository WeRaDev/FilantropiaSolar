<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Db;

use DateTime;
use JsonSerializable;
use OCP\AppFramework\Db\Entity;

/**
 * Installation Entity
 *
 * Represents a PV installation in the FilantropiaSolar system.
 *
 * @method string|null getUserId()
 * @method void setUserId(?string $userId)
 * @method string getName()
 * @method void setName(string $name)
 * @method string|null getSerialNumber()
 * @method void setSerialNumber(?string $serialNumber)
 * @method string getLocation()
 * @method void setLocation(string $location)
 * @method string getLatitude()
 * @method void setLatitude(string $latitude)
 * @method string getLongitude()
 * @method void setLongitude(string $longitude)
 * @method string getCapacityKwp()
 * @method void setCapacityKwp(string $capacityKwp)
 * @method string|null getConnectionPowerKwn()
 * @method void setConnectionPowerKwn(?string $connectionPowerKwn)
 * @method string|null getGridPriceKwh()
 * @method void setGridPriceKwh(?string $gridPriceKwh)
 * @method DateTime|null getInstallationDate()
 * @method void setInstallationDate(?DateTime $installationDate)
 * @method DateTime|null getCreatedAt()
 * @method void setCreatedAt(?DateTime $createdAt)
 * @method DateTime|null getUpdatedAt()
 * @method void setUpdatedAt(?DateTime $updatedAt)
 * @method bool getIsVirtual()
 * @method void setIsVirtual(bool $isVirtual)
 * @method string getSource()
 * @method void setSource(string $source)
 * @method DateTime|null getFromDate()
 * @method void setFromDate(?DateTime $fromDate)
 * @method DateTime|null getToDate()
 * @method void setToDate(?DateTime $toDate)
 * @method bool getErrorFlag()
 * @method void setErrorFlag(bool $errorFlag)
 * @method string|null getNearestLocation()
 * @method void setNearestLocation(?string $nearestLocation)
 */
class Installation extends Entity implements JsonSerializable
{
    protected ?string $userId = null;
    protected string $name = '';
    protected ?string $serialNumber = null;
    protected string $location = '';
    protected string $latitude = '0';
    protected string $longitude = '0';
    protected string $capacityKwp = '0';
    protected ?string $connectionPowerKwn = null;
    protected ?string $gridPriceKwh = '0.15';
    protected ?DateTime $installationDate = null;
    protected ?DateTime $createdAt = null;
    protected ?DateTime $updatedAt = null;
    protected bool $isVirtual = false;
    protected string $source = 'user';
    protected ?DateTime $fromDate = null;
    protected ?DateTime $toDate = null;
    protected bool $errorFlag = false;
    protected ?string $nearestLocation = null;

    public function __construct()
    {
        $this->addType('userId', 'string');
        $this->addType('name', 'string');
        $this->addType('serialNumber', 'string');
        $this->addType('location', 'string');
        $this->addType('latitude', 'string');
        $this->addType('longitude', 'string');
        $this->addType('capacityKwp', 'string');
        $this->addType('connectionPowerKwn', 'string');
        $this->addType('gridPriceKwh', 'string');
        $this->addType('installationDate', 'datetime');
        $this->addType('createdAt', 'datetime');
        $this->addType('updatedAt', 'datetime');
        $this->addType('isVirtual', 'boolean');
        $this->addType('source', 'string');
        $this->addType('fromDate', 'datetime');
        $this->addType('toDate', 'datetime');
        $this->addType('errorFlag', 'boolean');
        $this->addType('nearestLocation', 'string');
    }

    /**
     * Get coordinates as array [lat, lon].
     */
    public function getCoordinates(): array
    {
        return [
            (float) $this->latitude,
            (float) $this->longitude,
        ];
    }

    /**
     * Get capacity as float in kWp.
     */
    public function getCapacityFloat(): float
    {
        return (float) $this->capacityKwp;
    }

    /**
     * Get grid price as float in EUR/kWh.
     */
    public function getGridPriceFloat(): float
    {
        return (float) ($this->gridPriceKwh ?? '0.15');
    }

    /**
     * Generate installation ID (location_serial format).
     */
    public function getInstallationId(): string
    {
        return sprintf('%s_%s', $this->location, $this->serialNumber ?? $this->id);
    }

    /**
     * Serialize to JSON for API responses.
     */
    public function jsonSerialize(): array
    {
        return [
            'id' => $this->id,
            'userId' => $this->userId,
            'name' => $this->name,
            'serialNumber' => $this->serialNumber,
            'location' => $this->location,
            'latitude' => (float) $this->latitude,
            'longitude' => (float) $this->longitude,
            'capacityKwp' => (float) $this->capacityKwp,
            'connectionPowerKwn' => $this->connectionPowerKwn ? (float) $this->connectionPowerKwn : null,
            'gridPriceKwh' => (float) ($this->gridPriceKwh ?? '0.15'),
            'installationDate' => $this->installationDate?->format('Y-m-d'),
            'createdAt' => $this->createdAt?->format('c'),
            'updatedAt' => $this->updatedAt?->format('c'),
            'installationId' => $this->getInstallationId(),
            'isVirtual' => $this->isVirtual,
            'source' => $this->source,
            'fromDate' => $this->fromDate?->format('Y-m-d'),
            'toDate' => $this->toDate?->format('Y-m-d'),
            'errorFlag' => $this->errorFlag,
            'nearestLocation' => $this->nearestLocation,
        ];
    }
}
