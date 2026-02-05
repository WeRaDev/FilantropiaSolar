# FilantropiaSolar Testing Guide

## Quick Start

### 1. Start Development Environment

```bash
cd nextcloud-app

# Build and start all containers
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

### 2. Access Points
- **Nextcloud**: http://localhost:8080
- **ML Service**: http://localhost:8501
- **Database Admin**: http://localhost:8081 (run with `--profile debug`)

### 3. First-Time Setup
1. Open http://localhost:8080
2. Login with `admin` / `admin`
3. Go to **Apps** > **Disabled apps**
4. Find **FilantropiaSolar** and click **Enable**
5. Access the app from the top navigation bar

---

## Automated Tests

### PHP Unit Tests

```bash
# Install PHPUnit (if not in vendor)
composer require --dev phpunit/phpunit

# Run all tests
./vendor/bin/phpunit

# Run specific test suite
./vendor/bin/phpunit --testsuite Unit

# Run with coverage
./vendor/bin/phpunit --coverage-html tests/coverage
```

### JavaScript Tests

```bash
# Install dependencies
npm install

# Run tests
npm run test

# Run with watch mode
npm run test:watch

# Run with coverage
npm run test:coverage
```

### ML Service Tests

```bash
cd ml-service

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio httpx

# Run tests
pytest -v

# Test specific module
pytest tests/test_features.py -v
```

---

## Manual UI Testing Checklist

### Frame 1: Main View (Map + Installation List)

#### Map Panel (Left 70%)
- [ ] Map loads centered on Portugal
- [ ] OpenStreetMap tiles render correctly
- [ ] Golden markers appear for each installation
- [ ] Clicking marker opens popup with name and capacity
- [ ] Map pan/zoom works smoothly
- [ ] Markers cluster appropriately when zoomed out

#### Installation List (Right Sidebar 30%)
- [ ] Header shows "Installations" title
- [ ] "Add" button with golden styling visible
- [ ] Search bar filters installations by name
- [ ] Clear button (X) appears when search has text
- [ ] Installation cards show:
  - [ ] Name
  - [ ] Capacity badge (X.X kWp)
  - [ ] Production value (golden color)
  - [ ] Consumption value (orange color)
  - [ ] Status indicator dot
  - [ ] Location text
- [ ] Cards highlight on hover
- [ ] Selected card has golden border
- [ ] Single click selects and pans map to marker
- [ ] Double click navigates to detail view
- [ ] Footer shows total capacity sum
- [ ] Empty state message when no installations

#### Add Installation Dialog
- [ ] Dialog opens when clicking "Add"
- [ ] Form fields: Name, Latitude, Longitude, Capacity, Grid Price
- [ ] Default coordinates are Lisbon (38.7223, -9.1393)
- [ ] Default grid price is 0.15 EUR/kWh
- [ ] Validation prevents empty required fields
- [ ] Cancel button closes dialog
- [ ] Create button submits and adds to list
- [ ] New marker appears on map after creation

### Frame 2: Detail View (Installation Analysis)

#### Header
- [ ] Back button returns to main view
- [ ] Installation name displays correctly
- [ ] Location badge shows nearest Portuguese location
- [ ] Capacity displayed prominently in golden

#### Energy Chart Section
- [ ] Chart renders with 24-hour x-axis
- [ ] Production line (golden) visible
- [ ] Consumption line (orange) visible
- [ ] Radiation bars (blue) visible
- [ ] Dual Y-axis (kWh left, W/m2 right)
- [ ] Legend at bottom
- [ ] Tooltip shows values on hover

#### Statistics Grid
- [ ] Today's production in kWh
- [ ] This month's production
- [ ] This year's production
- [ ] Total savings card highlighted with golden gradient
- [ ] Performance ratio percentage
- [ ] Grid price value

#### Weather Section (if data available)
- [ ] Temperature display with icon
- [ ] Radiation display
- [ ] Cloud cover percentage

#### Loading State
- [ ] Golden spinner shows while loading
- [ ] Loading text visible

### Frame 3: Dashboard View (Network Overview)

#### Metrics Cards Row
- [ ] Network Capacity card with solar panel icon
- [ ] Systems Online card (X/Y format)
- [ ] Monthly Generation card
- [ ] Total Savings card (highlighted, golden value)
- [ ] Icons have appropriate colors

#### Network Map
- [ ] Map shows clustered markers by location
- [ ] Cluster size reflects installation count
- [ ] Popups show location name, count, capacity

#### Performance Summary Table
- [ ] Column headers: Location, Installations, Capacity, Avg. Performance
- [ ] Rows for each location with installations
- [ ] Performance color coded (green/golden/orange/red)

#### Recent Activity
- [ ] Activity items with icons
- [ ] Timestamp formatting (Just now, Today, date)
- [ ] Empty state when no activity

### Golden Brand Verification

- [ ] Primary golden (#C4B552) used for:
  - [ ] Production values
  - [ ] Selected states
  - [ ] Primary buttons
  - [ ] Map markers
- [ ] Cream background (#FDFBF5) on main areas
- [ ] Golden underline on app title
- [ ] Golden accent bar under header
- [ ] Loading spinner uses golden color
- [ ] Highlighted savings cards have golden gradient

### Navigation

- [ ] Header navigation shows Installations and Dashboard links
- [ ] Active link has golden background
- [ ] Page transitions are smooth (fade)
- [ ] Browser back/forward works correctly
- [ ] Deep linking to /installation/:id works

### Responsive Behavior

- [ ] Sidebar collapses appropriately on narrow screens
- [ ] Charts resize correctly
- [ ] Metrics grid adjusts to 2 columns on medium screens
- [ ] Touch interactions work on tablet

### Error Handling

- [ ] Network error shows appropriate message
- [ ] Invalid installation ID shows not found
- [ ] Empty states display correctly
- [ ] Console has no JavaScript errors

---

## ML Service API Testing

### Health Check
```bash
curl http://localhost:8501/health
# Expected: {"status":"healthy","models_loaded":0,"locations_available":["Lisbon",...]}
```

### Locations Endpoint
```bash
curl http://localhost:8501/locations
# Expected: {"Lisbon":{"lat":38.7223,"lon":-9.1393},...}
```

### Weather Simulation
```bash
curl -X POST http://localhost:8501/simulate-weather \
  -H "Content-Type: application/json" \
  -d '{"location":"Lisbon","start_date":"2026-01-15","end_date":"2026-01-16"}'
# Expected: Array of hourly weather data
```

### Energy Prediction (requires model)
```bash
curl -X POST http://localhost:8501/predict \
  -H "Content-Type: application/json" \
  -d '{
    "installation_id": "test",
    "capacity_kwp": 5.0,
    "latitude": 38.7223,
    "longitude": -9.1393,
    "weather_data": [
      {
        "timestamp": "2026-01-15T12:00:00",
        "temperature_2m": 15.0,
        "relative_humidity_2m": 60.0,
        "cloud_cover": 20.0,
        "wind_speed_10m": 5.0,
        "shortwave_radiation": 800.0
      }
    ]
  }'
# Expected: Predictions (fallback mode if no model)
```

---

## Test Data Setup

### Create Test Installations

In Nextcloud, use the Add button or API:

```bash
# Via API (after getting CSRF token)
curl -X POST http://localhost:8080/apps/filantropia_solar/api/v1/installations \
  -H "Content-Type: application/json" \
  -u admin:admin \
  -d '{
    "name": "Lisbon Solar Farm",
    "latitude": 38.7223,
    "longitude": -9.1393,
    "capacity_kwp": 50.0,
    "grid_price_kwh": 0.15
  }'
```

### Recommended Test Installations

1. **Lisbon Solar Farm** - 50 kWp at Lisbon coords
2. **Faro Residence** - 5 kWp at Faro coords
3. **Braga Industrial** - 100 kWp at Braga coords
4. **Setubal Port** - 25 kWp at Setubal coords

---

## Troubleshooting

### Container Issues
```bash
# Rebuild containers
docker compose build --no-cache

# Reset database
docker compose down -v
docker compose up -d
```

### App Not Showing
1. Check app is enabled: `docker compose exec nextcloud php occ app:list`
2. Enable if needed: `docker compose exec nextcloud php occ app:enable filantropia_solar`
3. Check logs: `docker compose logs nextcloud`

### JavaScript Errors
1. Check browser console for errors
2. Ensure `npm run build` completed successfully
3. Clear browser cache

### API Errors
1. Check Nextcloud logs in Docker
2. Verify CSRF token if getting 403
3. Check database migrations ran

---

## Sign-Off Checklist

Before release, verify:

- [ ] All automated tests pass
- [ ] All manual UI tests completed
- [ ] No console errors
- [ ] Golden branding consistent throughout
- [ ] Portuguese locations work correctly
- [ ] ML service health check passes
- [ ] App enables/disables cleanly
- [ ] Documentation accurate
