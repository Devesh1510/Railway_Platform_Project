"""
ml_models.py
------------
Two ML models for Pune Station Controller:

1. DelayPredictor  — Random Forest regressor that predicts arrival delay (minutes)
   Features: hour, minute, train_type_enc, route_enc, is_peak_hour

2. PlatformRecommender — Random Forest classifier that recommends a platform (1-6)
   Features: hour, minute, train_type_enc, route_enc, is_peak_hour, num_active_trains
   Trained on decisions made by the existing cost-function allocator (teacher model).
"""

import random
import numpy as np
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

# ── Encoders (fit once, reused at inference) ──────────────────────────────────
_type_enc  = LabelEncoder().fit(['Through', 'Terminating', 'Originating', 'Origin'])
_route_enc = LabelEncoder().fit(['Mumbai', 'Solapur', 'Miraj'])

def _encode_type(t):
    try:
        return int(_type_enc.transform([t])[0])
    except Exception:
        return 0

def _encode_route(r):
    try:
        return int(_route_enc.transform([r])[0])
    except Exception:
        return 0

def _is_peak(hour):
    return 1 if (7 <= hour <= 10 or 17 <= hour <= 21) else 0

def _features(hour, minute, train_type, route, num_active=0):
    return [
        hour,
        minute,
        _encode_type(train_type),
        _encode_route(route),
        _is_peak(hour),
        num_active,
    ]

# ── Synthetic training data generator ────────────────────────────────────────

PLATFORM_ZONES = {1: 'Miraj', 2: 'Miraj', 3: 'Miraj',
                  4: 'Solapur', 5: 'Solapur', 6: 'Solapur'}

def _preferred_platforms(route):
    """Return platforms preferred for a given route."""
    if 'Miraj' in route:
        return [1, 2, 3]
    if 'Solapur' in route:
        return [4, 5, 6]
    return [1, 2, 3, 4, 5, 6]  # Mumbai / any

def _generate_delay_data(n=2000):
    """
    Synthetic delay dataset.
    Rules baked in:
    - Peak hours → higher base delay
    - Through trains → shorter dwell, less delay
    - Terminating trains → longer dwell, more delay variance
    - Originating trains → usually on time (they start here)
    """
    random.seed(42)
    X, y = [], []
    types  = ['Through', 'Terminating', 'Originating']
    routes = ['Mumbai', 'Solapur', 'Miraj']

    for _ in range(n):
        hour   = random.randint(0, 23)
        minute = random.randint(0, 59)
        ttype  = random.choice(types)
        route  = random.choice(routes)

        base = 0
        if _is_peak(hour):
            base += random.uniform(3, 10)
        if ttype == 'Terminating':
            base += random.uniform(0, 8)
        elif ttype == 'Through':
            base += random.uniform(0, 5)
        else:  # Originating — starts here, rarely delayed
            base += random.uniform(0, 2)

        delay = max(0, base + random.gauss(0, 2))
        X.append(_features(hour, minute, ttype, route))
        y.append(round(delay, 1))

    return np.array(X), np.array(y)


def _generate_platform_data(n=3000):
    """
    Synthetic platform assignment dataset.
    The 'label' is what the cost-function allocator would choose:
    - Miraj route  → prefer P1-3
    - Solapur route → prefer P4-6
    - Mumbai route  → any, slight preference for P1-3 (historical)
    - Add noise to make the model generalise
    """
    random.seed(7)
    X, y = [], []
    types  = ['Through', 'Terminating', 'Originating']
    routes = ['Mumbai', 'Solapur', 'Miraj']

    for _ in range(n):
        hour        = random.randint(0, 23)
        minute      = random.randint(0, 59)
        ttype       = random.choice(types)
        route       = random.choice(routes)
        num_active  = random.randint(0, 6)

        preferred = _preferred_platforms(route)
        # 80 % of the time pick from preferred zone, 20 % crossover
        if random.random() < 0.80:
            platform = random.choice(preferred)
        else:
            all_p = [1, 2, 3, 4, 5, 6]
            platform = random.choice([p for p in all_p if p not in preferred] or all_p)

        X.append(_features(hour, minute, ttype, route, num_active))
        y.append(platform)

    return np.array(X), np.array(y)


# ── Train models at import time ───────────────────────────────────────────────

print("[ML] Training delay predictor...")
_Xd, _yd = _generate_delay_data()
delay_model = RandomForestRegressor(n_estimators=80, max_depth=8, random_state=42)
delay_model.fit(_Xd, _yd)
print("[ML] Delay predictor ready.")

print("[ML] Training platform recommender...")
_Xp, _yp = _generate_platform_data()
platform_model = RandomForestClassifier(n_estimators=80, max_depth=8, random_state=42)
platform_model.fit(_Xp, _yp)
print("[ML] Platform recommender ready.")


# ── Public inference functions ────────────────────────────────────────────────

def predict_delay(hour: int, minute: int, train_type: str, route: str) -> int:
    """Return predicted delay in whole minutes (0 = on time)."""
    feats = np.array([_features(hour, minute, train_type, route)]).reshape(1, -1)
    raw = delay_model.predict(feats)[0]
    return max(0, int(round(raw)))


def predict_platform(hour: int, minute: int, train_type: str, route: str,
                     num_active: int = 0) -> int:
    """Return ML-recommended platform number (1-6)."""
    feats = np.array([_features(hour, minute, train_type, route, num_active)]).reshape(1, -1)
    return int(platform_model.predict(feats)[0])


# ── Visualization Section ────────────────────────────────────────────────────
import matplotlib.pyplot as plt

def plot_graphs():
    print("[ML] Generating graphs...")

    # --- 1. Delay Distribution ---
    plt.figure()
    plt.hist(_yd, bins=30, color='blue', edgecolor='black')
    plt.title("Delay Distribution")
    plt.xlabel("Delay (minutes)")
    plt.ylabel("Frequency")
    plt.show()

    # --- 2. Delay vs Hour ---
    hours = _Xd[:, 0]
    plt.figure()
    plt.scatter(hours, _yd, alpha=0.5, color='green')
    plt.title("Delay vs Hour of Day")
    plt.xlabel("Hour")
    plt.ylabel("Delay (minutes)")
    plt.grid()
    plt.show()

    # --- 3. Platform Distribution ---
    plt.figure()
    plt.hist(_yp, bins=6, color='orange', edgecolor='black')
    plt.title("Platform Usage Distribution")
    plt.xlabel("Platform Number")
    plt.ylabel("Frequency")
    plt.grid()
    plt.show()

    # --- 4. Feature Importance (Delay Model) ---
    plt.figure()
    plt.bar(range(len(delay_model.feature_importances_)),
            delay_model.feature_importances_,
            color='red')
    plt.title("Delay Model Feature Importance")
    plt.xlabel("Feature Index")
    plt.ylabel("Importance")
    plt.grid()
    plt.show()

    # --- 5. Feature Importance (Platform Model) ---
    plt.figure()
    plt.bar(range(len(platform_model.feature_importances_)),
            platform_model.feature_importances_,
            color='purple')
    plt.title("Platform Model Feature Importance")
    plt.xlabel("Feature Index")
    plt.ylabel("Importance")
    plt.grid()
    plt.show()

    print("[ML] Graphs displayed.")


# Call this function manually when needed
if __name__ == "__main__":
    plot_graphs()