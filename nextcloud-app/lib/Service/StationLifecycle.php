<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Service;

/**
 * Station lifecycle helpers (MVP-1 / D3–D4).
 *
 * Ops labels: virtual | planned | running
 * Running mode: offline (predicted) | active (measured historical present)
 * Public map: planned | existing | none (virtual, soft-removed, or public_archived)
 * public_archived: still running for stats; hidden from public map only
 */
final class StationLifecycle
{
	public const VIRTUAL = 'virtual';
	public const PLANNED = 'planned';
	public const RUNNING = 'running';

	public const MODE_OFFLINE = 'offline';
	public const MODE_ACTIVE = 'active';

	public const PUBLIC_NONE = 'none';
	public const PUBLIC_PLANNED = 'planned';
	public const PUBLIC_EXISTING = 'existing';
	/** Map-hidden running station that still counts in aggregates. */
	public const PUBLIC_ARCHIVED = 'archived';

	/** @var list<string> */
	public const STATES = [self::VIRTUAL, self::PLANNED, self::RUNNING];

	public static function isValidState(string $state): bool
	{
		return in_array($state, self::STATES, true);
	}

	/**
	 * Default lifecycle for newly created rows.
	 */
	public static function defaultStateForNew(bool $isVirtual, string $source): string
	{
		if ($isVirtual || $source === 'user' || $source === 'crm') {
			return self::VIRTUAL;
		}

		return self::RUNNING;
	}

	/**
	 * Whether station contributes to public/ops energy statistics
	 * (planned + running, including public-archived running).
	 */
	public static function isPublic(string $lifecycleState, bool $softRemoved, bool $publicArchived = false): bool
	{
		if ($softRemoved) {
			return false;
		}
		// public_archived does not remove statistical contribution
		unset($publicArchived);

		return $lifecycleState === self::PLANNED || $lifecycleState === self::RUNNING;
	}

	/**
	 * Whether station should appear on the public website map/list.
	 */
	public static function isPublicMapVisible(string $lifecycleState, bool $softRemoved, bool $publicArchived = false): bool
	{
		if ($softRemoved || $publicArchived) {
			return false;
		}

		return $lifecycleState === self::PLANNED || $lifecycleState === self::RUNNING;
	}

	public static function publicCategory(string $lifecycleState, bool $softRemoved, bool $publicArchived = false): string
	{
		if ($softRemoved || $lifecycleState === self::VIRTUAL) {
			return self::PUBLIC_NONE;
		}
		if ($lifecycleState === self::PLANNED) {
			return self::PUBLIC_PLANNED;
		}
		if ($lifecycleState === self::RUNNING) {
			return $publicArchived ? self::PUBLIC_ARCHIVED : self::PUBLIC_EXISTING;
		}

		return self::PUBLIC_NONE;
	}

	/**
	 * Running mode only applies when lifecycle_state=running.
	 */
	public static function runningMode(string $lifecycleState, bool $hasMeasuredData): ?string
	{
		if ($lifecycleState !== self::RUNNING) {
			return null;
		}

		return $hasMeasuredData ? self::MODE_ACTIVE : self::MODE_OFFLINE;
	}

	/**
	 * Keep is_virtual in sync with lifecycle for legacy consumers.
	 */
	public static function isVirtualFlag(string $lifecycleState): bool
	{
		return $lifecycleState === self::VIRTUAL;
	}

	/**
	 * Whether Virtual → Planned is allowed (or already Planned = idempotent OK).
	 */
	public static function canPromoteToPlanned(string $lifecycleState, bool $softRemoved): bool
	{
		if ($softRemoved) {
			return false;
		}

		return $lifecycleState === self::VIRTUAL || $lifecycleState === self::PLANNED;
	}

	/**
	 * Whether Planned → Running is allowed (or already Running = idempotent OK).
	 */
	public static function canMarkInstalled(string $lifecycleState, bool $softRemoved): bool
	{
		if ($softRemoved) {
			return false;
		}

		return $lifecycleState === self::PLANNED || $lifecycleState === self::RUNNING;
	}

	/**
	 * Soft-remove is allowed for any non-already-removed station.
	 */
	public static function canSoftRemove(bool $softRemoved): bool
	{
		return !$softRemoved;
	}

	/**
	 * Ops may set any non-soft-removed station to any valid lifecycle state.
	 */
	public static function canSetLifecycleState(string $lifecycleState, bool $softRemoved): bool
	{
		if ($softRemoved) {
			return false;
		}

		return self::isValidState($lifecycleState);
	}
}
