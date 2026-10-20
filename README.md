# 🏭 Multi-Agent Supply Chain Simulator

> **5 KI-Agenten simulieren eine vollständige Lieferkette – von der Nachfrageprognose bis zur Auslieferung.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.50-FF4B4B?logo=streamlit)](https://streamlit.io)
[![Plotly](https://img.shields.io/badge/Plotly-6.8-3F4F75?logo=plotly)](https://plotly.com)

---

## 🎯 Überblick

Jeder Agent trifft **autonome operative Entscheidungen** und kommuniziert über einen **Event Bus**. Das Dashboard visualisiert Lagerbestände, Fill Rate, Kosten und Deckungsbeitrag in Echtzeit.

```
Nachfrage ──► Beschaffung ──► Produktion ──► Lager ──► Logistik ──► Kunde
     ▲                                                         │
     └──────────────────── Event Bus ──────────────────────────┘
```

### Die 5 Agenten

| Agent | Rolle | Entscheidungen |
|-------|-------|----------------|
| 📊 **Nachfrage** (Demand) | Erzeugt Kundenaufträge | Saisonalität, Trend, Rauschen |
| 🛒 **Beschaffung** (Procurement) | Bestellt Rohstoffe | (s,Q)-Policy, Sicherheitsbestand |
| 🔧 **Produktion** (Production) | Steuert Fertigung | Materialverfügbarkeit, Kapazität |
| 📦 **Lager** (Inventory) | Verwaltet Bestand | Kommissionierung, Stockout-Erkennung |
| 🚚 **Logistik** (Logistics) | Disposition Versand | Truck-Konsolidierung, Lieferzeit |

---

## 🚀 Quickstart

```bash
# 1. Repository klonen
git clone https://github.com/marcoduetsch-oc/supply-chain-simulator.git
cd supply-chain-simulator

# 2. Virtuelle Umgebung einrichten
python3 -m venv venv
source venv/bin/activate

# 3. Dependencies installieren
pip install -r requirements.txt

# 4. Starten
streamlit run dashboard.py
```

→ Dashboard unter **http://localhost:8501** öffnen.

---

## 📦 Requirements

```
streamlit==1.50.0
pandas==2.3.3
plotly==6.8.0
numpy==2.0.2
```

Gepinnt auf die lokal verifizierten Versionen (reproduzierbare Deploys). Aktualisieren: `pip install -U <paket>` → Versionen hier nachziehen.

---

## 🎮 Dashboard

| Steuerung | Beschreibung |
|-----------|--------------|
| 🔄 Simulation starten | Neuen Durchlauf starten |
| Simulations-Tage | Dauer (30–365 Tage) |
| Basis-Nachfrage | Durchschnittliche Tagesnachfrage |
| Volatilität | Standardabweichung der Nachfrage |
| Produktionskapazität | Max. Einheiten pro Tag |
| Lieferzeit | Tage bis Material eintrifft |
| Sicherheitsbestand | Tage als Puffer |

### Kennzahlen

- 🎯 **Fill Rate** (30 Tage rollierend) – Ziel: >95%
- 📊 **Gesamtnachfrage** & Gelieferte Einheiten
- ⚠️ **Stockouts** – Fehlmengen
- 💰 **Gewinn/Verlust** – Umsatz minus Kosten

### Diagramme

| Diagramm | Beschreibung |
|----------|--------------|
| 📦 **Lagerbestände** | Rohstoff A, B & Fertigwaren |
| 📈 **Nachfrage ↔ Produktion ↔ Lieferungen** | Tagesgenauer Flow |
| 🎯 **Fill Rate** | Rollierender 30-Tage-Schnitt |
| 💰 **Umsatz vs. Kosten** | Kumulierte Finanzdaten |

---

## 🧪 Headless Mode (ohne UI)

```bash
python run.py
```

Gibt alle KPIs und die letzten 20 Log-Einträge auf der Konsole aus – nützlich für Batch-Tests und CI.

---

## ⚙️ Konfiguration

Alle Parameter in [`src/config.py`](src/config.py):

```python
DEMAND_BASE = 100          # Durchschnittliche Tagesnachfrage
DEMAND_VOLATILITY = 20     # Standardabweichung
PRODUCTION_CAPACITY = 120  # Max. Produktion pro Tag
ORDER_LEAD_TIME = 5        # Lieferzeit Beschaffung
SAFETY_STOCK_DAYS = 7      # Sicherheitsbestand
TRUCK_CAPACITY = 50        # LKW-Kapazität
```

→ Im Dashboard können die wichtigsten Werte direkt über die Sidebar gesteuert werden.

---

## 📁 Projektstruktur

```
supply-chain-sim/
├── dashboard.py          # Streamlit-Dashboard
├── run.py                # Headless CLI-Runner
├── requirements.txt      # Python-Dependencies (gepinnt)
├── railway.toml          # Railway-Deploy (Start-Command, Healthcheck)
├── .python-version       # Python 3.12 für Deploy
├── .streamlit/
│   └── config.toml       # Streamlit-Server/Theme (headless)
├── README.md             # ← Du bist hier
├── .gitignore
├── venv/                 # Virtuelle Umgebung (lokal)
└── src/
    ├── __init__.py
    ├── config.py         # Konfiguration & Parameter
    ├── base_agent.py     # Basisklasse + Event-Typ
    ├── agents.py         # Die 5 Agenten
    └── sim_env.py        # Simulations-Engine, Event Bus, Tick-Loop
```

---

## 💡 Anwendungsideen

- **What-if-Analysen:** Parameter variieren und Fill-Rate-Effekte beobachten
- **Bullwhip-Effekt:** Sichtbar bei steigender Nachfragevolatilität
- **Bestandsoptimierung:** Sicherheitsbestand vs. Kapitalbindung ausbalancieren
- **Kapazitätsplanung:** Produktion vs. Lieferfähigkeit optimieren
- **Lehrbeispiel:** Für Studium / Ausbildung im Supply Chain Management

---

## 🔧 Entwicklung

```bash
# Lokal testen
python run.py

# Dashboard starten
streamlit run dashboard.py

# Neue Agenten hinzufügen
# 1. Klasse in agents.py (extends BaseAgent)
# 2. In dashboard.py + run.py registrieren
```

Jeder Agent implementiert zwei Methoden:
- `reset()` – Wird vor dem Simulationslauf aufgerufen
- `step(tick, state, events)` – Tick-Logik, gibt Events zurück

---

## 🚢 Deployment

### Railway (empfohlen, Produktion)

Repo ist deploy-fertig: `railway.toml` (Start-Command + Healthcheck), `.python-version` (3.12), `.streamlit/config.toml` (Headless, Telemetrie aus).

1. Railway → **New Project → Deploy from GitHub repo** → `marcoduetsch-oc/supply-chain-simulator`
2. Service → Settings → Region **EU West Metal (Amsterdam)** (CH-Kunden/revDSG)
3. Settings → Networking → **+ Custom Domain** (`biergame.duetsch.net`) → angezeigtes CNAME-Ziel beim DNS-Provider eintragen → TLS automatisch (Let's Encrypt)
4. Healthcheck `/_stcore/health` wird aus `railway.toml` gelesen

**Kosten:** Hobby $5/Mt Minimum inkl. $5 Nutzungsguthaben (RAM ~$10/GB-Mt, CPU ~$20/vCPU-Mt nur bei Nutzung, Egress $0.05/GB). App ist zustandslos → kein Volume/DB nötig, 0,5 GB RAM ≈ $5/Mt.
**Wichtig:** Der Railway-Free-Plan hat **0 Custom Domains** → eigene Domain erfordert Hobby.

### Alternative: Streamlit Community Cloud

→ streamlit.io/cloud → Repo verbinden → `dashboard.py` als Entrypoint. Kostenlos, aber ohne eigene Domain und mit Kaltstart.

---

## 📜 Lizenz

MIT – frei für Bildung, Experimente und kommerzielle Nutzung.

---

*Gebaut mit ❤️ von Marco & Hermes Agent*
