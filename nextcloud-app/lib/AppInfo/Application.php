<?php

declare(strict_types=1);

namespace OCA\FilantropiaSolar\AppInfo;

use OCA\FilantropiaSolar\BackgroundJob\PredictionJob;
use OCA\FilantropiaSolar\BackgroundJob\WeatherSyncJob;
use OCP\AppFramework\App;
use OCP\AppFramework\Bootstrap\IBootContext;
use OCP\AppFramework\Bootstrap\IBootstrap;
use OCP\AppFramework\Bootstrap\IRegistrationContext;
use OCP\INavigationManager;
use OCP\IURLGenerator;
use OCP\L10N\IFactory;

/**
 * FilantropiaSolar Application Bootstrap
 *
 * Handles app initialization, dependency injection, and event registration.
 */
class Application extends App implements IBootstrap
{
    public const APP_ID = 'filantropia_solar';

    /**
     * Golden olive brand colors for consistent theming.
     */
    public const BRAND_COLORS = [
        'primary' => '#C4B552',
        'secondary' => '#D4C563',
        'olive' => '#A89D3F',
        'orange' => '#E8A94B',
        'cream' => '#FDFBF5',
        'charcoal' => '#2D2D2D',
    ];

    /**
     * Default grid electricity price in EUR/kWh.
     */
    public const DEFAULT_GRID_PRICE = 0.15;

    /**
     * Portuguese location coordinates for weather data.
     */
    public const LOCATION_COORDS = [
        'Lisbon' => ['lat' => 38.7223, 'lon' => -9.1393],
        'Setubal' => ['lat' => 38.5244, 'lon' => -8.8882],
        'Faro' => ['lat' => 37.0194, 'lon' => -7.9304],
        'Braga' => ['lat' => 41.5454, 'lon' => -8.4265],
        'Tavira' => ['lat' => 37.1279, 'lon' => -7.6486],
        'Loule' => ['lat' => 37.1376, 'lon' => -8.0197],
    ];

    public function __construct()
    {
        parent::__construct(self::APP_ID);
    }

    /**
     * Register services, event listeners, and middleware.
     */
    public function register(IRegistrationContext $context): void
    {
        // Register services for dependency injection
        // $context->registerService(InstallationService::class, function ($c) {
        //     return new InstallationService(
        //         $c->get(InstallationMapper::class),
        //         $c->get(LoggerInterface::class)
        //     );
        // });

        // Register event listeners
        // $context->registerEventListener(
        //     UserDeletedEvent::class,
        //     UserDeletedListener::class
        // );

        // Register middleware
        // $context->registerMiddleware(AuthMiddleware::class);
    }

    /**
     * Boot the application after all apps are loaded.
     */
    public function boot(IBootContext $context): void
    {
        $serverContainer = $context->getServerContainer();

        // Register navigation entry programmatically
        /** @var INavigationManager $navigationManager */
        $navigationManager = $serverContainer->get(INavigationManager::class);
        $navigationManager->add(function () use ($serverContainer) {
            /** @var IURLGenerator $urlGenerator */
            $urlGenerator = $serverContainer->get(IURLGenerator::class);
            /** @var IFactory $l10nFactory */
            $l10nFactory = $serverContainer->get(IFactory::class);
            $l10n = $l10nFactory->get(self::APP_ID);

            return [
                'id' => self::APP_ID,
                'order' => 10,
                'href' => $urlGenerator->linkToRoute('filantropia_solar.page.index'),
                'icon' => $urlGenerator->imagePath(self::APP_ID, 'app.png'),
                'name' => $l10n->t('FilantropiaSolar'),
            ];
        });

        // Initialize any app-wide state
        $this->registerBackgroundJobs($context);
    }

    /**
     * Register background jobs for weather sync and predictions.
     */
    private function registerBackgroundJobs(IBootContext $context): void
    {
        // Background jobs are registered via info.xml, but can also be done here:
        // $jobList = $context->getServerContainer()->get(IJobList::class);
        // $jobList->add(WeatherSyncJob::class);
        // $jobList->add(PredictionJob::class);
    }
}
