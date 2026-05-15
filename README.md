# <img src='Taipei-City-Dashboard-FE/src/assets/images/TUIC.svg' height='28'> Taipei City Dashboard

## My Contribution — 2026 雙北城市黑客松 (Twin Cities Hackathon)

> **Context:** This fork was developed as part of the **2026 Twin Cities Hackathon** under **NCHU ICT Lab**, contributing new transit and environmental intelligence features to Taipei City's open-source urban dashboard.

### Features I Built

| Module | Description | Tech |
| --- | --- | --- |
| **Bus Route Search** | Multi-level query API — search routes by city, district, road, or stop; compute direct and 1-transfer routes between any two stops | Go, Gin, PostgreSQL |
| **Bus Route Map Overlay** | Visualizes bus route polylines and stop positions as interactive map layers | Python, GeoJSON, PostGIS |
| **Real-time Bus Position Dashboard** | Periodic pipeline fetching live ETA data from Taipei/New Taipei Open APIs; displays nearest bus arrival time per stop on map | Python, psycopg2, tcgbusfs API |
| **Environmental Data Pipelines** | Automated Airflow DAGs for precipitation probability, temperature/humidity, street trees, PM2.5, WiFi hotspots, and weather observations | Apache Airflow, Python, Google Cloud Composer |

### System Architecture (Bus Module)

```text
Taipei / New Taipei Open API (tcgbusfs .gz feeds)
        ↓ Python pipeline (gzip → JSON → preprocess)
   PostgreSQL (3 normalized tables)
     bus_route_tpe / bus_stop_tpe / bus_route_stops_tpe
        ↓ Go / Gin REST API (10+ endpoints)
   GET /api/v1/bus/stops
   GET /api/v1/bus/transfer          ← direct + 1-transfer routing
   GET /api/v1/bus/lookup/routes
        ↓ GeoJSON export
   Leaflet map overlay (route polylines + stop ETA heatmap)
```

### Tech Stack

`Python` `Go` `Gin` `PostgreSQL` `PostGIS` `Apache Airflow` `Google Cloud Composer` `GeoJSON` `psycopg2` `Vue.js` `Docker`

**APIs integrated:** Taipei Open Data Platform (`data.taipei`), tcgbusfs real-time bus feed (Taipei + New Taipei)

---

## Introduction

Taipei City Dashboard is a data visualization platform developed by [Taipei Urban Intelligence Center (TUIC)](https://citydashboard.taipei/documentation/en).

Our main goal is to create a comprehensive data visualization tool to assist in Taipei City policy decisions. This was achieved through the first version of the Taipei City Dashboard, which displayed a mix of internal and open data, seamlessly blending statistical and geographical data.

Fast forward to mid-2023, as Taipei City’s open data ecosystem matured and expanded, our vision gradually expanded as well. We aimed not only to aid policy decisions but also to keep citizens informed about the important statistics of their city. Given the effectiveness of this tool, we also hoped to publicize the codebase for this project so that any relevant organization could easily create a similar data visualization tool of their own.

Our dashboard, made yours.

Based on the above vision, we decided to begin development on Taipei City Dashboard 2.0. Unlike its predecessor, Taipei City Dashboard 2.0 will be a public platform instead of an internal tool. The codebase for Taipei City Dashboard will also be open-sourced, inviting all interested parties to participate in the development of this platform.

We have since released Taipei City Dashboard 2.0 to the general public. From now on, you will be able to suggest features and changes to Taipei City Dashboard and develop the platform alongside us. We are excited for you to join Taipei City Dashboard’s journey!

Please refer to the docs for the [Chinese Version](https://tuic.gov.taipei/documentation/front-end/introduction) (and click on the "switch languages" icon in the top right corner).

[Official Site](https://citydashboard.taipei) | [License](https://github.com/tpe-doit/Taipei-City-Dashboard/blob/main/LICENSE) | [Code of Conduct](https://github.com/tpe-doit/Taipei-City-Dashboard/blob/main/.github/CODE_OF_CONDUCT.md) | [Contribution Guide](https://citydashboard.taipei/documentation/front-end/contribution-overview)

## Quick Start

Please refer to the [Docs](https://citydashboard.taipei/documentation/front-end/project-setup) for the quick start guide.

## Documentation

Check out the complete documentation for Taipei City Dashboard [here](https://citydashboard.taipei/documentation/).

## Contributors

Many thanks to the contributors to this project!

<a href="https://github.com/tpe-doit/Taipei-City-Dashboard/graphs/contributors">
<img src="https://contrib.rocks/image?repo=tpe-doit/Taipei-City-Dashboard" />
</a>
