---
name: Cyber-Physical Security Interface
colors:
  surface: '#131313'
  surface-dim: '#131313'
  surface-bright: '#393939'
  surface-container-lowest: '#0e0e0e'
  surface-container-low: '#1b1b1c'
  surface-container: '#202020'
  surface-container-high: '#2a2a2a'
  surface-container-highest: '#353535'
  on-surface: '#e5e2e1'
  on-surface-variant: '#c0c7d4'
  inverse-surface: '#e5e2e1'
  inverse-on-surface: '#303030'
  outline: '#8a919e'
  outline-variant: '#404752'
  surface-tint: '#a3c9ff'
  primary: '#a3c9ff'
  on-primary: '#00315c'
  primary-container: '#0078d4'
  on-primary-container: '#ffffff'
  inverse-primary: '#0060ab'
  secondary: '#ffb597'
  on-secondary: '#581d00'
  secondary-container: '#f56209'
  on-secondary-container: '#4d1900'
  tertiary: '#ffb3ac'
  on-tertiary: '#680008'
  tertiary-container: '#ea1424'
  on-tertiary-container: '#ffffff'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#d3e3ff'
  primary-fixed-dim: '#a3c9ff'
  on-primary-fixed: '#001c39'
  on-primary-fixed-variant: '#004883'
  secondary-fixed: '#ffdbcd'
  secondary-fixed-dim: '#ffb597'
  on-secondary-fixed: '#360f00'
  on-secondary-fixed-variant: '#7d2d00'
  tertiary-fixed: '#ffdad6'
  tertiary-fixed-dim: '#ffb3ac'
  on-tertiary-fixed: '#410003'
  on-tertiary-fixed-variant: '#93000f'
  background: '#131313'
  on-background: '#e5e2e1'
  surface-variant: '#353535'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: '0'
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: '0'
  label-mono:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.08em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  window-width: 1000px
  window-height: 680px
  sidebar-width: 240px
  gutter: 12px
  margin: 20px
  stack-gap: 8px
---

## Brand & Style
This design system is engineered for high-stakes security monitoring and threat detection within a Windows desktop environment. The brand personality is clinical, authoritative, and high-performance, evoking the feel of a mission-control center.

The design style is **Corporate Modern with a Technical Edge**. It prioritizes information density and clarity over decorative elements. It utilizes a "Dark Mode" foundation to reduce eye strain during long monitoring sessions and to allow high-visibility alerts to pierce the interface effectively. The aesthetic leans into a subtle "Glassmorphism" for secondary panels to maintain depth without sacrificing the rigid, professional structure required for technical software.

## Colors
The palette is rooted in deep, charcoal neutrals to provide a stable backdrop for technical data.

- **Primary (#0078D4):** An electric "Windows Blue" used exclusively for primary actions, progress indicators, and active selection states.
- **Secondary / Warning (#F7630C):** A high-visibility safety orange used for non-critical alerts, suspicious activities, and cautionary status updates.
- **Tertiary / Danger (#E81123):** A vivid red reserved strictly for active threats, system failures, and immediate security breaches.
- **Neutral Surface:** The background uses `#121212` for the main workspace, with `#1F1F1F` used for elevated panels and sidebars to create a clear structural hierarchy.

## Typography
The system utilizes **Inter** for its exceptional readability in dense UI environments. For technical data, logs, and system paths, **Geist** is introduced to provide a monospaced, developer-friendly feel that distinguishes code/data from UI labels.

Headlines should be used sparingly to define major app sections. Labels in all-caps should be used for table headers and category groupings to provide a rhythmic anchor for the eye. High contrast ratio (minimum 4.5:1) must be maintained for all body text against the dark backgrounds.

## Layout & Spacing
The layout follows a **Fixed Grid** model optimized for a standard 1000x680 Windows application frame. The architecture is divided into three primary zones:
1.  **Navigation Rail (Left):** A 64px collapsed or 240px expanded sidebar for high-level module switching.
2.  **Tree-View Panel (Left-Center):** A secondary sidebar for hierarchical object navigation (e.g., File systems, Network nodes).
3.  **Main Stage (Right):** The primary data visualization and configuration area.

Spacing is tight and systematic, utilizing an 4px base unit. Most components use an 8px or 12px gap to maximize the information displayed on screen without causing visual clutter.

## Elevation & Depth
Depth is conveyed through **Tonal Layers** rather than heavy shadows. In this design system:
-   **Level 0 (#121212):** The base application canvas.
-   **Level 1 (#1F1F1F):** Sidebars and persistent navigation containers.
-   **Level 2 (#2D2D2D):** Floating cards, modals, and hovered list items.

A 1px solid stroke in `#333333` is used to define the boundaries of all containers. For active "Threat" modals, a subtle `#E81123` (Red) outer glow is permitted to draw immediate focus. Interactive elements utilize a very soft 4px blur shadow only when in an "Active" or "Pressed" state to simulate a physical push.

## Shapes
The shape language is **Soft (0.25rem)**. This provides a professional, "Windows-native" appearance that feels modern but remains grounded. 

-   **Buttons & Inputs:** 4px (0.25rem) corner radius.
-   **Status Badges:** Fully rounded (pill-shaped) to distinguish them from interactive buttons.
-   **Data Containers:** 8px (0.5rem) corner radius for larger groupings and card layouts.

## Components
-   **Desktop-Style Buttons:** Rectangular with subtle gradients. Primary buttons use the Electric Blue background with white text. Secondary buttons use a ghost style with a `#333333` border.
-   **Progress Bars:** Slim (4px height) tracks. Use Electric Blue for standard operations and Orange/Red if the process identifies a bottleneck or security risk.
-   **Tree-Views:** Use chevron icons for expansion. Indentation should be exactly 16px per level. Active items use a vertical blue bar on the far-left edge.
-   **Status Badges:** Small, high-contrast pills. Use a "Dot" icon inside the badge to indicate live status (pulsing for active threats).
-   **Input Fields:** Darker than the container background (#121212) with a 1px border that turns Electric Blue on focus. Use monospaced font for technical input.
-   **Detections Card:** A specialized component with a thick 4px left-border colored by severity (Orange/Red) and a "Quick Action" button inside the card.