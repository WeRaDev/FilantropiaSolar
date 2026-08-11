<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Tests\Unit\Db;

use OCA\FilantropiaSolar\Db\Installation;
use OCA\FilantropiaSolar\Service\StationLifecycle;
use PHPUnit\Framework\TestCase;

/**
 * Unit tests for Installation Entity
 */
class InstallationTest extends TestCase
{
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

	public function testGetGridPriceFloatDefault(): void
	{
		$installation = new Installation();
		$this->assertEquals(0.15, $installation->getGridPriceFloat());
	}

	public function testGetGridPriceFloatCustom(): void
	{
		$installation = new Installation();
		$installation->setGridPriceKwh('0.20');
		$this->assertEquals(0.20, $installation->getGridPriceFloat());
	}

	public function testGetCoordinates(): void
	{
		$installation = new Installation();
		$installation->setLatitude('38.7223');
		$installation->setLongitude('-9.1393');
		$coords = $installation->getCoordinates();
		$this->assertEqualsWithDelta(38.7223, $coords[0], 0.0001);
		$this->assertEqualsWithDelta(-9.1393, $coords[1], 0.0001);
	}

	public function testJsonSerialize(): void
	{
		$installation = new Installation();
		$installation->setUserId('user123');
		$installation->setName('Test Solar');
		$installation->setLatitude('38.7223');
		$installation->setLongitude('-9.1393');
		$installation->setCapacityKwp('5.50');
		$installation->setLocation('Lisbon');
		$installation->setSerialNumber('42');
		$installation->applyLifecycleState(StationLifecycle::PLANNED);
		$installation->setSoftRemoved(false);
		$installation->setOdooLeadId(99);

		$json = $installation->jsonSerialize();

		$this->assertArrayHasKey('lifecycle_state', $json);
		$this->assertArrayHasKey('soft_removed', $json);
		$this->assertArrayHasKey('odoo_lead_id', $json);
		$this->assertArrayHasKey('is_public', $json);
		$this->assertArrayHasKey('public_category', $json);
		$this->assertEquals('Test Solar', $json['name']);
		$this->assertSame('planned', $json['lifecycle_state']);
		$this->assertFalse($json['soft_removed']);
		$this->assertSame(99, $json['odoo_lead_id']);
		$this->assertTrue($json['is_public']);
		$this->assertSame('planned', $json['public_category']);
		$this->assertFalse($json['is_virtual']);
		$this->assertNull($json['running_mode']);
	}

	public function testApplyLifecycleStateSyncsIsVirtual(): void
	{
		$installation = new Installation();
		$installation->applyLifecycleState(StationLifecycle::VIRTUAL);
		$this->assertTrue($installation->getIsVirtual());
		$this->assertSame('virtual', $installation->getLifecycleState());
		$this->assertFalse($installation->isPubliclyVisible());

		$installation->applyLifecycleState(StationLifecycle::RUNNING);
		$this->assertFalse($installation->getIsVirtual());
		$this->assertSame('existing', $installation->getPublicCategory());
	}

	public function testRunningModeUsesMeasuredFlag(): void
	{
		$installation = new Installation();
		$installation->applyLifecycleState(StationLifecycle::RUNNING);
		$installation->setHasMeasuredData(false);
		$this->assertSame('offline', $installation->getRunningMode());
		$installation->setHasMeasuredData(true);
		$this->assertSame('active', $installation->getRunningMode());
	}

	public function testApplyLifecycleStateRejectsInvalid(): void
	{
		$this->expectException(\InvalidArgumentException::class);
		$installation = new Installation();
		$installation->applyLifecycleState('nope');
	}

	public function testCoordinatePrecision(): void
	{
		$installation = new Installation();
		$installation->setLatitude('38.72234567');
		$installation->setLongitude('-9.13934567');
		$coords = $installation->getCoordinates();
		$this->assertEqualsWithDelta(38.72234567, $coords[0], 0.00000001);
		$this->assertEqualsWithDelta(-9.13934567, $coords[1], 0.00000001);
	}
}
