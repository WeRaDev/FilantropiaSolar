# Nextcloud Map + Analytics App: Developer Specification & Build Guide

## Document Purpose
This is a **technical blueprint** for developers to understand the app's functional architecture, UI component structure, and implementation sequence. Use this to build the UI/UX that aligns with user research findings.

---

## Table of Contents
1. [App Architecture Overview](#app-architecture-overview)
2. [Functional Requirements by Feature](#functional-requirements-by-feature)
3. [Component Hierarchy & Dependencies](#component-hierarchy--dependencies)
4. [Data Flow & State Management](#data-flow--state-management)
5. [UI Layout Specification](#ui-layout-specification)
6. [Responsive Behavior by Breakpoint](#responsive-behavior-by-breakpoint)
7. [Implementation Checklist](#implementation-checklist)
8. [API Contracts & Data Models](#api-contracts--data-models)

---

# APP ARCHITECTURE OVERVIEW

## High-Level Application Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                    NEXTCLOUD APP WRAPPER                         │
│              (routing, permissions, Nextcloud API)               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      MAIN APP COMPONENT                          │
│                    (/src/App.vue or App.js)                     │
│                                                                  │
│  Responsibilities:                                              │
│  • Manage global state (selected object, time range, filters)  │
│  • Coordinate data fetching                                    │
│  • Pass data to child components                               │
│  • Handle keyboard shortcuts & global events                   │
└─────────────────────────────────────────────────────────────────┘
         ↓              ↓              ↓
    ┌────────┐    ┌──────────┐   ┌────────────┐
    │ Header │    │   Body   │   │   Footer   │
    │Component   │Component │   │ (optional) │
    └────────┘    └──────────┘   └────────────┘
                       ↓
         ┌─────────────┬──────────────┐
         ↓             ↓              ↓
    ┌────────┐   ┌──────────┐   ┌────────────┐
    │ List   │   │  Map     │   │ Analytics  │
    │Panel   │   │ Panel    │   │ Panel      │
    └────────┘   └──────────┘   └────────────┘
```

---

## Technology Stack Recommendations

**Frontend Framework:**
- Vue 3 (Nextcloud standard) or React
- Component-based architecture

**Map Library:**
- Leaflet.js + Leaflet.markercluster (lightweight, Nextcloud-friendly)
- OR Mapbox GL JS (modern, better performance with 500+ markers)

**State Management:**
- Pinia (Vue 3 recommended) or Redux (React)
- Single store for: selectedObject, timeRange, filters, objects array

**Charts:**
- Chart.js with vue-chartjs wrapper (lightweight)
- OR ECharts (more features, larger bundle)

**HTTP Client:**
- axios (Nextcloud uses this natively)

**Build Tool:**
- Vite (modern, fast) or webpack (traditional, Nextcloud template)

---

# FUNCTIONAL REQUIREMENTS BY FEATURE

## Feature 1: Header Section - KPI Summary & Time Selector

### Functional Requirements

**FR1.1: Display Key Performance Indicators**
- **Input:** Array of objects with status property
- **Process:** 
  - Count total objects
  - Count active objects (status = "active")
  - Count warning objects (status = "warning")
  - Count offline objects (status = "offline")
  - Calculate primary metric (e.g., total power generation, average temperature)
- **Output:** Display 3-4 KPI cards with:
  - Large metric value (28-32px bold)
  - Metric label (12px gray)
  - Trend indicator (% change vs previous period or absolute number)
  - Color-coded badge (green for active, orange for warning, red for offline)

**FR1.2: Dynamically Update KPIs Based on Filters**
- When user applies filter (status filter, time range):
  - Recalculate KPIs considering only filtered objects
  - Animate the change (smooth number transition, 300ms)
  - Update trend comparison

**FR1.3: Time Period Selector**
- **Input:** User click on time picker
- **Options:** 
  - Predefined: "Today", "Week", "Month", "Year"
  - Custom: Date range picker (start date + end date)
- **Process:**
  - Store selected range in app state
  - Fetch analytics data for that range
  - Trigger re-render of list/map/analytics
- **Output:** Display selected range label + calendar icon

**FR1.4: Display Last Updated Timestamp**
- Show "Last updated: 2 minutes ago" (human-readable relative time)
- Update every 10 seconds

---

## Feature 2: List Panel - Object Inventory

### Functional Requirements

**FR2.1: Display List of Objects**
- **Input:** Array of objects with: id, name, status, location, customData
- **Process:**
  - Render each object as a card/row (56px height)
  - Display: status badge + name + location + one key metric
  - Sort by: status (active first) → alphabetical
- **Output:** Scrollable list with 4-8 items visible at once

**FR2.2: Search Functionality**
- **Input:** User types in search box
- **Process:**
  - Real-time filter: match against name, id, location, tags
  - Case-insensitive matching
  - Show "0 results found" if no match
  - Debounce input (300ms)
- **Output:** 
  - Update list display immediately
  - Preserve selection if selected item still matches filter

**FR2.3: Status Filter Chips**
- **Input:** User clicks status filter chip (Active | Warning | Offline)
- **Process:**
  - Toggle chip active/inactive state
  - Filter objects to show only selected statuses
  - Multiple chips can be active (AND logic doesn't apply; instead, show union of selected statuses)
  - Store filter state in app state
- **Output:**
  - Visual feedback: chip changes color/style when active
  - List updates to show only matching objects
  - Map updates to show only matching markers
  - KPIs recalculate for filtered set

**FR2.4: Clear Filters Button**
- **Input:** User clicks "Clear" (✕) button
- **Process:**
  - Reset all filters to show all objects
  - Reset search box to empty
  - Reset status chips to inactive
- **Output:** List shows all objects again

**FR2.5: Object Selection from List**
- **Input:** User clicks object in list
- **Process:**
  - Set selectedObject in app state
  - Highlight row (left border + background color)
  - Update map: center on selected object's marker, highlight marker, zoom to object location
  - Update analytics panel: switch to "Selected Object" tab, show detailed analytics
  - If object is off-screen on map, trigger "Return to selected" button
- **Output:**
  - List row highlighted
  - Map focuses on selected object
  - Analytics shows selected object detail

**FR2.6: Hover Preview**
- **Input:** User hovers over object in list
- **Process:**
  - Highlight row with subtle background
  - On map: highlight corresponding marker with larger size (scale 1.3x)
  - Show map tooltip with object name + key metric
- **Output:**
  - Visual preview in both list and map

**FR2.7: Auto-Scroll List to Selected Item**
- **Input:** Object selected (from map or direct click)
- **Process:**
  - If selected object not visible in list viewport:
    - Scroll list to make selected item visible
    - Smooth scroll animation (300ms)
- **Output:** Selected item always visible in list

**FR2.8: Persist Selection Across Filters**
- **Input:** User has object selected, then applies filter
- **Process:**
  - If selected object matches new filter:
    - Keep it selected
  - If selected object doesn't match filter:
    - Clear selection
    - Clear analytics detail tab
- **Output:** Selection state updated appropriately

---

## Feature 3: Map Panel - Interactive Location Visualization

### Functional Requirements

**FR3.1: Render Map with Base Layer**
- **Input:** App initializes
- **Process:**
  - Create map instance (Leaflet/Mapbox)
  - Set default center (user's location or app default)
  - Set default zoom level (11-13 for regional view)
  - Use neutral basemap (OpenStreetMap standard or Mapbox light)
  - Disable POI labels (restaurants, shops, etc.)
- **Output:** Interactive map visible, ready for markers

**FR3.2: Render Status-Colored Markers**
- **Input:** Array of objects with location (lat, lng) + status
- **Process:**
  - For each object:
    - Create marker with color based on status:
      - Active: #22A559 (green)
      - Warning: #F5A623 (orange)
      - Offline: #CC2020 (red)
    - Marker size: 28px diameter (SVG or icon image)
    - Add object id + name as marker data attribute
    - Render marker on map at lat/lng coordinates
- **Output:** Markers visible on map, distinct by status color

**FR3.3: Auto-Cluster Markers on Zoom Out**
- **Input:** Map zoom level or number of nearby markers
- **Process:**
  - When 5+ markers within 50px radius:
    - Group into cluster
    - Show cluster circle with count (e.g., "12")
    - Cluster color = weighted average of marker colors (or blue if mixed statuses)
    - Cluster size increases with marker count
  - When zoom > threshold or only 1-4 markers in radius:
    - Uncluster and show individual markers
  - Clusters should not overlap with individual markers
- **Output:**
  - Zoomed-out view: clean, readable clusters
  - Zoomed-in view: individual markers visible

**FR3.4: Map Marker Interaction - Click**
- **Input:** User clicks marker on map
- **Process:**
  - Identify clicked marker's object
  - Set selectedObject in app state
  - Highlight marker (larger size, glow effect, 4px theme-color shadow)
  - Scroll list to show selected object + highlight row
  - Update analytics panel to "Selected Object" tab
  - If list off-screen, scroll map to show marker
- **Output:**
  - Marker highlighted
  - List and analytics updated
  - Selection state synced across all views

**FR3.5: Map Marker Interaction - Hover**
- **Input:** User hovers over marker
- **Process:**
  - Enlarge marker (scale 1.3x)
  - Show tooltip: object name + key metric (e.g., "Solar Array 1: 5.2 kW")
  - Tooltip appears above marker, disappears on mouse out
  - In list: highlight corresponding row
- **Output:**
  - Visual feedback (marker size + tooltip)
  - Synchronized highlight in list

**FR3.6: Respond to List Selection on Map**
- **Input:** User clicks object in list
- **Process:**
  - Map should automatically:
    - Center on selected object's marker
    - Zoom to appropriate level (zoom = 16-17)
    - Highlight marker (larger, glow)
    - Show marker tooltip
  - Transition: smooth pan + zoom animation (500ms)
- **Output:**
  - Map focused on selected object
  - User can immediately see object's precise location

**FR3.7: Zoom Controls**
- **Input:** User clicks zoom buttons or scrolls mouse wheel
- **Process:**
  - Provide zoom in/out buttons (top-left corner, 44px each)
  - Allow mouse wheel zoom (standard map behavior)
  - Debounce zoom events (max every 100ms)
- **Output:**
  - Map zoom level changes smoothly
  - Markers cluster/uncluster appropriately

**FR3.8: Basemap Toggle**
- **Input:** User clicks basemap toggle button (top-right)
- **Process:**
  - Switch between: Standard (street map) ↔ Satellite (aerial imagery)
  - Store preference in localStorage or app state
- **Output:**
  - Map background changes, all markers remain visible

**FR3.9: "Return to Selected" Button**
- **Input:** User selects marker, then pans map so marker goes off-screen
- **Process:**
  - Show floating button: "← Selected" (top-right area)
  - On click: pan/zoom map back to selected marker (500ms animation)
  - Hide button if selected marker is visible
- **Output:**
  - Button appears/disappears contextually
  - Helps user refocus on selected object

**FR3.10: Apply Filters to Map Markers**
- **Input:** User applies status filter
- **Process:**
  - Show only markers matching filter criteria
  - Hide (or remove from DOM) non-matching markers
  - Recalculate clusters with remaining markers
  - If selected object hidden by filter: clear selection
- **Output:**
  - Map displays only filtered objects

**FR3.11: Performance: Lazy-Load Markers**
- **Input:** Map pans into new region or zooms
- **Process:**
  - Only render markers within current map bounds + 200px buffer
  - Remove off-screen markers from DOM
  - Debounce pan/zoom events (250ms)
  - Show loading spinner briefly if data fetch needed
- **Output:**
  - Smooth map performance even with 500+ markers

---

## Feature 4: Analytics Panel - Data Insights & Drill-Down

### Functional Requirements

**FR4.1: Tab Navigation - "All Objects" vs "Selected Object"**
- **Input:** User clicks tab or selects/deselects object
- **Process:**
  - "All Objects" tab: always enabled, shows aggregate analytics
  - "Selected Object" tab: enabled only when object is selected
  - If object deselected: switch back to "All Objects" tab automatically
  - Active tab visually distinct (highlight, underline, or background)
- **Output:** Two tabs visible, one active at a time

**FR4.2: Tab 1 - "All Objects" Analytics - Time Series Chart**
- **Input:** Array of objects + selected time range
- **Process:**
  - Fetch time series data for all objects in selected range
  - Calculate aggregate: sum or average of primary metric
  - Plot on line chart: X-axis = time (minute/hour/day based on zoom)
  - Y-axis = primary metric value
  - Show trend line with area fill (semi-transparent color)
  - If multiple series (e.g., actual vs target):
    - Actual: solid line, primary color
    - Target: dashed line, gray color
- **Output:**
  - Interactive chart visible (Chart.js, ECharts, or Recharts)
  - Hover: show tooltip with exact value + timestamp
  - Click data point: zoom into that time (optional advanced feature)

**FR4.3: Tab 1 - "All Objects" Analytics - Status Distribution Pie Chart**
- **Input:** Filtered objects array + their statuses
- **Process:**
  - Count objects in each status (Active, Warning, Offline)
  - Create pie chart with three segments
  - Color each segment: green (active), orange (warning), red (offline)
  - Show label: "Active 38 (90%)" with percentage
  - Show legend outside pie
- **Output:**
  - Pie chart visible (40% width, right of time series)
  - Interactivity (optional): click segment to filter list/map

**FR4.4: Tab 1 - "All Objects" Analytics - Ranked Performers Table**
- **Input:** Sorted objects by primary metric
- **Process:**
  - Rank objects from highest to lowest metric value
  - Display top 10-15 performers (truncated list with "..." if more)
  - Show: rank number, object name, metric value, unit
  - Make sortable: click header to toggle ascending/descending (optional)
- **Output:**
  - Compact table display (right side, below pie chart)
  - Sortable columns (optional)

**FR4.5: Tab 1 - "All Objects" Analytics - Key Statistics Cards**
- **Input:** Primary metric values for all objects
- **Process:**
  - Calculate:
    - Average value
    - Minimum value
    - Maximum value
    - Change from previous period (% and arrow indicator)
    - Trend (↑ = up, ↓ = down, → = flat)
  - Display in 4 cards (each ~100px width)
- **Output:**
  - Cards visible above or beside time series chart
  - Large bold numbers, trend arrows colored (green up, red down)

**FR4.6: Tab 2 - "Selected Object" Analytics - Object Header**
- **Input:** selectedObject data
- **Process:**
  - Display in analytics panel header:
    - Object name (large, bold)
    - Object ID (secondary gray text)
    - Location address (if available)
    - Status badge (green/orange/red)
    - Last update timestamp ("2 minutes ago")
    - "Edit Custom Data" button (pencil icon)
- **Output:**
  - Clear context for user that they're viewing object-specific data

**FR4.7: Tab 2 - "Selected Object" Analytics - Time Series for One Object**
- **Input:** Time series data for selected object + time range
- **Process:**
  - Plot single series on line chart
  - Same axes as "All Objects" for consistency
  - Overlay optional comparison line (e.g., global average as dashed line)
  - Show threshold band (e.g., expected performance range as shaded area)
  - Allow zoom/pan on chart (optional: click and drag to zoom into time range)
- **Output:**
  - Interactive chart showing object's performance over time
  - Easy visual comparison: object trend vs global average

**FR4.8: Tab 2 - "Selected Object" Analytics - Custom Data Fields Display**
- **Input:** Object's customData object (dynamic structure)
- **Process:**
  - For each custom field in object:
    - Display field name (label) + value
    - Format by data type: text as-is, dates as "YYYY-MM-DD", numbers with units
  - Group fields into a card with title "Custom Data"
  - Read-only display (no editing here; use modal for editing)
- **Output:**
  - Clean card display showing all custom attributes

**FR4.9: Tab 2 - "Selected Object" Analytics - Recent Events / Alerts Timeline**
- **Input:** Events array for object (status changes, alerts, updates)
- **Process:**
  - Sort events by timestamp (newest first)
  - Display: timestamp, event type, event description
  - Color-code by event type (alert = red, update = blue, status change = orange)
  - Show max 10 recent events; link to "View all" if more exist
- **Output:**
  - Timeline display showing object's history

**FR4.10: Respond to Time Range Selection**
- **Input:** User selects new time range from header time picker
- **Process:**
  - Fetch new analytics data for selected range
  - Update all charts in both tabs
  - Animate chart transitions (if data changes significantly, fade-in new chart over 300ms)
  - Update "All Objects" data if filters were applied
- **Output:**
  - All analytics charts refresh with new data
  - No loss of selection (selected object remains selected if still valid)

**FR4.11: Analytics Chart Interactivity**
- **Input:** User interacts with charts
- **Process:**
  - Hover data point: show tooltip with exact values
  - Click legend item: toggle series visibility (if multi-series chart)
  - Zoom (if supported): drag on chart area to select time range, double-click to reset
- **Output:**
  - Responsive charts that allow data exploration

---

## Feature 5: Custom Data Management - Add/Edit Object Metadata

### Functional Requirements

**FR5.1: Open Edit Modal - Entry Points**
- **Input:** User clicks "Edit Custom Data" button or pencil icon
- **Process:**
  - Trigger modal overlay
  - Modal appears centered, semi-transparent background darkens page
  - Modal width: 90% (max 600px), height: auto (scrollable if tall)
- **Output:**
  - Modal visible with selected object's current custom data

**FR5.2: Display Custom Data Form Fields**
- **Input:** Object's customData schema (field names, types, labels)
- **Process:**
  - For each custom field:
    - Display form input based on field type:
      - Text: `<input type="text" />`
      - Number: `<input type="number" />`
      - Date: `<input type="date" />` or date picker
      - Select: `<select>` dropdown with predefined options
      - Textarea: `<textarea>` for longer text
    - Show field label above input (bold, 12px)
    - Mark required fields with red asterisk
    - Show placeholder text (hint text, e.g., "e.g., 2023-05-15")
    - Show current value pre-filled in input
  - Organize fields vertically (one per row)
- **Output:**
  - Form visible with all custom fields, values pre-populated

**FR5.3: Input Validation**
- **Input:** User fills form and clicks "Save Changes"
- **Process:**
  - Validate each field:
    - Required fields: must not be empty
    - Number fields: must be numeric (show error if not)
    - Date fields: must be valid date format
    - Text fields: trim whitespace, max length if defined
  - If validation fails:
    - Highlight invalid field with red border
    - Show error message below field (red text)
    - Prevent form submission
- **Output:**
  - Form highlights errors or passes validation

**FR5.4: Save Custom Data**
- **Input:** User clicks "Save Changes" button (after passing validation)
- **Process:**
  - Collect all form field values
  - Update selectedObject.customData with new values
  - Send PUT/PATCH request to backend:
    - Endpoint: `/api/objects/{objectId}/custom-data`
    - Payload: { customData: { field1: value1, field2: value2, ... } }
  - Wait for response (show loading state: button disabled, spinner)
  - On success:
    - Close modal
    - Show toast notification: "Updated successfully" (green, auto-dismiss in 3s)
    - Update list/map if custom data displayed there
    - Update analytics panel if custom fields shown there
  - On error:
    - Show error toast: "Failed to save. Try again."
    - Keep modal open for retry
- **Output:**
  - Custom data persisted to backend
  - UI updated to reflect new values
  - User feedback via toast notification

**FR5.5: Cancel Edit**
- **Input:** User clicks "Cancel" button
- **Process:**
  - Close modal without saving
  - Discard any unsaved changes
  - Return to analytics panel view
- **Output:**
  - Modal closed
  - Original data remains unchanged

**FR5.6: Modal Accessibility**
- **Input:** User interacts with modal
- **Process:**
  - Focus trap: Tab key cycles only through modal elements
  - Escape key: close modal (same as Cancel button)
  - First focusable element: automatically focused when modal opens
  - Close button (X) in top-right corner
- **Output:**
  - Full keyboard navigation support

---

# COMPONENT HIERARCHY & DEPENDENCIES

## Vue 3 Component Structure (Example)

```
App.vue (Root Component)
├── Store (Pinia) - Global State
│   ├── selectedObject
│   ├── timeRange
│   ├── filters (statusFilter, searchTerm)
│   ├── objects (array)
│   └── actions (selectObject, setTimeRange, applyFilter, etc.)
│
├── Header.vue
│   ├── KpiCard.vue (×3-4)
│   └── TimeSelector.vue
│
├── MainContent.vue (Flex container: List + Map)
│   ├── ListPanel.vue
│   │   ├── SearchBox.vue
│   │   ├── FilterChips.vue
│   │   └── ObjectList.vue
│   │       └── ObjectListItem.vue (×N)
│   │
│   └── MapPanel.vue
│       ├── MapContainer.vue (Leaflet map instance)
│       ├── MapMarkers.vue (rendered via Leaflet, not Vue)
│       ├── MapClusters.vue (auto-managed by marker cluster plugin)
│       ├── ZoomControls.vue
│       ├── BasemapToggle.vue
│       └── ReturnToSelectedButton.vue
│
├── AnalyticsPanel.vue
│   ├── AnalyticsTabs.vue (All Objects | Selected Object)
│   │
│   ├── Tab: AllObjectsAnalytics.vue
│   │   ├── TimeSeriesChart.vue
│   │   ├── StatusDistributionPie.vue
│   │   ├── KeyStatsCards.vue
│   │   └── RankedPerformersTable.vue
│   │
│   └── Tab: SelectedObjectAnalytics.vue
│       ├── ObjectHeader.vue
│       │   └── EditCustomDataButton.vue
│       ├── TimeSeriesChart.vue
│       ├── CustomDataDisplay.vue
│       └── EventsTimeline.vue
│
└── CustomDataModal.vue (Overlay)
    ├── ModalHeader.vue
    ├── FormFields.vue
    │   └── FormField.vue (×N by data type)
    ├── ValidationErrorMessage.vue
    └── ModalFooter.vue (Save / Cancel buttons)
```

## Component Responsibilities

### **Header.vue**
- **Props:** objects (array), timeRange (object)
- **State:** none (stateless)
- **Emits:** onTimeRangeChange(newRange)
- **Renders:** KPI cards + time selector

### **ListPanel.vue**
- **Props:** objects (array), selectedObjectId (string), filters (object)
- **State:** searchTerm (local)
- **Emits:** onSelectObject(id), onFilterChange(filters)
- **Renders:** SearchBox, FilterChips, ObjectList

### **MapPanel.vue**
- **Props:** objects (array), selectedObjectId (string), filters (object)
- **State:** mapInstance (Leaflet map), basemapMode (string)
- **Emits:** onSelectObject(id), onMapReady()
- **Lifecycle:** Initialize map on mount, clean up on unmount
- **Renders:** Map container + overlay UI

### **AnalyticsPanel.vue**
- **Props:** objects (array), selectedObject (object), timeRange (object), filters (object)
- **State:** activeTab (string: "all" | "selected")
- **Emits:** onEditCustomData()
- **Renders:** Tabs + analytics content

### **CustomDataModal.vue**
- **Props:** object (object), isOpen (boolean)
- **State:** formData (object), validationErrors (object), isSaving (boolean)
- **Emits:** onSave(customData), onCancel()
- **API Call:** PUT /api/objects/{id}/custom-data

---

## Data Flow Diagram

```
User Action (e.g., click list item)
         ↓
Component emits event (e.g., onSelectObject)
         ↓
App.vue listens to event
         ↓
Update Pinia store (e.g., selectedObject = newObject)
         ↓
Store notifies all subscribed components
         ↓
Components reactively re-render:
  • ListPanel highlights row
  • MapPanel centers on marker
  • AnalyticsPanel switches to "Selected Object" tab
         ↓
User sees synchronized update across all views
```

---

# DATA FLOW & STATE MANAGEMENT

## Global State (Pinia Store / Redux)

```javascript
// State structure
{
  // Objects data
  objects: [
    {
      id: "sp-001",
      name: "Solar Panel 1",
      status: "active", // "active" | "warning" | "offline"
      location: { lat: 38.7223, lng: -9.1393 },
      customData: {
        installationDate: "2023-05-15",
        manufacturer: "SunPower",
        maintenanceSchedule: "quarterly",
        notes: "Prone to bird droppings"
      },
      metrics: {
        powerOutput: 5.2, // kW (current value)
        temperature: 42, // °C
        efficiency: 0.95 // %
      },
      timeSeries: [
        { timestamp: "2026-01-20T08:00:00Z", value: 0 },
        { timestamp: "2026-01-20T08:15:00Z", value: 2.1 },
        { timestamp: "2026-01-20T08:30:00Z", value: 5.2 },
        // ... more data points
      ],
      events: [
        { timestamp: "2026-01-18T14:22:00Z", type: "status_change", description: "Went online" },
        { timestamp: "2026-01-15T09:00:00Z", type: "alert", description: "Low performance" },
        // ... more events
      ]
    },
    // ... more objects
  ],

  // UI State
  selectedObjectId: "sp-001" | null,
  timeRange: {
    start: "2026-01-01",
    end: "2026-01-31",
    label: "Month"
  },
  filters: {
    status: ["active", "warning"], // selected statuses (multi-select)
    searchTerm: "" // search query
  },

  // Computed values
  filteredObjects: [], // objects matching current filters
  selectedObject: {}, // current selected object or null

  // Loading states
  isLoadingObjects: false,
  isLoadingAnalytics: false,
  error: null
}

// Actions
{
  // Object management
  setObjects(objects),
  selectObject(objectId),
  clearSelection(),
  updateCustomData(objectId, customData),

  // Filter management
  setStatusFilter(statuses), // ["active", "warning"]
  setSearchTerm(term),
  clearFilters(),

  // Time range
  setTimeRange(start, end, label),

  // Analytics
  fetchAnalytics(objectId, timeRange),
  fetchTimeSeries(objectId, timeRange),
  fetchAllObjectsTimeSeries(timeRange),

  // Computed getters
  getTotalObjects(),
  getActiveObjectsCount(),
  getWarningObjectsCount(),
  getOfflineObjectsCount(),
  getAggregateMetric(metricName),
  getFilteredObjects(),
  getSelectedObject()
}
```

## State Mutation Flow Example

**User Scenario: Clicking an object in the list**

```
1. User clicks ObjectListItem (e.g., "Solar Panel 1")
   └─ Component emits: @selectObject(id="sp-001")

2. App.vue receives event
   └─ Calls: store.selectObject("sp-001")

3. Pinia store updates state
   └─ selectedObjectId = "sp-001"
   └─ selectedObject = objects.find(o => o.id === "sp-001")

4. All components subscribed to store reactively update:

   a) ListPanel component:
      - Re-renders ObjectList
      - ObjectListItem with id="sp-001" now has :selected="true"
      - CSS applies highlight styling (left border + background)

   b) MapPanel component:
      - Watches selectedObject change
      - Calls: map.setView([lat, lng], zoom)
      - Calls: mapMarker.setIcon(selectedMarkerIcon)
      - Shows marker with glow effect

   c) AnalyticsPanel component:
      - Watches selectedObject change
      - Switches activeTab from "all" to "selected"
      - Updates ObjectHeader display (name, location, ID)
      - Calls: fetchTimeSeries(objectId, timeRange) → updates chart

5. User sees:
   - List item highlighted
   - Map centered on marker with glow
   - Analytics switched to object detail tab
   (All changes instant or smoothly animated)
```

---

# UI LAYOUT SPECIFICATION

## Layout Container Structure

### **Layout Layers (Z-order)**

```
Layer 4 (Top):     CustomDataModal.vue (overlay)
Layer 3:           Toast notifications (success/error)
Layer 2:           Map UI controls (zoom, basemap toggle)
Layer 1:           Main content (Header + MainContent + Analytics)
Layer 0 (Bottom):  HTML body background
```

### **Responsive Grid Breakpoints**

```javascript
const breakpoints = {
  mobile: { max: 767, layout: "vertical" },      // Stack layout
  tablet: { min: 768, max: 1023, layout: "hybrid" }, // List drawer + map
  desktop: { min: 1024, layout: "horizontal" }   // Side-by-side
};

// Mobile (<768px)
// ┌──────────────────┐
// │ Header (100vh-80)|
// │ Map (full width) │
// │  [List drawer▲]  │  ← Swipeable bottom drawer
// └──────────────────┘
// ┌──────────────────┐
// │   Analytics      │
// │   (full width)   │
// └──────────────────┘

// Tablet (768-1023px)
// ┌────────────┬──────────────────┐
// │  Header    │   (spans both)   │
// ├────────────┼──────────────────┤
// │ List       │ Map              │
// │ (drawer/   │ (70% width)      │
// │  sidebar)  │                  │
// └────────────┴──────────────────┘

// Desktop (≥1024px)
// ┌────────────┬──────────────────┐
// │            Header              │ 80px
// ├──────────────┬─────────────────┤
// │              │                 │
// │ List (30%)   │ Map (70%)       │ 400-600px (auto-fit)
// │              │                 │
// ├──────────────┴─────────────────┤
// │      Analytics (100%)           │ 300-400px (collapsible)
// └──────────────────────────────────┘
```

## Detailed Layout Specs by Section

### **Section 1: Header (80px height)**

```
┌──────────────────────────────────────────────────────────────┐
│ Logo(15px) │ KPI Cards (3-4)  │ [Spacer] │ Time Picker (right-aligned)
└──────────────────────────────────────────────────────────────┘

Element breakdown:
• Logo/App name: left 16px, 14px font, gray
• KPI Card 1: 120px wide, centered
  ├─ Large number (28px, bold, theme color)
  ├─ Label (12px, gray)
  └─ Badge (small circle, status color)
• KPI Card 2: 120px wide
• KPI Card 3: 120px wide
• [Spacer]: flex-grow (fills middle)
• Time Picker: 180px wide, right-aligned (16px margin-right)
  ├─ Predefined buttons: Today | Week | Month | Year (inline)
  ├─ Calendar icon
  └─ "Date Range" text (12px)

Styling:
• Background: match Nextcloud theme (typically light gray #f5f5f5)
• Border-bottom: 1px solid #ddd
• Padding: 12px 16px (vertical × horizontal)
• Box-shadow: 0 1px 3px rgba(0,0,0,0.1)
```

### **Section 2: Main Content (70-80% of remaining height)**

```
┌────────────────────┬──────────────────────────────────────┐
│   LIST PANEL       │       MAP PANEL                      │
│   (30-35% width)   │       (65-70% width)                 │
│                    │                                      │
│ ┌──────────────┐   │ ┌──────────────────────────────────┐│
│ │ Search box   │   │ │ [Map Container]                 ││
│ │ (40px)       │   │ │ • Leaflet map                   ││
│ │ ┌──────────┐ │   │ │ • Markers (colored by status)   ││
│ │ │🔍 Search │ │   │ │ • Clusters (auto-managed)      ││
│ │ └──────────┘ │   │ │ • Pan/zoom interactive         ││
│ │              │   │ │                                  ││
│ │ Filter Chips │   │ │ [Overlay Controls]              ││
│ │ (32px)       │   │ │ • Zoom +/- (top-left)           ││
│ │ [Active] [W] │   │ │ • Basemap toggle (top-right)    ││
│ │ [×Clear]     │   │ │ • "Return to selected" (dynamic)││
│ │              │   │ │                                  ││
│ │ Object List  │   │ │                                  ││
│ │ (scrollable) │   │ │                                  ││
│ │              │   │ │                                  ││
│ │ ✓ Object 1   │   │ │                                  ││
│ │   Location   │   │ │                                  ││
│ │   4.5kW      │   │ │                                  ││
│ │              │   │ │                                  ││
│ │ ✓ Object 2   │   │ │                                  ││
│ │   Location   │   │ │                                  ││
│ │   5.2kW      │   │ │                                  ││
│ │              │   │ └──────────────────────────────────┘│
│ │ ⚠ Object 3   │   │                                      │
│ │   Location   │   │                                      │
│ │   80% SOC     │   │                                      │
│ │              │   │                                      │
│ │ [Load more]  │   │                                      │
│ └──────────────┘   │                                      │
└────────────────────┴──────────────────────────────────────┘
```

**Dimensions:**
- List panel: 280-400px width (responsive)
- Map panel: remaining width (min 500px)
- Separator: 2px border (right of list panel)
- Scrollable areas: List has max-height with vertical scroll

**List Panel Details:**
- Search box: 40px height, 16px padding
  - Input border: 1px solid #ccc
  - Focus: border-color theme color, box-shadow 0 0 0 3px rgba(theme, 0.1)
- Filter chips: 32px height, 8px margin between
  - Inactive chip: gray background, dark text, cursor pointer
  - Active chip: theme background, white text
  - Hover: slightly darker background
  - Close button (X) only on active chips
- Object list: 56px per item
  - Status badge: 20px circle, status color
  - Object name: 14px, bold
  - Location: 12px, gray
  - Metric: 12px, theme color
  - Hover: 10% theme-color background
  - Selected: 4px left border (theme color), 5% background

**Map Panel Details:**
- Map container: fills remaining space (flex-grow: 1)
- Leaflet map: display: block, width: 100%, height: 100%
- Markers: 28px diameter, status colored (SVG or icon)
- Clusters: 28-44px diameter, count badge centered
- Zoom buttons: 44×44px each, 12px top, 12px left, 8px spacing
- Basemap toggle: 44×44px, 12px top, 12px right
- Return button: 44×44px, appears dynamically, top-right area

---

### **Section 3: Analytics Panel (300-400px height, collapsible)**

```
┌────────────────────────────────────────────────────────────┐
│ 📊 All Objects  │  📈 Selected Object (grayed if no select) │
├────────────────────────────────────────────────────────────┤
│                                                            │
│ [Time Series Chart - full width, 200px height]           │
│ ┌────────────────────────────────────────────────────────┐
│ │ Power Generation (kW) - Last 30 Days                  │
│ │ 6 ┤     ╱╲      ╱╲                                    │
│ │ 4 ┤    ╱  ╲╱╲  ╱  ╲                [Legend: ──avg]   │
│ │ 2 ┤───────────────────  [X-axis: Days]              │
│ │ 0 ├─────────────────────────────────────────────      │
│ │    └─────────────────────────────────────────────     │
│ └────────────────────────────────────────────────────────┘
│
│ [3-Column Grid below chart]
│
│ [Pie Chart]      [Key Stats]       [Ranked List]
│ ┌────────────┐  ┌────────────┐   ┌────────────┐
│ │  90% Active│  │ AVG: 4.2kW │   │ 1. Panel 5 │
│ │  5% Warn   │  │ MIN: 0.2kW │   │    5.8kW   │
│ │  5% Offline│  │ MAX: 6.8kW │   │ 2. Panel 3 │
│ │            │  │ △ +12% week│   │    5.4kW   │
│ │            │  │            │   │ 3. Panel 1 │
│ │            │  │            │   │    5.2kW   │
│ │            │  │            │   │ ...        │
│ └────────────┘  └────────────┘   └────────────┘
└────────────────────────────────────────────────────────────┘
```

**Dimensions & Layout:**
- Analytics panel height: 300-400px (collapsible, toggle with ↑/↓)
- Tab bar: 32px height (tabs with underline indicator)
- Time Series chart: 60% of panel height, full width
- Grid below: 40% height, 3 equal columns
  - Pie chart: ~25% width
  - Key stats: ~35% width (4 stat cards stacked)
  - Ranked list: ~40% width (scrollable)

**Chart Styling:**
- Background: white or light gray (match Nextcloud)
- Border: 1px solid #eee
- Padding: 12px all around
- Font: 12px for labels, 14px for values

---

## Color Scheme & Typography

### **Status Colors (Consistent Everywhere)**

```css
--status-active: #22A559;    /* Green */
--status-warning: #F5A623;   /* Orange */
--status-offline: #CC2020;   /* Red */
--status-neutral: #CCCCCC;   /* Gray */

/* All status badges, markers, chart segments use these exact colors */
```

### **Typography Scale**

```css
/* Headings */
h1: 28px, weight 700, line-height 1.2, color: --text-primary
h2: 24px, weight 700, line-height 1.2, color: --text-primary
h3: 18px, weight 600, line-height 1.3, color: --text-primary

/* Body Text */
body: 14px, weight 400, line-height 1.5, color: --text-primary
label: 12px, weight 600, line-height 1.4, color: --text-secondary
caption: 11px, weight 400, line-height 1.4, color: --text-muted

/* Numbers (KPIs, charts) */
metric-value: 28-32px, weight 700, mono-spaced, color: --primary
metric-label: 12px, weight 400, color: --text-secondary

/* UI Elements */
button-text: 14px, weight 500, line-height 1.5
input-text: 14px, weight 400, line-height 1.5
tooltip: 12px, weight 400, line-height 1.4
```

---

# RESPONSIVE BEHAVIOR BY BREAKPOINT

## Mobile (<768px)

### Layout Changes:
- Header: Condensed KPIs (show only 1-2 metrics, not 3-4)
- List panel: Hidden by default, shown as bottom drawer (swipeable, 40% height when expanded)
- Map panel: Full width (primary focus)
- Analytics panel: Below map (separate section)

### Interaction Changes:
- Map gestures: Two-finger pinch to zoom (vs mouse wheel)
- List drawer: Swipe up to expand, swipe down to collapse
- Tab navigation: Touch-friendly, larger hit targets (48px minimum)

### Example Mobile Layout:
```
┌─────────────────────┐
│ Header (condensed)  │ 60px
├─────────────────────┤
│ Map (full width)    │ 300px
│                     │
├─────────────────────┤
│ Analytics tabs      │ 32px
│ Time Series Chart   │ 120px
│ (single column grid)│
└─────────────────────┘
  [List drawer above ▲]

Drawer (swipeable):
┌─────────────────────┐
│ ▼ List (collapsed)  │ ← Drag handle
├─────────────────────┤
│ Search box          │
│ Filters             │
│ Object list         │
│ (scrollable)        │
└─────────────────────┘
```

---

## Tablet (768-1023px)

### Layout Changes:
- Header: Full KPIs visible
- List panel: Left drawer (toggle with hamburger menu or always visible)
- Map panel: Main area (60-70%)
- Analytics panel: Below both (full width)

### Interaction Changes:
- List drawer: Collapsible sidebar (hamburger menu toggle)
- Tab navigation: Larger touch targets, tab content doesn't scroll too fast

### Example Tablet Layout:
```
┌──────────────────────────────────────┐
│        Header                        │
├─────────┬──────────────────────────┤
│ ☰ List  │ Map                      │ ← Toggle drawer with ☰
│ (drawer)│                          │
│         │                          │
│ Search  │                          │
│ Filters │                          │
│ Objects │                          │
└─────────┴──────────────────────────┘
└──────────────────────────────────────┘
│ Analytics                            │
└──────────────────────────────────────┘
```

---

## Desktop (≥1024px)

### Layout: Fixed split-view (described above)

```
┌────────────────────────────────────────────────────────┐
│ Header (full width)                                    │
├──────────────────┬──────────────────────────────────────┤
│ List (30-35%)    │ Map (65-70%)                        │
│ • Search         │ • Interactive markers               │
│ • Filters        │ • Clusters                          │
│ • Objects        │ • Overlay controls                  │
│                  │                                      │
└──────────────────┴──────────────────────────────────────┘
│ Analytics (100%)                                       │
│ • Chart + Grid (Pie + Stats + Ranked)                │
└──────────────────────────────────────────────────────────┘
```

---

# IMPLEMENTATION CHECKLIST

## Phase 1: MVP (Basic Functionality)

### Setup & Structure
- [ ] Create Nextcloud app scaffolding (routing, permissions)
- [ ] Set up Vue 3 project with Pinia store
- [ ] Install dependencies: Leaflet, Chart.js, axios
- [ ] Create folder structure:
  - `/src/components/` (UI components)
  - `/src/store/` (Pinia store)
  - `/src/services/` (API calls)
  - `/src/styles/` (SCSS/CSS)
  - `/src/utils/` (helpers, constants)

### Core Components (Phase 1)
- [ ] **App.vue** - Root component with layout structure
- [ ] **Header.vue** - KPI cards (hardcoded to 3 metrics)
- [ ] **ListPanel.vue** - Object list with search (no filters yet)
- [ ] **MapPanel.vue** - Leaflet map with basic markers
- [ ] **AnalyticsPanel.vue** - Stub (basic tab structure)

### State Management
- [ ] Define Pinia store schema (objects, selectedObject, filters)
- [ ] Implement store actions: selectObject, setObjects
- [ ] Setup computed getters: filteredObjects, selectedObject

### API Integration
- [ ] Create API service: fetchObjects()
- [ ] Load sample data from backend or mock data
- [ ] Handle loading/error states

### Styling
- [ ] Apply Nextcloud theme CSS
- [ ] Implement responsive grid (desktop layout fixed, no mobile yet)
- [ ] Style components with utility classes or SCSS modules

### Testing
- [ ] Verify objects display in list
- [ ] Verify markers display on map
- [ ] Verify selection syncs between list and map
- [ ] Test on desktop screen (1024px+)

---

## Phase 2: Analytics & Filters

### Components
- [ ] **AllObjectsAnalytics.vue** - Time series chart, pie chart, stats
- [ ] **SelectedObjectAnalytics.vue** - Object detail tab
- [ ] **TimeSeriesChart.vue** - Chart.js wrapper component
- [ ] **FilterChips.vue** - Status filter UI
- [ ] **SearchBox.vue** - Search input with debounce

### State Management
- [ ] Extend store: add filters (status, searchTerm)
- [ ] Implement filter actions: setStatusFilter, setSearchTerm, clearFilters
- [ ] Computed: getFilteredObjects (combines all filters)

### API Integration
- [ ] fetchAnalytics(objectId, timeRange) - fetch time series data
- [ ] fetchAllObjectsAnalytics(timeRange) - aggregate data

### Features
- [ ] Implement search box (real-time filter with debounce)
- [ ] Implement status filter chips (multi-select)
- [ ] Render time series chart (line chart with trend)
- [ ] Render pie chart (status distribution)
- [ ] Render key stats cards (avg, min, max)
- [ ] Display ranked performers table

### Styling
- [ ] Style filter chips (active/inactive states)
- [ ] Style chart containers (padding, borders, legends)
- [ ] Ensure contrast and readability

### Testing
- [ ] Test search filtering (list and map update)
- [ ] Test status filter (multiple selections)
- [ ] Test analytics charts populate with data
- [ ] Test time range selection updates charts

---

## Phase 3: Custom Data & Modals

### Components
- [ ] **CustomDataModal.vue** - Overlay modal with form
- [ ] **FormFields.vue** - Dynamic form field renderer (text, number, date, select)
- [ ] **ValidationErrorMessage.vue** - Error display for invalid fields

### State Management
- [ ] Extend store: add modalOpen (boolean), formData (object)
- [ ] Actions: openModal, closeModal, updateCustomData

### API Integration
- [ ] PUT /api/objects/{id}/custom-data - save custom data
- [ ] Handle validation errors from backend

### Features
- [ ] Render modal overlay (center, semi-transparent background)
- [ ] Render form fields based on object schema
- [ ] Implement form validation (required, type checking)
- [ ] Implement save/cancel buttons
- [ ] Show toast notification on success/error
- [ ] Close modal after successful save

### Styling
- [ ] Style modal (width, padding, shadows)
- [ ] Style form inputs (borders, focus states)
- [ ] Style error messages (red text, below fields)
- [ ] Style buttons (primary/secondary, disabled states)

### Testing
- [ ] Test modal opens/closes correctly
- [ ] Test form validation (required fields, invalid input)
- [ ] Test custom data saves to backend
- [ ] Test toast notifications appear
- [ ] Test modal closes on success

---

## Phase 4: Responsive Design & Mobile

### Components
- [ ] Refactor layout for responsive breakpoints
- [ ] **ListDrawer.vue** - Mobile bottom drawer version of list
- [ ] **MobileHeader.vue** - Condensed header for small screens
- [ ] Hamburger menu toggle for tablet

### Features
- [ ] Implement mobile layout (<768px)
  - Map full width (primary)
  - List as bottom drawer (swipeable)
  - Analytics below
  - KPIs condensed to 1-2 metrics

- [ ] Implement tablet layout (768-1023px)
  - List sidebar (collapsible)
  - Map main area
  - Analytics below

- [ ] Touch interactions:
  - Swipe to expand/collapse drawer
  - Two-finger pinch on map
  - 48px minimum touch targets

### Styling
- [ ] Update responsive grid (media queries)
- [ ] Update component widths/padding for small screens
- [ ] Ensure text is readable at mobile zoom (16px minimum for inputs)

### Testing
- [ ] Test layout on mobile (375px, 414px, 768px)
- [ ] Test layout on tablet (768px, 1024px)
- [ ] Test on desktop (1440px+)
- [ ] Test touch interactions (drawer swipe, pinch)
- [ ] Test no horizontal scroll on mobile

---

## Phase 5: Advanced Features & Optimization

### Features
- [ ] Map clustering (auto-group markers when zoomed out)
- [ ] Marker clustering on zoom interaction
- [ ] Advanced analytics (anomaly detection, trends)
- [ ] Export data to CSV
- [ ] Saved filter presets
- [ ] Dark mode toggle (if Nextcloud supports)

### Performance
- [ ] Lazy-load markers (render only visible area + buffer)
- [ ] Debounce pan/zoom events (max 250ms)
- [ ] Virtualize long lists (render only visible items)
- [ ] Code splitting (lazy-load analytics tab)
- [ ] Image optimization (marker icons)

### Testing
- [ ] Load test with 500+ markers (performance target: <2s load, 60 FPS)
- [ ] Filter performance (target: <300ms response)
- [ ] Chart interaction performance (hover, zoom)

---

# API CONTRACTS & DATA MODELS

## Backend API Endpoints (REST)

### **GET /api/objects**
Fetch all objects with basic data.

**Query Parameters:**
- `limit` (optional, default 100): pagination limit
- `offset` (optional, default 0): pagination offset
- `filter` (optional): comma-separated statuses (active,warning,offline)

**Response:**
```json
{
  "objects": [
    {
      "id": "sp-001",
      "name": "Solar Panel 1",
      "status": "active",
      "location": {
        "lat": 38.7223,
        "lng": -9.1393,
        "address": "Roof North, Building A"
      },
      "metrics": {
        "powerOutput": 5.2,
        "temperature": 42,
        "efficiency": 0.95
      },
      "customData": {
        "installationDate": "2023-05-15",
        "manufacturer": "SunPower"
      },
      "lastUpdate": "2026-01-20T13:45:00Z",
      "events": [
        { "timestamp": "2026-01-20T13:45:00Z", "type": "update", "description": "Data refreshed" }
      ]
    }
    // ... more objects
  ],
  "total": 42
}
```

---

### **GET /api/objects/{id}**
Fetch single object with full details.

**Response:**
```json
{
  "id": "sp-001",
  "name": "Solar Panel 1",
  "status": "active",
  "location": { "lat": 38.7223, "lng": -9.1393, "address": "..." },
  "metrics": { "powerOutput": 5.2, "temperature": 42, "efficiency": 0.95 },
  "customData": {
    "installationDate": "2023-05-15",
    "manufacturer": "SunPower 400W",
    "maintenanceSchedule": "quarterly",
    "notes": "..."
  },
  "lastUpdate": "2026-01-20T13:45:00Z",
  "events": [ ... ]
}
```

---

### **GET /api/objects/{id}/analytics?start={date}&end={date}**
Fetch time series analytics for object.

**Query Parameters:**
- `start` (required): ISO date (2026-01-01)
- `end` (required): ISO date (2026-01-31)
- `granularity` (optional, default "hour"): minute | hour | day

**Response:**
```json
{
  "objectId": "sp-001",
  "timeSeries": [
    { "timestamp": "2026-01-01T00:00:00Z", "value": 0, "unit": "kW" },
    { "timestamp": "2026-01-01T01:00:00Z", "value": 2.1, "unit": "kW" },
    { "timestamp": "2026-01-01T02:00:00Z", "value": 5.2, "unit": "kW" },
    // ... data points
  ],
  "statistics": {
    "average": 4.2,
    "min": 0,
    "max": 6.8,
    "unit": "kW"
  },
  "comparison": {
    "previousPeriodAverage": 3.9,
    "changePercent": 7.7,
    "trend": "up"
  }
}
```

---

### **GET /api/analytics/aggregate?start={date}&end={date}&filter={statuses}**
Fetch aggregate analytics for all objects.

**Query Parameters:**
- `start` (required): ISO date
- `end` (required): ISO date
- `filter` (optional): comma-separated statuses

**Response:**
```json
{
  "timeSeries": [
    { "timestamp": "2026-01-01T00:00:00Z", "value": 120.5, "unit": "kW" },
    // ... data points
  ],
  "statistics": {
    "average": 115.3,
    "min": 50.0,
    "max": 180.0,
    "unit": "kW"
  },
  "statusDistribution": {
    "active": { "count": 38, "percent": 90 },
    "warning": { "count": 2, "percent": 5 },
    "offline": { "count": 2, "percent": 5 }
  },
  "topPerformers": [
    { "id": "sp-005", "name": "Solar Panel 5", "value": 5.8, "unit": "kW" },
    { "id": "sp-003", "name": "Solar Panel 3", "value": 5.4, "unit": "kW" },
    { "id": "sp-001", "name": "Solar Panel 1", "value": 5.2, "unit": "kW" }
  ]
}
```

---

### **PUT /api/objects/{id}/custom-data**
Update object's custom data fields.

**Request Body:**
```json
{
  "customData": {
    "installationDate": "2023-05-15",
    "manufacturer": "SunPower 400W",
    "maintenanceSchedule": "quarterly",
    "notes": "Prone to bird droppings. Clean monthly."
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Custom data updated",
  "object": {
    "id": "sp-001",
    "customData": { ... },
    "lastUpdate": "2026-01-20T14:00:00Z"
  }
}
```

**Error Response (Validation Failed):**
```json
{
  "success": false,
  "errors": {
    "installationDate": "Invalid date format"
  }
}
```

---

## Data Models

### **Object Model**
```typescript
interface Object {
  id: string; // unique identifier
  name: string; // display name
  status: "active" | "warning" | "offline"; // status
  location: {
    lat: number; // latitude
    lng: number; // longitude
    address?: string; // human-readable address
  };
  metrics: {
    [key: string]: number; // dynamic metrics (powerOutput, temperature, etc.)
  };
  customData: {
    [key: string]: any; // user-defined fields (installationDate, manufacturer, etc.)
  };
  lastUpdate: string; // ISO 8601 timestamp
  events?: Array<{
    timestamp: string;
    type: "alert" | "status_change" | "update";
    description: string;
  }>;
}
```

### **TimeRange Model**
```typescript
interface TimeRange {
  start: string; // ISO date or datetime (2026-01-01 or 2026-01-01T00:00:00Z)
  end: string; // ISO date or datetime
  label?: string; // "Today" | "Week" | "Month" | "Year" | "Custom"
  granularity?: "minute" | "hour" | "day" | "week"; // for analytics
}
```

### **Filter Model**
```typescript
interface Filters {
  status: string[]; // ["active", "warning"] (multi-select)
  searchTerm: string; // search query
  customFilters?: {
    [key: string]: any; // dynamic custom filters
  };
}
```

### **Analytics Model**
```typescript
interface Analytics {
  timeSeries: Array<{
    timestamp: string; // ISO 8601
    value: number;
    unit: string;
  }>;
  statistics: {
    average: number;
    min: number;
    max: number;
    unit: string;
  };
  comparison?: {
    previousPeriodAverage: number;
    changePercent: number;
    trend: "up" | "down" | "flat";
  };
}
```

---

## Error Handling

### **HTTP Status Codes**
- `200 OK`: Successful request
- `400 Bad Request`: Invalid parameters (e.g., invalid date format)
- `401 Unauthorized`: User not authenticated
- `403 Forbidden`: User lacks permission
- `404 Not Found`: Object/resource not found
- `500 Internal Server Error`: Server error

### **Error Response Format**
```json
{
  "success": false,
  "error": "Error message",
  "details": {
    "field": "error details"
  }
}
```

### **Client-Side Error Handling**
```javascript
// In Vue component or API service:
try {
  const data = await api.fetchObjects();
  // handle success
} catch (error) {
  if (error.response?.status === 401) {
    // Handle unauthorized (redirect to login)
  } else if (error.response?.status === 404) {
    // Handle not found (show "No objects" message)
  } else {
    // Generic error: show toast notification
    showErrorToast(error.message || "Failed to load objects");
  }
}
```

---

## Frontend Service Layer (Example: axios)

```javascript
// services/api.js
import axios from 'axios';

const API_BASE = '/apps/your-app-name/api';

export const objectService = {
  fetchObjects(filters = {}) {
    return axios.get(`${API_BASE}/objects`, { params: filters });
  },

  fetchObject(id) {
    return axios.get(`${API_BASE}/objects/${id}`);
  },

  fetchAnalytics(objectId, timeRange) {
    return axios.get(`${API_BASE}/objects/${objectId}/analytics`, {
      params: {
        start: timeRange.start,
        end: timeRange.end,
        granularity: timeRange.granularity || 'hour'
      }
    });
  },

  fetchAggregateAnalytics(timeRange, filters) {
    return axios.get(`${API_BASE}/analytics/aggregate`, {
      params: {
        start: timeRange.start,
        end: timeRange.end,
        filter: filters.status.join(',')
      }
    });
  },

  updateCustomData(objectId, customData) {
    return axios.put(`${API_BASE}/objects/${objectId}/custom-data`, {
      customData
    });
  }
};
```

---

## Nextcloud Integration Notes

### Permissions & Authentication
- All API endpoints require user to be authenticated
- Use Nextcloud's built-in auth (session token)
- Include CSRF token in PUT/POST requests
- Respect object permissions (only show objects user has access to)

### Data Storage
- Store custom data fields in database (likely Nextcloud's database)
- Consider: app-specific table vs existing tables
- Ensure data is scoped to current user (privacy)

### Responses
- Return data in Nextcloud-compatible format (JSON-LD or simple JSON)
- Include proper HTTP status codes
- Use standard error format

---

## Summary: Developer Build Steps

1. **Clone or scaffold** Nextcloud app template
2. **Set up frontend** (Vue 3, Pinia, Leaflet, Chart.js)
3. **Implement components** in order: Header → List → Map → Analytics
4. **Build state management** (Pinia store with actions/getters)
5. **Create API service** (axios wrapper around backend endpoints)
6. **Integrate backend** (fetch/display real data)
7. **Implement filters & search** (sync across all views)
8. **Build analytics panels** (time series, pie, stats charts)
9. **Add custom data modal** (form + validation)
10. **Test responsiveness** (desktop, tablet, mobile)
11. **Optimize performance** (lazy-load, clustering, debouncing)
12. **Deploy to Nextcloud** (follow Nextcloud app distribution guidelines)

---

## End of Developer Specification

This document provides:
- ✅ Functional requirements for each feature
- ✅ Component architecture and dependencies
- ✅ Data flow and state management
- ✅ UI layout specifications with dimensions
- ✅ Responsive breakpoints and behaviors
- ✅ Implementation checklist (5 phases)
- ✅ API contracts and data models
- ✅ Error handling patterns

**Next Steps for Developer:**
1. Review this document thoroughly
2. Create project structure and install dependencies
3. Build components in Phase 1-5 order
4. Test functionality after each phase
5. Reference API contracts when building integrations
6. Use implementation checklist to track progress

