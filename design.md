# 🎨 Design System & UI/UX Architecture

> **Cinematic Engineering Experience Design — AIOps Root Cause Correlator**  
> *Design Philosophy: Apple-Level Precision & Visual Restraint Meets High-Density Mission-Critical Enterprise SRE Intelligence.*

---

## 1. Design Tokens & Visual Hierarchy

The interface is engineered around a dark, high-contrast visual hierarchy optimized for low-latency cognitive processing during high-stress production outages:

| Design Token | Value / Specification | Functional Purpose |
| :--- | :--- | :--- |
| **Canvas Background** | `#0B0D12` (Deep Obsidian Graphite) | Eliminates eye fatigue during nocturnal incident response; provides deep spatial contrast |
| **Glassmorphic Surface** | `rgba(255, 255, 255, 0.04)` + `backdrop-filter: blur(20px)` | Creates depth layers for telemetry cards without obscuring the background canvas |
| **Panel Hairline Border** | `rgba(255, 255, 255, 0.08)` (1px solid) | Crisp card perimeter separation complying with modern glassmorphism standards |
| **Data Accent (Blue)** | `#3B82F6` $\rightarrow$ `#60A5FA` (Electric Azure) | Ingested metric telemetry curves, active WebSocket status, nominal flows |
| **Root Cause Signature (Gold)** | `#F2B84B` (Luminous Amber Gold) | **Reserved strictly for isolated root cause origin** — never used elsewhere |
| **Critical Alarm (Red)** | `#EF4444` / `rgba(239, 68, 68, 0.15)` | Service failure nodes, connection exhaustion indicators, high-severity alerts |
| **Nominal Flow (Green)** | `#10B981` / `rgba(16, 185, 129, 0.15)` | Healthy service statuses, successful query responses, verified diagnostic RPCs |
| **Display Typography** | `Space Grotesk`, sans-serif | Bold, technical, geometric headlines and numerical metric readouts |
| **Body Typography** | `Inter`, -apple-system, sans-serif | Highly legible, clean body paragraphs and explanations |
| **Monospace Typography** | `IBM Plex Mono`, monospace | Timestamps, Z-scores, JSON payloads, gRPC proto definitions, and log lines |

---

## 2. Component Design Breakdown

### 2.1 The Operations Dashboard
The primary viewport balances high data density with clear visual hierarchy:

![Operations Dashboard Layout](docs/images/01_operations_dashboard.png)

- **Left Rail (Incident Queue & Service Health)**: Displays active incident cards categorized by priority (P1 Investigating, P2 Monitoring) and real-time health badges for all 8 microservices.
- **Center Canvas (Causal Topology & Streaming EWMA)**: Houses the interactive dependency graph and real-time anomaly curve tracking statistical deviations ($z > 2.5\sigma$).
- **Right Rail (AI Reasoning & Evidence Chain)**: Presents the isolated root cause with confidence percentage, human-readable rationale, verified evidence checklist, and proposed runbook action.

---

### 2.2 3D Spatial Neural Mesh (Three.js WebGL)
Transitioning from 2D flow to 3D spatial mode immerses the operator in an interactive WebGL canvas:

![3D Spatial Mesh Design](docs/images/02_3d_spatial_mesh.png)

- **Orbital Camera Controls**: Smooth 360° rotation and pinch-to-zoom powered by Three.js `OrbitControls`.
- **Luminous Microservice Spheres**: Services rendered as semi-translucent wireframe spheres that glow and pulse in real time.
- **Spherical Wavefronts**: Animated concentric rings emanate from the identified root cause, visually demonstrating causal cascade direction.

---

### 2.3 Modal Architecture & Glassmorphic Overlays
All secondary workflows (RCA generation, Slack alerts, distributed control plane, benchmarks) render within standardized centered modals:

```css
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(5, 8, 14, 0.82);
  backdrop-filter: blur(10px);
  display: grid;
  place-items: center;
  z-index: 100;
}

.modal-content {
  background: #0b1118;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 16px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
}
```

#### Executive Post-Mortem Document Modal
Designed as a clean, publication-ready document preview with copy-to-clipboard and export capabilities:

![Executive Post-Mortem Modal](docs/images/03_executive_rca_report.png)

#### Distributed Infrastructure Plane Modal
Features high-contrast tabbed navigation between gRPC health cards, Kafka topic queues, and the GraphQL query runner:

![gRPC Diagnostic Mesh](docs/images/05_grpc_diagnostic_mesh.png)

![Kafka Event Bus](docs/images/06_kafka_event_bus.png)

![GraphQL Control Plane](docs/images/07_graphql_control_plane.png)

---

## 3. Audio & Sensory Feedback System

To elevate operational awareness without inducing alarm fatigue, the UI incorporates a synthesized Web Audio API sound engine (`audio.js`):

- **Alert Tone (`sound.alert()`)**: Crisp dual-frequency chime when an anomaly or incident is detected.
- **Success Chime (`sound.success()`)**: Ascending harmonic chord upon cluster auto-healing or runbook execution.
- **Transition Sweep (`sound.whoosh()`)**: Subtle atmospheric sweep when shifting camera modes or injecting chaos.
- **Click Feedback (`sound.click()`)**: Soft mechanical click on interactive controls.
- **Global Sound Toggle**: Easily muted via the sound button in the top navigation bar.
