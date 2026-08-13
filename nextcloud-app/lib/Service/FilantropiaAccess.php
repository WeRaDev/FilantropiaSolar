<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Service;

use OCP\IGroupManager;
use OCP\IUser;
use OCP\IUserSession;

/**
 * Authorization for FilantropiaSolar ops mutations.
 *
 * Group FilantropiaSolarAdmin (or Nextcloud admin) may mutate lifecycle/master data
 * and persist simulated series. Any logged-in user may upload measured readings.
 */
class FilantropiaAccess
{
	public const GROUP_ADMIN = 'FilantropiaSolarAdmin';

	public function __construct(
		private readonly IUserSession $userSession,
		private readonly IGroupManager $groupManager,
	) {
	}

	public function currentUser(): ?IUser
	{
		return $this->userSession->getUser();
	}

	public function currentUserId(): ?string
	{
		return $this->currentUser()?->getUID();
	}

	public function isLoggedIn(): bool
	{
		return $this->currentUser() !== null;
	}

	/**
	 * FilantropiaSolarAdmin group member or Nextcloud instance admin.
	 */
	public function isFilantropiaAdmin(?IUser $user = null): bool
	{
		$user = $user ?? $this->currentUser();
		if ($user === null) {
			return false;
		}
		if ($this->groupManager->isAdmin($user->getUID())) {
			return true;
		}

		return $this->groupManager->isInGroup($user->getUID(), self::GROUP_ADMIN);
	}

	public function canEditMasterData(): bool
	{
		return $this->isFilantropiaAdmin();
	}

	public function canChangeLifecycle(): bool
	{
		return $this->isFilantropiaAdmin();
	}

	/** Any logged-in user may upload measured series. */
	public function canUploadMeasured(): bool
	{
		return $this->isLoggedIn();
	}

	/** Persist simulated series: admin/jobs only. */
	public function canPersistSimulated(): bool
	{
		return $this->isFilantropiaAdmin();
	}
}
