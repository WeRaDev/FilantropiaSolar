<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Service;

use DateInterval;
use DateTime;
use DateTimeImmutable;
use DateTimeInterface;
use DateTimeZone;

/**
 * Operational timezone for series hours, Active badge, and production windows.
 * Storage uses naive Y-m-d H:i:s wall-clock in this zone (Europe/Lisbon).
 */
final class AppTimezone
{
	public const ZONE_ID = 'Europe/Lisbon';

	public static function zone(): DateTimeZone
	{
		return new DateTimeZone(self::ZONE_ID);
	}

	public static function now(?DateTimeInterface $now = null): DateTimeImmutable
	{
		if ($now === null) {
			return new DateTimeImmutable('now', self::zone());
		}

		return DateTimeImmutable::createFromInterface($now)->setTimezone(self::zone());
	}

	/**
	 * Last complete hour start in app timezone (e.g. 13:00 when now is 13:42 Lisbon).
	 */
	public static function lastCompleteHour(?DateTimeInterface $now = null): DateTimeImmutable
	{
		$nowLocal = self::now($now);
		$floored = $nowLocal->setTime((int) $nowLocal->format('H'), 0, 0);

		return $floored->sub(new DateInterval('PT1H'));
	}

	public static function formatHourKey(DateTimeInterface $dt): string
	{
		$local = DateTimeImmutable::createFromInterface($dt)->setTimezone(self::zone());

		return $local->setTime((int) $local->format('H'), 0, 0)->format('Y-m-d H:i:s');
	}

	public static function mutableHour(DateTimeInterface $dt): DateTime
	{
		return DateTime::createFromImmutable(
			DateTimeImmutable::createFromInterface($dt)->setTimezone(self::zone())
				->setTime((int) DateTimeImmutable::createFromInterface($dt)->setTimezone(self::zone())->format('H'), 0, 0)
		);
	}
}
