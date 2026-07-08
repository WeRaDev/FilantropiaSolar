<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\Settings;

use OCA\FilantropiaSolar\AppInfo\Application;
use OCP\IL10N;
use OCP\IURLGenerator;
use OCP\Settings\IIconSection;

/**
 * Admin Section
 *
 * Registers the FilantropiaSolar section in Nextcloud's admin settings.
 */
class AdminSection implements IIconSection
{
    public function __construct(
        private readonly IURLGenerator $urlGenerator,
        private readonly IL10N $l10n,
    ) {
    }

    /**
     * Section ID.
     */
    public function getID(): string
    {
        return Application::APP_ID;
    }

    /**
     * Section display name.
     */
    public function getName(): string
    {
        return $this->l10n->t('FilantropiaSolar');
    }

    /**
     * Section priority (lower = higher in list).
     */
    public function getPriority(): int
    {
        return 80;
    }

    /**
     * Section icon URL.
     */
    public function getIcon(): string
    {
        return $this->urlGenerator->imagePath(Application::APP_ID, 'app.svg');
    }
}
