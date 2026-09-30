# ADR 004: Strawberry GraphQL Control Plane vs. REST Endpoint Fragmentation

## Status
**Accepted**

## Context
During high-severity production incidents, frontend SRE dashboards must simultaneously fetch:
1. Incident metadata (ID, severity, start time)
2. Root cause service & confidence score
3. gRPC verification diagnostic details
4. Downstream affected services in propagation order
5. Chronological anomaly timeline
6. Runbook remediation proposals

Fetching this across traditional REST required 5–8 sequential network roundtrips (`/incidents/{id}`, `/services/{id}`, `/diagnostics/{id}`, `/impact/{id}`, `/runbook/{type}`), leading to request waterfalls and slower UI rendering during critical outages.

## Decision
We implemented a **Strawberry GraphQL Control Plane** mounted at `/graphql`:
- **Single Roundtrip Resolution**: The frontend issues a single tailored query specifying exact fields required for the incident view.
- **Python-Native Schema**: Using Strawberry GraphQL provides native Python 3.12 dataclasses and seamless integration with FastAPI without maintaining a separate Node.js Apollo Gateway backend.
- **Real-Time Subscriptions**: Supports WebSocket subscriptions (`graphql-transport-ws`) for streaming incident status changes directly to the browser.

## Consequences
### Positive
- **Zero Over-Fetching / Under-Fetching**: Dashboard receives precisely the data requested in one roundtrip.
- **Unified SRE API**: Simplifies client state management across 2D/3D topology visualizers and incident sidebars.
- **Interactive Exploration**: Built-in GraphiQL explorer available for ad-hoc incident querying.

### Negative
- Query complexity must be bounded to prevent arbitrary expensive database joins.
