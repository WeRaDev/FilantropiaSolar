<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Tests\Unit\Service;

use OCA\FilantropiaSolar\Service\FilantropiaAccess;
use OCP\IGroupManager;
use OCP\IUser;
use OCP\IUserSession;
use PHPUnit\Framework\MockObject\MockObject;
use PHPUnit\Framework\TestCase;

class FilantropiaAccessTest extends TestCase
{
	private MockObject&IUserSession $session;
	private MockObject&IGroupManager $groups;
	private FilantropiaAccess $access;

	protected function setUp(): void
	{
		$this->session = $this->createMock(IUserSession::class);
		$this->groups = $this->createMock(IGroupManager::class);
		$this->access = new FilantropiaAccess($this->session, $this->groups);
	}

	public function testNotLoggedInCannotMutate(): void
	{
		$this->session->method('getUser')->willReturn(null);
		$this->assertFalse($this->access->isLoggedIn());
		$this->assertFalse($this->access->canEditMasterData());
		$this->assertFalse($this->access->canUploadMeasured());
		$this->assertFalse($this->access->canPersistSimulated());
	}

	public function testLoggedInUserCanUploadMeasuredOnly(): void
	{
		$user = $this->createMock(IUser::class);
		$user->method('getUID')->willReturn('alice');
		$this->session->method('getUser')->willReturn($user);
		$this->groups->method('isAdmin')->with('alice')->willReturn(false);
		$this->groups->method('isInGroup')->with('alice', FilantropiaAccess::GROUP_ADMIN)->willReturn(false);

		$this->assertTrue($this->access->canUploadMeasured());
		$this->assertFalse($this->access->canEditMasterData());
		$this->assertFalse($this->access->canChangeLifecycle());
		$this->assertFalse($this->access->canPersistSimulated());
	}

	public function testGroupAdminCanEdit(): void
	{
		$user = $this->createMock(IUser::class);
		$user->method('getUID')->willReturn('ops');
		$this->session->method('getUser')->willReturn($user);
		$this->groups->method('isAdmin')->with('ops')->willReturn(false);
		$this->groups->method('isInGroup')->with('ops', FilantropiaAccess::GROUP_ADMIN)->willReturn(true);

		$this->assertTrue($this->access->isFilantropiaAdmin());
		$this->assertTrue($this->access->canEditMasterData());
		$this->assertTrue($this->access->canChangeLifecycle());
		$this->assertTrue($this->access->canPersistSimulated());
		$this->assertTrue($this->access->canUploadMeasured());
	}

	public function testNcAdminIsFilantropiaAdmin(): void
	{
		$user = $this->createMock(IUser::class);
		$user->method('getUID')->willReturn('admin');
		$this->session->method('getUser')->willReturn($user);
		$this->groups->method('isAdmin')->with('admin')->willReturn(true);

		$this->assertTrue($this->access->isFilantropiaAdmin());
	}
}
