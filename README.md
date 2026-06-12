# Railway_Platform_Project

# 🚆 Real-Time Railway Station Platform Allocation System

A full-stack intelligent platform allocation system inspired by the operational complexity of busy railway stations like **Pune Junction**.

Built not as a simulation, but as a controller-oriented dashboard capable of handling dynamic arrivals, departures, delays, platform conflicts, and real-time operational changes.

---

## 📌 Overview

Railway platform assignment is a constrained scheduling problem involving:

* Limited platforms
* Multiple incoming routes
* Delays and uncertain arrivals
* Platform occupancy conflicts
* Continuous real-time changes

This project replicates many of these challenges through a live dashboard designed from the perspective of how station controllers operate.

---

## ✨ Features

### 🔐 Secure Controller Access

Inspired by Indian Railways control-room and data-logger workflows.

* Role-based authentication
* Protected dashboard access
* Manual platform override capability
* Timestamped audit logs
* Traceability of every controller action

---

### 🔧 Intelligent Platform Allocation Engine

A custom greedy cost-function scheduler assigns trains to the optimal platform among six available platforms.

The algorithm considers:

* Route zone preference (Miraj / Solapur corridors)
* Platform load balancing
* Dwell duration
* Existing occupancy constraints

#### Automatic Reallocation

If a controller forces a platform override:

* Existing trains are automatically re-routed
* No train is dropped
* Conflicts are resolved dynamically

---

### 🤖 Machine Learning Integration

Two Random Forest models operate during every allocation cycle.

#### 1. Delay Prediction Model

Predicts arrival delay (in minutes) using:

* Train type
* Route information
* Time of day

#### 2. Platform Recommendation Model

Provides an independent platform suggestion that acts as an advisory signal alongside the scheduler's decision.

This gives controllers visibility into both:

* Algorithm allocation
* ML recommendation

---

### 📡 Multi-Station Live Tracking

The system tracks nearby sub-stations:

* Hadapsar
* Shivajinagar
* Ghorpuri

When a train departs Pune Junction:

* Corresponding stations update automatically
* "ARRIVING NOW" alerts appear in real time
* Entries are removed after arrival

---

### 🌙 Midnight Rollover Scheduling Logic

One of the most challenging aspects of railway scheduling.

Example:

A train scheduled for **00:15** must still appear correctly in a **22:00–01:00 operational window**.

This required custom time-window handling logic rather than simple date-based filtering.

---

## 🏗 System Architecture

```
                ┌──────────────┐
                │ React Frontend│
                └──────┬───────┘
                       │
                 REST API Calls
                       │
                ┌──────▼──────┐
                │ Flask Backend│
                └──────┬──────┘
                       │
        ┌──────────────┼───────────────┐
        │              │               │
        ▼              ▼               ▼
 SQLite Database  ML Models      Indian Railways API
                     (Random Forest)
```

---

## ⚙ Tech Stack

### Frontend

* React
* JavaScript
* HTML/CSS

### Backend

* Python
* Flask
* REST APIs

### Database

* SQLite

### Machine Learning

* scikit-learn
* Random Forest Regressor
* Random Forest Classifier

### External Services

* Indian Railways API (Live Running Status)

---

## 🧠 Core Components

| Module                 | Description                    |
| ---------------------- | ------------------------------ |
| Authentication         | Secure controller login        |
| Scheduler              | Cost-function based allocation |
| Conflict Resolver      | Automatic platform reallocation|
| Delay Predictor        | Random Forest regression       |
| Platform Advisor       | Random Forest classification   |
| Audit Logger           | Tracks manual interventions    |
| Multi-Station Monitor  | Live station updates           |
| Midnight Window Engine | Cross-day schedule handling    |

---

## 📂 Project Structure

```
railway-platform-allocation/
│
├── frontend/
│   ├── src/
│   ├── components/
│   ├── pages/
│   └── assets/
│
├── backend/
│   ├── app.py
│   ├── routes/
│   ├── models/
│   ├── scheduler/
│   ├── authentication/
│   ├── ml/
│   └── database/
│
├── dataset/
├── trained_models/
├── requirements.txt
├── package.json
└── README.md
```

---

## 🚀 Future Improvements

* Priority handling for premium trains
* Emergency platform reservation
* Graph-based optimization algorithms
* Reinforcement Learning-based scheduling
* WebSocket-based real-time updates
* PostgreSQL migration
* Docker deployment
* Controller analytics dashboard

---

## 🛠 Installation

### Clone Repository

```bash
git clone https://github.com/yourusername/railway-platform-allocation.git
cd railway-platform-allocation
```

### Backend Setup

```bash
pip install -r requirements.txt
python app.py
```

### Frontend Setup

```bash
npm install
npm start
```

---

## 📷 Dashboard Highlights

* Real-time train board
* Platform occupancy visualization
* Delay prediction display
* Platform recommendation system
* Controller login panel
* Audit log history
* Multi-station tracking dashboard

---

## 💡 Inspiration

Most people see trains arriving and departing.

This project explores the decisions happening behind the scenes.

Because railway operations are ultimately a scheduling problem under constraints—and software becomes most interesting when it has to make those decisions.

---

## 🏷 Technologies

`React` `Flask` `Python` `SQLite` `scikit-learn` `Random Forest` `REST API` `Machine Learning` `Full Stack Development`

---

### ⭐ If you found this project interesting, consider giving it a star!

