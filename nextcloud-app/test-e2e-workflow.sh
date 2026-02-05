#!/bin/bash
set -e

##############################################################################
# FilantropiaSolar v3.0.2 - Automated E2E Test with Self-Healing
#
# This script:
# 1. Runs the "Working Workflow" test case with Playwright
# 2. Captures screenshots after each action
# 3. Analyzes results and triggers self-healing via Warp conversation
# 4. Retries up to 6 times until all issues are resolved
#
# Requirements:
# - Node.js with Playwright installed
# - Nextcloud app running at http://localhost:8080
# - Warp CLI available
##############################################################################

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEST_DIR="$SCRIPT_DIR/test-results"
SCREENSHOTS_DIR="$TEST_DIR/screenshots"
MAX_ITERATIONS=6
CURRENT_ITERATION=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

##############################################################################
# Setup
##############################################################################
setup() {
    log_info "Setting up test environment..."
    
    # Create test directories
    mkdir -p "$SCREENSHOTS_DIR"
    
    # Clean previous test results
    rm -rf "$SCREENSHOTS_DIR"/*
    
    # Check if Playwright is installed
    if ! command -v npx &> /dev/null; then
        log_error "npx not found. Please install Node.js"
        exit 1
    fi
    
    # Install Playwright if needed
    if ! npx playwright --version &> /dev/null 2>&1; then
        log_info "Installing Playwright..."
        npm install -D @playwright/test
        npx playwright install chromium
    fi
    
    log_info "Setup complete"
}

##############################################################################
# Create Playwright Test Script
##############################################################################
create_test_script() {
    log_info "Creating Playwright test script..."
    
    cat > "$TEST_DIR/workflow-test.spec.js" <<'EOF'
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

const BASE_URL = 'http://localhost:8080';
const SCREENSHOTS_DIR = path.join(__dirname, 'screenshots');
const USERNAME = 'admin';
const PASSWORD = 'admin';

// Ensure screenshots directory exists
if (!fs.existsSync(SCREENSHOTS_DIR)) {
    fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}

test.describe('FilantropiaSolar v3.0.2 Working Workflow', () => {
    test('Complete analysis workflow', async ({ page }) => {
        let stepNumber = 0;
        
        const screenshot = async (name) => {
            stepNumber++;
            const filename = `step-${stepNumber.toString().padStart(2, '0')}-${name}.png`;
            await page.screenshot({ 
                path: path.join(SCREENSHOTS_DIR, filename),
                fullPage: true 
            });
            console.log(`📸 Screenshot: ${filename}`);
        };
        
        // Step 1: Navigate to Nextcloud login
        console.log('🚀 Starting test: Complete analysis workflow');
        await page.goto(BASE_URL);
        await screenshot('01-login-page');
        
        // Step 2: Login
        console.log('🔐 Logging in...');
        await page.fill('input[name="user"]', USERNAME);
        await page.fill('input[name="password"]', PASSWORD);
        await page.click('button[type="submit"]');
        await page.waitForLoadState('networkidle');
        await screenshot('02-logged-in-dashboard');
        
        // Step 3: Navigate to FilantropiaSolar app
        console.log('📱 Opening FilantropiaSolar app...');
        await page.goto(`${BASE_URL}/apps/filantropia_solar`);
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(2000); // Wait for Vue app to mount
        await screenshot('03-app-main-view');
        
        // Step 4: Navigate to Analysis tab
        console.log('📊 Navigating to Analysis tab...');
        const analysisLink = page.locator('text=Analysis').first();
        await analysisLink.waitFor({ state: 'visible', timeout: 5000 });
        await analysisLink.click();
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(1000);
        await screenshot('04-analysis-view');
        
        // Step 5: Select mode (should default to Historical)
        console.log('🔘 Verifying mode selection...');
        const historicalRadio = page.locator('input[type="radio"][value="historical"]');
        await expect(historicalRadio).toBeChecked();
        await screenshot('05-mode-selected');
        
        // Step 6: Verify installation is selected
        console.log('🏭 Verifying installation selection...');
        const installationSelect = page.locator('select').first();
        const selectedValue = await installationSelect.inputValue();
        console.log(`   Selected installation: ${selectedValue}`);
        expect(selectedValue).toBeTruthy();
        await screenshot('06-installation-selected');
        
        // Step 7: Select a date
        console.log('📅 Selecting date...');
        const dateSelect = page.locator('select').nth(1); // Second select is date
        const dateOptions = await dateSelect.locator('option').count();
        if (dateOptions > 0) {
            await dateSelect.selectOption({ index: dateOptions - 1 }); // Select last date
        }
        await screenshot('07-date-selected');
        
        // Step 8: Click Generate Analysis
        console.log('🚀 Generating analysis...');
        const generateBtn = page.locator('button:has-text("Generate 21-Day Analysis")');
        await generateBtn.waitFor({ state: 'visible', timeout: 5000 });
        await generateBtn.click();
        await screenshot('08-generate-clicked');
        
        // Step 9: Wait for results page to load
        console.log('⏳ Waiting for results...');
        await page.waitForURL('**/results', { timeout: 30000 });
        await page.waitForLoadState('networkidle');
        await page.waitForTimeout(2000); // Wait for charts to render
        await screenshot('09-results-loaded');
        
        // Step 10: Verify statistics panel
        console.log('📈 Verifying statistics panel...');
        const statsPanel = page.locator('.stats-panel');
        await expect(statsPanel).toBeVisible();
        const statCards = statsPanel.locator('.stat-card');
        const cardCount = await statCards.count();
        console.log(`   Found ${cardCount} stat cards`);
        expect(cardCount).toBeGreaterThanOrEqual(5);
        await screenshot('10-statistics-panel');
        
        // Step 11: Verify daily overview chart
        console.log('📊 Verifying daily overview chart...');
        const dailyChart = page.locator('.daily-overview-chart');
        await expect(dailyChart).toBeVisible();
        await screenshot('11-daily-overview-chart');
        
        // Step 12: Test day navigation
        console.log('◀️ Testing Previous day button...');
        const prevBtn = page.locator('button:has-text("Previous")');
        await prevBtn.waitFor({ state: 'visible' });
        await prevBtn.click();
        await page.waitForTimeout(500);
        await screenshot('12-previous-day');
        
        console.log('▶️ Testing Next day button...');
        const nextBtn = page.locator('button:has-text("Next")');
        await nextBtn.click();
        await page.waitForTimeout(500);
        await screenshot('13-next-day');
        
        // Step 13: Verify hourly energy chart
        console.log('⚡ Verifying hourly energy chart...');
        const energyChart = page.locator('.energy-chart');
        await expect(energyChart).toBeVisible();
        const legend = energyChart.locator('.legend');
        await expect(legend).toBeVisible();
        await screenshot('14-energy-chart');
        
        // Step 14: Verify weather chart
        console.log('🌤️ Verifying weather chart...');
        const weatherChart = page.locator('.weather-chart');
        await expect(weatherChart).toBeVisible();
        await screenshot('15-weather-chart');
        
        // Step 15: Verify daily breakdown table
        console.log('📋 Verifying daily breakdown table...');
        const breakdownTable = page.locator('.breakdown-table');
        await expect(breakdownTable).toBeVisible();
        const tableRows = breakdownTable.locator('tbody tr');
        const rowCount = await tableRows.count();
        console.log(`   Found ${rowCount} days in breakdown table`);
        expect(rowCount).toBeGreaterThanOrEqual(3);
        await screenshot('16-breakdown-table');
        
        // Step 16: Test table row selection
        console.log('🖱️ Testing table row click...');
        await tableRows.nth(5).click();
        await page.waitForTimeout(500);
        await screenshot('17-table-row-selected');
        
        // Step 17: Back to Analysis
        console.log('◀️ Navigating back to Analysis...');
        const backBtn = page.locator('button:has-text("Back to Configuration")');
        await backBtn.click();
        await page.waitForLoadState('networkidle');
        await screenshot('18-back-to-analysis');
        
        console.log('✅ Test completed successfully!');
    });
});
EOF
    
    log_info "Test script created at $TEST_DIR/workflow-test.spec.js"
}

##############################################################################
# Run Test
##############################################################################
run_test() {
    log_info "Running E2E test (iteration $CURRENT_ITERATION/$MAX_ITERATIONS)..."
    
    cd "$TEST_DIR"
    
    # Run Playwright test
    if npx playwright test --reporter=line 2>&1 | tee test-output.log; then
        log_info "Test passed!"
        return 0
    else
        log_error "Test failed!"
        return 1
    fi
}

##############################################################################
# Analyze Results
##############################################################################
analyze_results() {
    log_info "Analyzing test results..."
    
    # Count screenshots
    local screenshot_count=$(ls -1 "$SCREENSHOTS_DIR"/*.png 2>/dev/null | wc -l | tr -d ' ')
    log_info "Captured $screenshot_count screenshots"
    
    # Check for errors in log
    if grep -q "Error:" "$TEST_DIR/test-output.log"; then
        log_error "Errors detected in test output"
        return 1
    fi
    
    if grep -q "✅ Test completed successfully!" "$TEST_DIR/test-output.log"; then
        log_info "All test steps completed successfully"
        return 0
    fi
    
    log_warn "Test completed with warnings"
    return 1
}

##############################################################################
# Trigger Self-Healing via Warp
##############################################################################
trigger_self_healing() {
    log_warn "Triggering self-healing via Warp conversation..."
    
    # Check if Warp CLI is available
    if ! command -v warp &> /dev/null; then
        log_error "Warp CLI not found. Cannot trigger self-healing."
        log_info "Install Warp CLI: https://www.warp.dev"
        return 1
    fi
    
    # Create analysis report
    local report="$TEST_DIR/test-report.txt"
    cat > "$report" <<EOF
# FilantropiaSolar v3.0.2 E2E Test Report
Iteration: $CURRENT_ITERATION/$MAX_ITERATIONS
Date: $(date -u +"%Y-%m-%dT%H:%M:%SZ")

## Test Output
$(tail -50 "$TEST_DIR/test-output.log")

## Screenshots
$(ls -1 "$SCREENSHOTS_DIR"/*.png | wc -l) screenshots captured in:
$SCREENSHOTS_DIR

## Next Steps
Please analyze the screenshots and test output to:
1. Identify any UI issues or failures
2. Fix issues in the codebase
3. Rebuild frontend (npm run build)
4. Restart services if needed
5. Confirm ready for next test iteration
EOF
    
    log_info "Test report created: $report"
    log_info "Screenshots available in: $SCREENSHOTS_DIR"
    
    # Launch Warp with the report (if in interactive mode)
    if [ -t 0 ]; then
        log_info "Opening screenshots directory..."
        open "$SCREENSHOTS_DIR" 2>/dev/null || true
        
        log_info "You can now:"
        echo "  1. Review screenshots in $SCREENSHOTS_DIR"
        echo "  2. Send this command in Warp:"
        echo ""
        echo "     Here is the result of the test-case. Analyze, fix, modify and relaunch test-case script."
        echo ""
        echo "  3. Attach screenshots from $SCREENSHOTS_DIR"
    fi
    
    return 0
}

##############################################################################
# Main Test Loop
##############################################################################
main() {
    log_info "=== FilantropiaSolar v3.0.2 E2E Test Runner ==="
    
    setup
    create_test_script
    
    while [ $CURRENT_ITERATION -lt $MAX_ITERATIONS ]; do
        CURRENT_ITERATION=$((CURRENT_ITERATION + 1))
        
        log_info "=== Iteration $CURRENT_ITERATION/$MAX_ITERATIONS ==="
        
        if run_test; then
            if analyze_results; then
                log_info "✅ All tests passed! No issues found."
                exit 0
            fi
        fi
        
        log_warn "Issues detected in iteration $CURRENT_ITERATION"
        
        if [ $CURRENT_ITERATION -ge $MAX_ITERATIONS ]; then
            log_error "Maximum iterations reached ($MAX_ITERATIONS)"
            trigger_self_healing
            exit 1
        fi
        
        trigger_self_healing
        
        # Wait for user to fix issues and press enter
        if [ -t 0 ]; then
            log_info "Press Enter after fixing issues to continue, or Ctrl+C to abort..."
            read -r
        else
            log_error "Non-interactive mode: stopping after first failure"
            exit 1
        fi
    done
}

# Run main function
main "$@"
