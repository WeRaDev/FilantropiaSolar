<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Tests\Unit\Service;

use OCA\FilantropiaSolar\Service\WeatherService;
use OCP\Http\Client\IClientService;
use OCP\ICacheFactory;
use OCP\ICache;
use PHPUnit\Framework\TestCase;
use PHPUnit\Framework\MockObject\MockObject;
use Psr\Log\NullLogger;

/**
 * Unit tests for WeatherService
 */
class WeatherServiceTest extends TestCase
{
    private WeatherService $service;
    private MockObject&IClientService $clientServiceMock;
    private MockObject&ICacheFactory $cacheFactoryMock;
    private MockObject&ICache $cacheMock;

    protected function setUp(): void
    {
        $this->clientServiceMock = $this->createMock(IClientService::class);
        $this->cacheFactoryMock = $this->createMock(ICacheFactory::class);
        $this->cacheMock = $this->createMock(ICache::class);
        $logger = new NullLogger();

        $this->cacheFactoryMock
            ->method('createDistributed')
            ->willReturn($this->cacheMock);

        $this->service = new WeatherService(
            $this->clientServiceMock,
            $this->cacheFactoryMock,
            $logger
        );
    }

    /**
     * Test getAvailableLocations returns all Portuguese locations
     */
    public function testGetAvailableLocationsReturnsSixLocations(): void
    {
        $locations = $this->service->getAvailableLocations();

        $this->assertCount(6, $locations);
        $this->assertArrayHasKey('Lisbon', $locations);
        $this->assertArrayHasKey('Setubal', $locations);
        $this->assertArrayHasKey('Faro', $locations);
        $this->assertArrayHasKey('Braga', $locations);
        $this->assertArrayHasKey('Tavira', $locations);
        $this->assertArrayHasKey('Loule', $locations);
    }

    /**
     * Test location coordinates match v1.2.x values
     */
    public function testLocationCoordinatesInheritedFromPython(): void
    {
        $locations = $this->service->getAvailableLocations();

        // Verify Lisbon coordinates (from Python weather_simulator.py)
        $this->assertEqualsWithDelta(38.7223, $locations['Lisbon']['lat'], 0.0001);
        $this->assertEqualsWithDelta(-9.1393, $locations['Lisbon']['lon'], 0.0001);

        // Verify Faro coordinates
        $this->assertEqualsWithDelta(37.0194, $locations['Faro']['lat'], 0.0001);
        $this->assertEqualsWithDelta(-7.9304, $locations['Faro']['lon'], 0.0001);

        // Verify Braga coordinates (northernmost)
        $this->assertEqualsWithDelta(41.5454, $locations['Braga']['lat'], 0.0001);
        $this->assertEqualsWithDelta(-8.4265, $locations['Braga']['lon'], 0.0001);
    }

    /**
     * Test findNearestLocation returns Lisbon for Lisbon coordinates
     */
    public function testFindNearestLocationForLisbon(): void
    {
        $nearest = $this->service->findNearestLocation(38.7223, -9.1393);

        $this->assertEquals('Lisbon', $nearest);
    }

    /**
     * Test findNearestLocation returns Braga for northern Portugal
     */
    public function testFindNearestLocationForNorthernPortugal(): void
    {
        // Porto coordinates (should be closest to Braga)
        $nearest = $this->service->findNearestLocation(41.1579, -8.6291);

        $this->assertEquals('Braga', $nearest);
    }

    /**
     * Test findNearestLocation returns Faro for southern Portugal
     */
    public function testFindNearestLocationForSouthernPortugal(): void
    {
        // Albufeira coordinates (should be closest to Faro or Loule)
        $nearest = $this->service->findNearestLocation(37.0893, -8.2500);

        $this->assertContains($nearest, ['Faro', 'Loule']);
    }

    /**
     * Test findNearestLocation handles edge case of exact coordinates
     */
    public function testFindNearestLocationExactMatch(): void
    {
        $locations = $this->service->getAvailableLocations();

        foreach ($locations as $name => $coords) {
            $nearest = $this->service->findNearestLocation($coords['lat'], $coords['lon']);
            $this->assertEquals($name, $nearest);
        }
    }

    /**
     * Test Haversine distance calculation is reasonable
     */
    public function testFindNearestLocationUsesReasonableDistance(): void
    {
        // Point equidistant from Lisbon and Setubal
        // Lisbon: 38.7223, -9.1393
        // Setubal: 38.5244, -8.8882

        // Very close to Setubal
        $nearest = $this->service->findNearestLocation(38.53, -8.89);
        $this->assertEquals('Setubal', $nearest);
    }

    /**
     * Test location structure has required keys
     */
    public function testLocationStructureHasLatLon(): void
    {
        $locations = $this->service->getAvailableLocations();

        foreach ($locations as $name => $coords) {
            $this->assertArrayHasKey('lat', $coords, "Location {$name} missing 'lat'");
            $this->assertArrayHasKey('lon', $coords, "Location {$name} missing 'lon'");
            $this->assertIsFloat($coords['lat']);
            $this->assertIsFloat($coords['lon']);
        }
    }

    /**
     * Test all locations are in Portugal (reasonable lat/lon bounds)
     */
    public function testAllLocationsInPortugal(): void
    {
        $locations = $this->service->getAvailableLocations();

        // Portugal bounds approximately: lat 36.9-42.2, lon -9.5 to -6.2
        foreach ($locations as $name => $coords) {
            $this->assertGreaterThan(36.5, $coords['lat'], "{$name} latitude too low");
            $this->assertLessThan(42.5, $coords['lat'], "{$name} latitude too high");
            $this->assertGreaterThan(-10.0, $coords['lon'], "{$name} longitude too low");
            $this->assertLessThan(-6.0, $coords['lon'], "{$name} longitude too high");
        }
    }
}
