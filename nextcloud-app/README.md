# FilantropiaSolar for Nextcloud

Solar energy management app for Nextcloud. Monitor PV installations, track energy production, and calculate savings against grid electricity prices.

## Features

- **Installation Management**: Add and manage multiple PV installations with geographic coordinates
- **Interactive Map**: Leaflet-based map with golden solar panel markers
- **Energy Charts**: 24-hour production/consumption visualization with Chart.js
- **Savings Calculator**: Track cost savings vs grid at 0.15 EUR/kWh default rate
- **Weather Integration**: Open-Meteo API for Portuguese locations
- **Multi-language**: English and Portuguese translations

## Requirements

- Nextcloud 28, 29, 30, or 31
- PHP 8.1, 8.2, 8.3, or 8.4
- Node.js 18+ (for development)

## Installation

### From Nextcloud App Store (Recommended)
1. Go to Apps in your Nextcloud
2. Search for "FilantropiaSolar"
3. Click Install

### Manual Installation
```bash
# Clone to Nextcloud apps directory
cd /path/to/nextcloud/apps
git clone https://github.com/youruser/filantropia_solar.git

# Install dependencies and build
cd filantropia_solar
npm install
npm run build

# Enable the app
cd /path/to/nextcloud
php occ app:enable filantropia_solar
```

## Development

```bash
# Install dependencies
npm install

# Development build with watch
npm run watch

# Production build
npm run build

# Lint
npm run lint
npm run lint:fix
```

## Project Structure

```
filantropia_solar/
├── appinfo/
│   ├── info.xml          # App metadata
│   └── routes.php        # API routes
├── lib/
│   ├── AppInfo/          # Bootstrap
│   ├── Controller/       # API controllers
│   ├── Db/               # Entities and mappers
│   ├── Migration/        # Database migrations
│   └── Service/          # Business logic
├── src/
│   ├── main.js           # Vue entry point
│   ├── App.vue           # Root component
│   ├── views/            # Page components
│   ├── store/            # Pinia stores
│   └── style/            # SCSS styles
├── templates/
│   └── index.php         # HTML shell
├── l10n/                 # Translations
└── js/                   # Built assets
```

## Golden Brand Colors

The app uses a distinctive golden olive palette:

- Primary: `#C4B552` - Production values, highlights
- Secondary: `#D4C563` - Lighter accents
- Olive: `#A89D3F` - Borders, subtle elements
- Warm Orange: `#E8A94B` - Consumption data
- Cream Background: `#FDFBF5`

## API Endpoints

### Installations
- `GET /api/v1/installations` - List all installations
- `GET /api/v1/installations/{id}` - Get single installation
- `POST /api/v1/installations` - Create installation
- `PUT /api/v1/installations/{id}` - Update installation
- `DELETE /api/v1/installations/{id}` - Delete installation

### Energy Data
- `GET /api/v1/installations/{id}/readings` - Get energy readings
- `GET /api/v1/installations/{id}/stats` - Get statistics
- `POST /api/v1/installations/{id}/import` - Import readings

### Dashboard
- `GET /api/v1/dashboard` - Network overview
- `GET /api/v1/dashboard/savings` - Total savings

### Weather
- `GET /api/v1/weather/locations` - Available locations
- `GET /api/v1/weather/forecast` - Weather forecast

## Portuguese Locations

Built-in coordinates for:
- Lisbon (38.7223, -9.1393)
- Setubal (38.5244, -8.8882)
- Faro (37.0194, -7.9304)
- Braga (41.5454, -8.4265)
- Tavira (37.1279, -7.6486)
- Loule (37.1376, -8.0197)

## ML Integration (Future)

The app is designed to integrate with a Python ML microservice for:
- Energy production predictions (26-feature model)
- Weather simulation using KNN
- Ensemble model (RF 0.4, GB 0.35, Linear 0.25 weights)

## License

AGPL-3.0

## Credits

- Original Python application: FilantropiaSolar v1.2.x
- Nextcloud Vue components: @nextcloud/vue
- Maps: Leaflet + OpenStreetMap
- Charts: Chart.js
- Weather data: Open-Meteo API

---

Built with the Warp Agent development system.
