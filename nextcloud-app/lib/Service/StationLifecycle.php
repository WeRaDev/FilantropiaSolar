<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Service;

/**
 * Station lifecycle helpers (MVP-1 / D3–D4).
 *
 * Ops labels: virtual | planned | running
 * Running mode: offline (predicted) | active (measured historical present)
 * Public: planned | existing | none (virtual or soft-removed)
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

	public static function isPublic(string $lifecycleState, bool $softRemoved): bool
	{
		if ($softRemoved) {
			return false;
		}

		return $lifecycleState === self::PLANNED || $lifecycleState === self::RUNNING;
	}

	public static function publicCategory(string $lifecycleState, bool $softRemoved): string
	{
		if ($softRemoved || $lifecycleState === self::VIRTUAL) {
			return self::PUBLIC_NONE;
		}
		if ($lifecycleState === self::PLANNED) {
			return self::PUBLIC_PLANNED;
		}
		if ($lifecycleState === self::RUNNING) {
			return self::PUBLIC_EXISTING;
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
}
