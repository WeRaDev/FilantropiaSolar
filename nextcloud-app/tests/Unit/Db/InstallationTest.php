<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Tests\Unit\Db;

use OCA\FilantropiaSolar\Db\Installation;
use PHPUnit\Framework\TestCase;

/**
 * Unit tests for Installation Entity
 */
class InstallationTest extends TestCase
{
    /**
     * Test entity creation with all fields
     */
    public function testCreateInstallation(): void
    {
        $installation = new Installation();
        $installation->setUserId('user123');
        $installation->setName('Test Solar');
        $installation->setLatitude('38.7223');
        $installation->setLongitude('-9.1393');
        $installation->setCapacityKwp('5.50');
        $installation->setGridPriceKwh('0.15');

        $this->assertEquals('user123', $installation->getUserId());
        $this->assertEquals('Test Solar', $installation->getName());
        $this->assertEquals('38.7223', $installation->getLatitude());
        $this->assertEquals('-9.1393', $installation->getLongitude());
        $this->assertEquals('5.50', $installation->getCapacityKwp());
        $this->assertEquals('0.15', $installation->getGridPriceKwh());
    }

    /**
     * Test getGridPriceFloat returns default when null
     */
    public function testGetGridPriceFloatDefault(): void
    {
        $installation = new Installation();

        // Should return 0.15 (DEFAULT_GRID_PRICE from v1.2.x)
        $this->assertEquals(0.15, $installation->getGridPriceFloat());
    }

    /**
     * Test getGridPriceFloat with custom value
     */
    public function testGetGridPriceFloatCustom(): void
    {
        $installation = new Installation();
        $installation->setGridPriceKwh('0.20');

        $this->assertEquals(0.20, $installation->getGridPriceFloat());
    }

    /**
     * Test getCoordinates helper method
     */
    public function testGetCoordinates(): void
    {
        $installation = new Installation();
        $installation->setLatitude('38.7223');
        $installation->setLongitude('-9.1393');

        $coords = $installation->getCoordinates();

        $this->assertEqualsWithDelta(38.7223, $coords['lat'], 0.0001);
        $this->assertEqualsWithDelta(-9.1393, $coords['lon'], 0.0001);
    }

    /**
     * Test jsonSerialize includes all required fields
     */
    public function testJsonSerialize(): void
    {
        $installation = new Installation();
        $installation->setUserId('user123');
        $installation->setName('Test Solar');
        $installation->setLatitude('38.7223');
        $installation->setLongitude('-9.1393');
        $installation->setCapacityKwp('5.50');

        $json = $installation->jsonSerialize();

        $this->assertArrayHasKey('id', $json);
        $this->assertArrayHasKey('name', $json);
        $this->assertArrayHasKey('latitude', $json);
        $this->assertArrayHasKey('longitude', $json);
        $this->assertArrayHasKey('capacity_kwp', $json);
        $this->assertEquals('Test Solar', $json['name']);
    }

    /**
     * Test that coordinates can be set with float precision
     */
    public function testCoordinatePrecision(): void
    {
        $installation = new Installation();
        $installation->setLatitude('38.72234567');
        $installation->setLongitude('-9.13934567');

        $coords = $installation->getCoordinates();

        // Should maintain precision
        $this->assertEqualsWithDelta(38.72234567, $coords['lat'], 0.00000001);
        $this->assertEqualsWithDelta(-9.13934567, $coords['lon'], 0.00000001);
    }
}
