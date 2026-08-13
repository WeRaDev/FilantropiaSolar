<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Tests\Unit\Service;

use OCA\FilantropiaSolar\Service\SavingsService;
use OCA\FilantropiaSolar\Db\InstallationMapper;
use OCA\FilantropiaSolar\Db\Installation;
use OCP\IDBConnection;
use PHPUnit\Framework\TestCase;
use PHPUnit\Framework\MockObject\MockObject;
use Psr\Log\NullLogger;

/**
 * Unit tests for SavingsService
 */
class SavingsServiceTest extends TestCase
{
    private SavingsService $service;
    private MockObject&IDBConnection $dbMock;
    private MockObject&InstallationMapper $mapperMock;

    protected function setUp(): void
    {
        $this->dbMock = $this->createMock(IDBConnection::class);
        $this->mapperMock = $this->createMock(InstallationMapper::class);
        $logger = new NullLogger();

        $this->service = new SavingsService(
            $this->dbMock,
            $this->mapperMock,
            $logger
        );
    }

    /**
     * Test calculateSavings with default grid price
     */
    public function testCalculateSavingsWithDefaultPrice(): void
    {
        $production = 100.0; // kWh
        // default factor on-grid 0.4
        $expectedSavings = 100.0 * 0.15 * 0.4;

        $result = $this->service->calculateSavings($production);

        $this->assertEquals($expectedSavings, $result);
    }

    /**
     * Test calculateSavings with custom grid price
     */
    public function testCalculateSavingsWithCustomPrice(): void
    {
        $production = 100.0; // kWh
        $customPrice = 0.20; // EUR/kWh
        $expectedSavings = 100.0 * 0.20 * 0.4;

        $result = $this->service->calculateSavings($production, $customPrice);

        $this->assertEquals($expectedSavings, $result);
    }

    /**
     * Test calculateSavings with zero production
     */
    public function testCalculateSavingsWithZeroProduction(): void
    {
        $result = $this->service->calculateSavings(0.0);

        $this->assertEquals(0.0, $result);
    }

    /**
     * Test calculateSavings with large production value
     */
    public function testCalculateSavingsWithLargeProduction(): void
    {
        $production = 10000.0; // 10 MWh
        $expectedSavings = 10000.0 * 0.15 * 0.4;

        $result = $this->service->calculateSavings($production);

        $this->assertEquals($expectedSavings, $result);
    }

    /**
     * Test that default grid price matches v1.2.x constant
     */
    public function testDefaultGridPriceInheritedFromPython(): void
    {
        // DEFAULT_GRID_PRICE in Python v1.2.x was 0.15 EUR/kWh
        $production = 1.0;
        $result = $this->service->calculateSavings($production);

        // default price 0.15 * on-grid factor 0.4
        $this->assertEquals(0.06, $result);
    }

    /**
     * Test savings calculation precision
     */
    public function testSavingsCalculationPrecision(): void
    {
        $production = 123.456;
        $price = 0.123;
        $expected = $production * $price * 0.4;

        $result = $this->service->calculateSavings($production, $price);

        $this->assertEqualsWithDelta($expected, $result, 0.0001);
    }

    public function testOffGridFactorIsOne(): void
    {
        $result = $this->service->calculateSavings(100.0, 0.15, 1.0);
        $this->assertEquals(15.0, $result);
    }

    public function testFactorForGridType(): void
    {
        $this->assertEquals(0.4, SavingsService::factorForGridType('on_grid'));
        $this->assertEquals(1.0, SavingsService::factorForGridType('off_grid'));
        $this->assertEquals(0.4, SavingsService::factorForGridType(null));
    }
}
