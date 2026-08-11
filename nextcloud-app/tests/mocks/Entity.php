<?php

declare(strict_types=1);

namespace OCP\AppFramework\Db;

/**
 * Minimal Entity stub for unit tests without Nextcloud core.
 */
class Entity
{
	/** @var array<string, string> */
	private array $fieldTypes = [];

	/** @var mixed */
	protected $id = null;

	protected function addType(string $fieldName, string $type): void
	{
		$this->fieldTypes[$fieldName] = $type;
	}

	public function __call(string $name, array $args)
	{
		if (str_starts_with($name, 'get') && $name !== 'get') {
			$prop = lcfirst(substr($name, 3));
			if (property_exists($this, $prop)) {
				return $this->$prop;
			}
		}
		if (str_starts_with($name, 'set') && $name !== 'set' && count($args) >= 1) {
			$prop = lcfirst(substr($name, 3));
			if (property_exists($this, $prop)) {
				$this->$prop = $args[0];
				return null;
			}
		}
		throw new \BadMethodCallException('Unknown method ' . $name);
	}

	public function getId(): mixed
	{
		return $this->id;
	}

	public function setId(mixed $id): void
	{
		$this->id = $id;
	}
}
