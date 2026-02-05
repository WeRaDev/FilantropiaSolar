# FilantropiaSolar Nextcloud App Development Guide

## Overview
This document captures Nextcloud-specific development patterns, solutions, and best practices learned during FilantropiaSolar v3.0.x development.

## Version History
- v3.0.0 (2026-01-16): Initial Nextcloud app launch with basic UI
- v3.0.1 (2026-01-17): Data integration from Mendeley PV dataset via PHP proxy

---

# Nextcloud App Architecture

## Directory Structure (Recommended)
```
filantropia_solar/
├── appinfo/
│   ├── info.xml                    # App metadata, NC version compatibility
│   └── routes.php                  # REST API route definitions
├── lib/
│   ├── AppInfo/Application.php     # DI container registration
│   ├── Controller/                 # Request handlers
│   │   ├── PageController.php      # Main page rendering
│   │   └── *ApiController.php      # REST API controllers
│   ├── Db/                         # Database layer
│   │   ├── *Entity.php             # Entity definitions
│   │   └── *Mapper.php             # QBMapper implementations
│   ├── Service/                    # Business logic
│   └── Migration/                  # Database migrations
├── src/                            # Vue.js frontend
│   ├── main.js                     # App entry point
│   ├── App.vue                     # Root component
│   └── views/                      # Page components
├── templates/
│   └── index.php                   # Vue mount point
├── js/                             # Compiled JS (gitignored)
├── css/                            # Compiled CSS
├── img/                            # App icons and assets
└── l10n/                           # Translations
```

## Technology Stack Decisions

### PHP Backend (Required)
- **Framework**: OCP AppFramework
- **Database**: QBMapper ORM (Nextcloud's abstraction)
- **HTTP Client**: `OCP\Http\Client\IClientService`
- **Dependency Injection**: Constructor injection with type hints

### Frontend Options (Choose Based on Needs)
| Complexity | Recommendation | When to Use |
|------------|----------------|-------------|
| Minimal | PHP templates only | Static content, simple forms |
| Low | PHP + Vanilla JS | AJAX calls, basic interactivity |
| Medium | PHP + Chart.js/Leaflet | Data visualization |
| High | Vue 2 + @nextcloud/vue v8 | Full NC28 integration |
| Future | Vue 3 + @nextcloud/vue v9 | Requires NC31+ |

### Critical Decision: Vue 2 vs Vue 3
**NC28 requires Vue 2.7**. The `@nextcloud/vue` v8 is Vue 2-based; v9 requires NC31+.
- Vue 3 migration in Nextcloud ecosystem is incomplete
- Use Vue 2 for NC28-30 compatibility
- Plan Vue 3 migration when NC31 becomes baseline

---

# Problem-Solution Registry (Nextcloud Specific)

## SOL-NC-001: Internal Host Connection Blocked
**Problem**: PHP HTTP client cannot reach internal Docker services
**Symptom**: "Host ml-service was not connected to because it violates local access rules"
**Root Cause**: Nextcloud security feature blocks connections to internal/local hosts
**Solution**: Add config setting:
```bash
docker exec -u www-data <container> php occ config:system:set allow_local_remote_servers --value=true --type=boolean
```
**Prevention**: Document this in deployment guide; add to docker-compose setup script

## SOL-NC-002: IL10N Dependency Injection Failure
**Problem**: `Could not resolve OCP\IL10N! Class can not be instantiated`
**Root Cause**: IL10N cannot be directly resolved from container; needs app context
**Solution**: Use `IFactory` instead:
```php
public function __construct(
    private readonly IFactory $l10nFactory,
) {
    $this->l10n = $l10nFactory->get(Application::APP_ID);
}
```
**Prevention**: Never inject IL10N directly; always use IFactory

## SOL-NC-003: Header Overlap with NC Navigation
**Problem**: Custom app header overlaps with Nextcloud's 50px navigation header
**Root Cause**: App CSS positioned at `top: 0` instead of accounting for NC header
**Solution**: Use sidebar navigation pattern; set `height: calc(100vh - 50px)`
**Prevention**: Always use sidebar navigation for NC apps; never add top-positioned headers

## SOL-NC-004: PHP Changes Not Reflected
**Problem**: PHP edits don't appear in browser after saving
**Root Cause**: PHP OPcache caches bytecode
**Solution**: Restart Apache:
```bash
docker exec <container> apache2ctl graceful
```
**Prevention**: Always restart Apache after PHP edits in development

## SOL-NC-005: Database Index Name Too Long
**Problem**: MariaDB 64-character limit for index names
**Symptom**: "Primary index name too long" during app:enable
**Solution**: Use short table name prefixes (e.g., `fs_` instead of `filantropia_`)
**Prevention**: Keep table names under 30 chars to allow for index naming

## SOL-NC-006: Volume Mount Conflicts
**Problem**: "read-only file system" error with nested Docker volumes
**Root Cause**: Cannot nest writable volume inside read-only mount
**Solution**: Remove `:ro` flag from parent volume mount or restructure
```yaml
# BAD
volumes:
  - ./code:/app:ro
  - data_volume:/app/data

# GOOD
volumes:
  - ./code:/app
  - data_volume:/app/data
```

## SOL-NC-007: Vue/Axios API Calls Fail
**Problem**: Browser cannot reach internal services directly
**Root Cause**: CORS/CSP blocks cross-origin requests; internal hostnames not resolvable from browser
**Solution**: Create PHP proxy endpoints that forward requests to internal services
```php
// Controller
public function index(): JSONResponse {
    $client = $this->clientService->newClient();
    $response = $client->get('http://ml-service:8501/data/installations');
    return new JSONResponse(json_decode($response->getBody(), true));
}
```
**Prevention**: Always proxy external/internal service calls through PHP

## SOL-NC-008: JS Resource Not Found
**Problem**: "Could not find resource filantropia_solar/js/..." error
**Root Cause**: Build output not in expected location or cache stale
**Solution**: Clear JS cache and rebuild:
```bash
rm -rf node_modules/.cache js/*
npm run build
docker exec -u www-data <container> php occ maintenance:repair
```

---

# API Design Patterns

## Controller Attributes (NC28+)
Use PHP 8 attributes for route configuration:
```php
use OCP\AppFramework\Http\Attribute\NoAdminRequired;
use OCP\AppFramework\Http\Attribute\NoCSRFRequired;

class MyApiController extends ApiController {
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function index(): JSONResponse {
        // ...
    }
}
```

## Service Proxy Pattern
When integrating external services (ML, weather APIs):
```php
class InstallationApiController extends ApiController {
    private const ML_SERVICE_URL = 'http://ml-service:8501';
    
    public function __construct(
        IRequest $request,
        private readonly IClientService $clientService,
        private readonly LoggerInterface $logger,
    ) {
        parent::__construct(APP_ID, $request);
    }
    
    #[NoAdminRequired]
    #[NoCSRFRequired]
    public function index(): JSONResponse {
        try {
            $client = $this->clientService->newClient();
            $response = $client->get(self::ML_SERVICE_URL . '/data/installations');
            return new JSONResponse(json_decode($response->getBody(), true));
        } catch (\Exception $e) {
            $this->logger->error('ML service error', ['exception' => $e]);
            return $this->fallbackToDatabase();
        }
    }
}
```

## Route Definition
```php
// appinfo/routes.php
return [
    'routes' => [
        // Page routes (return HTML)
        ['name' => 'page#index', 'url' => '/', 'verb' => 'GET'],
        
        // API routes (return JSON)
        ['name' => 'installation_api#index', 'url' => '/api/v1/installations', 'verb' => 'GET'],
        ['name' => 'installation_api#show', 'url' => '/api/v1/installations/{id}', 'verb' => 'GET'],
    ],
];
```

---

# Frontend Patterns

## Vue Component Structure
```vue
<template>
    <div class="main-view">
        <!-- Content -->
    </div>
</template>

<script>
import { generateUrl } from '@nextcloud/router'
import axios from '@nextcloud/axios'

export default {
    name: 'MainView',
    data() {
        return {
            items: [],
        }
    },
    mounted() {
        this.fetchData()
    },
    methods: {
        async fetchData() {
            try {
                const url = generateUrl('/apps/APP_ID/api/v1/endpoint')
                const response = await axios.get(url)
                this.items = response.data.items || []
            } catch (error) {
                console.error('API error:', error)
            }
        },
    },
}
</script>

<style lang="scss" scoped>
@import '../style/_variables.scss';
// Styles
</style>
```

## Sidebar Navigation Layout
```vue
<template>
    <NcAppContent>
        <div class="app-layout">
            <aside class="sidebar">
                <nav>
                    <router-link to="/">Installations</router-link>
                    <router-link to="/dashboard">Dashboard</router-link>
                </nav>
            </aside>
            <main class="content">
                <router-view />
            </main>
        </div>
    </NcAppContent>
</template>

<style scoped>
.app-layout {
    display: flex;
    height: calc(100vh - 50px); /* Account for NC header */
}
.sidebar {
    width: 200px;
    flex-shrink: 0;
}
.content {
    flex: 1;
    overflow: auto;
}
</style>
```

---

# Docker Development Environment

## docker-compose.yml Template
```yaml
services:
  nextcloud:
    image: nextcloud:28-apache
    ports:
      - "8080:80"
    environment:
      - MYSQL_HOST=db
      - MYSQL_DATABASE=nextcloud
      - MYSQL_USER=nextcloud
      - MYSQL_PASSWORD=dev_password
    volumes:
      - nextcloud_data:/var/www/html
      - ./:/var/www/html/custom_apps/your_app
    depends_on:
      - db

  db:
    image: mariadb:10.11
    environment:
      - MYSQL_ROOT_PASSWORD=root_dev
      - MYSQL_DATABASE=nextcloud
      - MYSQL_USER=nextcloud
      - MYSQL_PASSWORD=dev_password
    volumes:
      - db_data:/var/lib/mysql

  ml-service:
    build: ./ml-service
    ports:
      - "8501:8501"
    volumes:
      - ./ml-service:/app
      - ../Data:/app/data:ro

volumes:
  nextcloud_data:
  db_data:
```

## Common Commands
```bash
# Start environment
docker compose up -d

# Enable app
docker exec -u www-data <nc-container> php occ app:enable your_app

# Allow internal connections (required for service proxy)
docker exec -u www-data <nc-container> php occ config:system:set allow_local_remote_servers --value=true --type=boolean

# After PHP changes
docker exec <nc-container> apache2ctl graceful

# Clear caches
docker exec -u www-data <nc-container> php occ maintenance:repair

# Check logs
docker exec <nc-container> tail -50 /var/www/html/data/nextcloud.log

# Rebuild frontend
rm -rf node_modules/.cache js/* && npm run build
```

---

# Database Migration Patterns

## Migration Class Template
```php
<?php
namespace OCA\YourApp\Migration;

use Closure;
use OCP\DB\ISchemaWrapper;
use OCP\Migration\IOutput;
use OCP\Migration\SimpleMigrationStep;

class Version001Date20260117 extends SimpleMigrationStep {
    public function changeSchema(IOutput $output, Closure $schemaClosure, array $options): ?ISchemaWrapper {
        /** @var ISchemaWrapper $schema */
        $schema = $schemaClosure();
        
        if (!$schema->hasTable('fs_installations')) {
            $table = $schema->createTable('fs_installations');
            $table->addColumn('id', 'bigint', [
                'autoincrement' => true,
                'notnull' => true,
            ]);
            $table->addColumn('user_id', 'string', [
                'notnull' => true,
                'length' => 64,
            ]);
            // ... more columns
            $table->setPrimaryKey(['id']);
            $table->addIndex(['user_id'], 'fs_inst_user_idx');
        }
        
        return $schema;
    }
}
```

---

# Testing Patterns

## PHPUnit Test Structure
```php
<?php
namespace OCA\YourApp\Tests\Unit\Service;

use OCA\YourApp\Service\YourService;
use PHPUnit\Framework\TestCase;

class YourServiceTest extends TestCase {
    private YourService $service;
    
    protected function setUp(): void {
        $this->service = new YourService();
    }
    
    public function testSomething(): void {
        $result = $this->service->doSomething();
        $this->assertEquals('expected', $result);
    }
}
```

## Running Tests
```bash
# From app directory
./vendor/bin/phpunit tests/
```

---

# Performance Considerations

## Caching
Use Nextcloud's caching layer:
```php
use OCP\ICacheFactory;

public function __construct(
    private readonly ICacheFactory $cacheFactory,
) {
    $this->cache = $cacheFactory->createDistributed('your_app');
}

public function getData(): array {
    $cached = $this->cache->get('key');
    if ($cached !== null) {
        return $cached;
    }
    
    $data = $this->fetchData();
    $this->cache->set('key', $data, 3600); // 1 hour TTL
    return $data;
}
```

## Background Jobs
For long-running tasks:
```php
use OCP\BackgroundJob\TimedJob;

class MyJob extends TimedJob {
    public function __construct() {
        $this->setInterval(3600); // Run hourly
    }
    
    protected function run($argument): void {
        // Do work
    }
}
```

---

# Retrospective: v3.0.1 Session (2026-01-17)

## What Went Well
- Successfully integrated Mendeley PV dataset (9 installations, 302.56 kWp)
- PHP proxy pattern solved browser-to-service connectivity
- `allow_local_remote_servers` config resolved internal network access

## Blockers Encountered
1. **Direct ML service calls failing** - Browser couldn't reach localhost:8501
   - Solution: PHP proxy pattern
   - Time to resolve: ~20 minutes
2. **Internal host blocked** - Nextcloud security feature
   - Solution: `allow_local_remote_servers` config
   - Time to resolve: ~10 minutes

## Key Learnings
1. **Never call external services directly from Vue** - Always proxy through PHP
2. **Nextcloud has security restrictions** - Document and automate config requirements
3. **Test API endpoints with curl first** - Validate PHP proxy before frontend integration

## Cost-Effectiveness Metrics
- Session duration: ~45 minutes
- Blockers resolved: 2
- Pattern reuse: 100% (proxy pattern now standard)
- Documentation created: 8 solutions added to registry

---

# Next Steps for v3.0.2

## Feature Parity with v1.2.3 Desktop App
1. **Analysis Configuration Tab**: Mode selection, installation picker, date controls
2. **Analysis Results Tab**: Split panel with summary and hourly breakdown
3. **Interactive Charts Tab**: Chart.js implementation with day navigation
4. **Custom Station Simulation**: User-defined capacity at chosen location

## Implementation Priority
1. Chart.js integration for energy visualization
2. Day navigation controls (Previous/Center/Next)
3. Weather data display
4. Analysis configuration panel
5. Results export functionality

---

# References

## Official Documentation
- [Nextcloud Developer Manual](https://docs.nextcloud.com/server/latest/developer_manual/)
- [App Tutorial](https://docs.nextcloud.com/server/latest/developer_manual/app_development/tutorial.html)
- [@nextcloud/vue Components](https://nextcloud-vue-components.netlify.app/)
- [OCP API Reference](https://docs.nextcloud.com/server/latest/developer_manual/digging_deeper/api_reference.html)

## Related Projects
- [nextcloud/maps](https://github.com/nextcloud/maps) - Geographic visualization
- [Rello/analytics](https://github.com/Rello/analytics) - Data visualization patterns
- [julien-nc/cospend-nc](https://github.com/julien-nc/cospend-nc) - Shared resource tracking
