# FilantropiaSolar v3.0.2 - Figma Wireframe Specification

## Overview
This document provides detailed specifications for recreating the FilantropiaSolar dashboard wireframes in Figma.

---

## 1. Global Design Tokens

### Colors
```
Primary:        #0082c9
Primary Hover:  #006ba7
Background:     #FFFFFF
Surface:        #F5F5F5
Border:         #E0E0E0
Border Dark:    #EBEBEB
Text Primary:   #1A1A1A
Text Secondary: #767676

Status Colors:
  Active:       #22A559
  Warning:      #F5A623
  Offline:      #CC2020

Ranking Colors (v1.2.3):
  0 Non-prod:   #B0B0B0
  1 Poor:       #DC143C
  2 Below Avg:  #FF8C00
  3 Average:    #FFA500
  4 Good:       #32CD32
  5 Excellent:  #FFD700
```

### Typography
```
Font Family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif

Heading 1:    20px / 600 weight
Heading 2:    14px / 600 weight
Body:         14px / 400 weight
Small:        12px / 400 weight
Caption:      11px / 400 weight
KPI Value:    28px / 700 weight
```

### Spacing
```
XS: 4px
SM: 8px
MD: 12px
LG: 16px
XL: 24px
```

### Border Radius
```
Small:  4px
Medium: 6px
Large:  8px
Round:  50%
```

---

## 2. Layout Structure

### Viewport
- **Full Dashboard**: 1440 x 900px (design at this size)
- **Mobile Breakpoint**: 768px
- **Tablet Breakpoint**: 1024px

### Main Layout (3 Sections)
```
+--------------------------------------------------+
|                    HEADER                         | 80px
+--------------------------------------------------+
|                                                   |
|    LIST PANEL    |        MAP PANEL              | 
|      30-35%      |         65-70%                | calc(100% - 80px - 350px)
|                  |                               |
+--------------------------------------------------+
|                ANALYTICS PANEL                    | 300-400px (350px default)
+--------------------------------------------------+
```

---

## 3. Component Specifications

### 3.1 Header Component
**Dimensions**: Full width × 80px
**Padding**: 0 24px
**Background**: #FFFFFF
**Border Bottom**: 1px solid #E0E0E0

#### Layout
```
+--------+------------------------+------------------+
| LOGO   |      KPI CARDS         |  TIME SELECTOR   |
| 32×32  |  (5 cards, centered)   |    (4 buttons)   |
+--------+------------------------+------------------+
```

#### Logo Section
- SVG Sun icon: 32×32px
- App title: "FilantropiaSolar" - 20px/600
- Version badge: "v3.0.2" - 12px, #F5F5F5 bg, 4px radius

#### KPI Cards (5 cards)
- **Card Size**: 120px width × 56px height
- **Gap**: 16px between cards
- **Background**: #F5F5F5
- **Border Radius**: 8px
- **Border (active)**: 2px solid #0082c9

Each card:
```
+------------------+
|       28        | KPI Value (28px/700)
|   Total Plants  | Label (11px, uppercase)
+------------------+
```

Cards:
1. Total Plants (neutral)
2. Active (#22A559)
3. Warnings (#F5A623)
4. Offline (#CC2020)
5. kWp Total (#0082c9)

#### Time Selector
- **Button Size**: padding 8px 16px
- **Border**: 1px solid #E0E0E0
- **Border Radius**: 4px
- **Gap**: 4px
- Options: Day | Week | Month | 21-Day

---

### 3.2 List Panel Component
**Width**: 32% (min 280px, max 400px)
**Background**: #FFFFFF
**Border Right**: 1px solid #E0E0E0

#### Search Box
- **Padding**: 16px
- **Input Height**: 40px
- **Border Radius**: 8px
- **Background**: #F5F5F5
- **Icon**: 16×16px search icon, left side

#### Filter Chips
- **Padding**: 12px 16px
- **Chip Size**: padding 6px 12px
- **Border Radius**: 16px (pill)
- **Gap**: 8px
- Chips: All | Active | Warning | Offline

#### Object List
- **Item Height**: 56px
- **Padding**: 0 16px
- **Border Left (selected)**: 4px solid status color
- **Background (hover)**: #F5F5F5
- **Background (selected)**: rgba(0, 130, 201, 0.08)

Each list item:
```
+---+-------------------------------------+----+
|   | Name                    Capacity    | >  |
| O | Location               Efficiency   |    |
+---+-------------------------------------+----+
  ^                                         ^
Status Badge (10px circle)              Chevron
```

#### List Footer
- **Height**: 32px
- **Text**: "X of Y installations"
- **Alignment**: center

---

### 3.3 Map Panel Component
**Width**: 68% (flex: 1)
**Background**: Map tiles

#### Map Controls (top-right)
- **Position**: 16px from top-right
- **Button Size**: 36×36px
- **Border Radius**: 6px
- **Gap**: 4px
- Buttons: Zoom In (+) | Zoom Out (-) | Reset

#### Legend (bottom-left)
- **Position**: 16px from bottom-left
- **Background**: #FFFFFF
- **Padding**: 8px 16px
- **Border Radius**: 6px
- Items: Active/Warning/Offline with colored dots (12px)

#### Map Markers
- **Size**: 28px diameter (34px when selected)
- **Border**: 2px solid white (4px when selected)
- **Colors**: Based on status
- **Shadow**: 0 2px 8px rgba(0,0,0,0.3)

#### Info Card (when marker selected)
- **Position**: 16px from top-left
- **Width**: 280px
- **Border Radius**: 8px
- **Shadow**: 0 4px 12px rgba(0,0,0,0.15)

```
+--------------------------------+
| [O] Installation Name     [X] | Header (#F5F5F5)
+--------------------------------+
| Location        Lisbon        |
| Capacity        46.0 kWp      |
| Efficiency      85%           |
+--------------------------------+
|       [ View Analysis ]       | Button (primary)
+--------------------------------+
```

---

### 3.4 Analytics Panel Component
**Height**: 350px (300-400px range)
**Background**: #FFFFFF
**Border Top**: 1px solid #E0E0E0

#### Panel Header
- **Height**: 48px
- **Background**: #F5F5F5
- **Padding**: 12px 24px

```
+-----------------------------------------------+
| v Analytics  [Selected Badge]   [< Day Nav >] |
+-----------------------------------------------+
```

#### Tabs
- **Padding**: 8px 24px
- **Tab Padding**: 8px 20px
- **Border Bottom (active)**: 2px solid #0082c9
- Tabs: Energy | Weather | Overview

#### Tab Content Area
- **Padding**: 16px 24px
- **Overflow**: auto

---

### 3.5 Overview Tab (v1.2.3 Feature Parity)

#### Key Performance Metrics Section
- **Background**: #F5F5F5
- **Padding**: 12px
- **Border Radius**: 8px

```
+---------------------------------------------------+
| KEY PERFORMANCE METRICS (21-day period)           |
+---------------------------------------------------+
| Total Energy    | Avg Daily     | Specific Energy |
| 1227.20 kWh     | 58.44 kWh/day | 1.27 kWh/kWp   |
+---------------------------------------------------+
| Peak Hour       | Avg Temp      | Avg Cloud       |
| 0.47 kWh/kWp    | 15.2 C        | 42.5 %          |
+---------------------------------------------------+
```

Metric item:
- **Background**: #FFFFFF
- **Padding**: 6px 10px
- **Border Radius**: 4px
- **Grid**: 3 columns

#### Daily Summary Table
- **Max Height**: 120px (scrollable)
- **Font Size**: 11px

| Day | Date  | Energy | Peak | Temp | Cloud | Rating |
|-----|-------|--------|------|------|-------|--------|
| 1   | 04-12 | 168.8  | 21.5 | 15   | 47    | [Good] |

Rating badges use ranking colors with 3px radius.

#### Data Source Section
- **Background**: #F5F5F5
- **Font Size**: 11px

```
PV Data:        Sarmas et al. (2025)
Analysis Mode:  Historical
Weather Source: Historical (local)
ML Model:       Gradient Boosting
```

---

## 4. Figma Frame Structure

Recommended Figma file structure:

```
📁 FilantropiaSolar v3.0.2
├── 📁 Design Tokens
│   ├── Colors
│   ├── Typography
│   └── Spacing
├── 📁 Components
│   ├── Header
│   │   ├── Logo
│   │   ├── KPI Card
│   │   └── Time Button
│   ├── ListPanel
│   │   ├── Search Box
│   │   ├── Filter Chip
│   │   └── List Item
│   ├── MapPanel
│   │   ├── Map Marker
│   │   ├── Info Card
│   │   └── Legend
│   └── AnalyticsPanel
│       ├── Tab
│       ├── Metric Card
│       ├── Daily Table Row
│       └── Rating Badge
└── 📁 Screens
    ├── Dashboard - Default
    ├── Dashboard - Installation Selected
    ├── Dashboard - Analysis Generated
    └── Dashboard - Mobile
```

---

## 5. Interactive States

### Buttons
- **Default**: Background #FFFFFF, Border #E0E0E0
- **Hover**: Background #F5F5F5
- **Active**: Background #0082c9, Color #FFFFFF
- **Disabled**: Opacity 0.4

### List Items
- **Default**: Background transparent
- **Hover**: Background #F5F5F5
- **Selected**: Background rgba(0,130,201,0.08), Border-left 4px

### KPI Cards
- **Default**: Border transparent
- **Hover**: Background #EDEDED
- **Active Filter**: Border 2px #0082c9

---

## 6. Export Notes

When exporting from Figma:
- Export @1x, @2x, @3x for icons
- Use SVG for logos and icons
- Export component CSS using Figma's inspect panel
- Use Auto Layout for responsive components

---

## 7. Assets Required

### Icons (16×16 and 24×24 variants)
- Search
- Chevron Right
- Chevron Left
- Plus (zoom in)
- Minus (zoom out)
- Target (reset view)
- Close (X)
- Toggle arrow

### Logo
- Sun icon SVG (32×32)
- Full logo with text (optional)

---

*Document Version: 1.0*
*Last Updated: January 2026*
