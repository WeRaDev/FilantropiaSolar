<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Tests\Unit\Service;

use OCA\FilantropiaSolar\Service\StationLifecycle;
use PHPUnit\Framework\TestCase;

class StationLifecycleTest extends TestCase
{
	public function testValidStates(): void
	{
		$this->assertTrue(StationLifecycle::isValidState('virtual'));
		$this->assertTrue(StationLifecycle::isValidState('planned'));
		$this->assertTrue(StationLifecycle::isValidState('running'));
		$this->assertFalse(StationLifecycle::isValidState('active'));
		$this->assertFalse(StationLifecycle::isValidState(''));
	}

	public function testDefaultStateForNew(): void
	{
		$this->assertSame('virtual', StationLifecycle::defaultStateForNew(true, 'user'));
		$this->assertSame('virtual', StationLifecycle::defaultStateForNew(false, 'user'));
		$this->assertSame('virtual', StationLifecycle::defaultStateForNew(false, 'crm'));
		$this->assertSame('running', StationLifecycle::defaultStateForNew(false, 'dataset'));
	}

	public function testPublicVisibility(): void
	{
		$this->assertFalse(StationLifecycle::isPublic('virtual', false));
		$this->assertTrue(StationLifecycle::isPublic('planned', false));
		$this->assertTrue(StationLifecycle::isPublic('running', false));
		$this->assertFalse(StationLifecycle::isPublic('planned', true));
		$this->assertFalse(StationLifecycle::isPublic('running', true));
	}

	public function testPublicCategory(): void
	{
		$this->assertSame('none', StationLifecycle::publicCategory('virtual', false));
		$this->assertSame('planned', StationLifecycle::publicCategory('planned', false));
		$this->assertSame('existing', StationLifecycle::publicCategory('running', false));
		$this->assertSame('none', StationLifecycle::publicCategory('running', true));
	}

	public function testRunningMode(): void
	{
		$this->assertNull(StationLifecycle::runningMode('virtual', true));
		$this->assertNull(StationLifecycle::runningMode('planned', false));
		$this->assertSame('active', StationLifecycle::runningMode('running', true));
		$this->assertSame('offline', StationLifecycle::runningMode('running', false));
	}

	public function testIsVirtualFlag(): void
	{
		$this->assertTrue(StationLifecycle::isVirtualFlag('virtual'));
		$this->assertFalse(StationLifecycle::isVirtualFlag('planned'));
		$this->assertFalse(StationLifecycle::isVirtualFlag('running'));
	}
}
