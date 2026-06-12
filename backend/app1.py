from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

# --- ALGORITHM LOGIC START ---

PLATFORMS = {
    1: {'id': 1, 'zone': 'Miraj', 'free_at': 0},
    2: {'id': 2, 'zone': 'Miraj', 'free_at': 0},
    3: {'id': 3, 'zone': 'Miraj', 'free_at': 0},
    4: {'id': 4, 'zone': 'Solapur', 'free_at': 0},
    5: {'id': 5, 'zone': 'Solapur', 'free_at': 0},
    6: {'id': 6, 'zone': 'Solapur', 'free_at': 0},
}

class Train:
    def __init__(self, data_dict):
        self.data_ref = data_dict
        self.number = data_dict['number']
        self.name = data_dict['name']
        self.time_str = data_dict['time']
        self.type = data_dict['type']
        self.route = data_dict['route']
        
        self.force_platform = int(data_dict['force_platform']) if data_dict.get('force_platform') else None
        self.locked_platform = int(data_dict['allocated_platform']) if data_dict.get('allocated_platform') else None

        try:
            h, m = map(int, self.time_str.split(':'))
            self.mins = h * 60 + m
        except ValueError:
            self.mins = 0
        
        if self.type == 'Origin':
            self.start_needed = self.mins - 45
            self.duration = 45
        else:
            self.start_needed = self.mins
            self.duration = 30 if self.type == 'Terminating' else 15

def reset_platforms():
    for p in PLATFORMS.values():
        p['free_at'] = 0

def run_allocation(train_data):
    reset_platforms()
    schedule_results = []
    
    train_objs = [Train(t) for t in train_data]
    train_objs.sort(key=lambda x: x.start_needed)

    for train in train_objs:
        best_pid = -1
        actual_start = -1
        status_msg = ""
        is_conflict = False

        if train.force_platform:
            best_pid = train.force_platform
        elif train.locked_platform:
            best_pid = train.locked_platform
        else:
            min_cost = float('inf')
            pref_zone = 'Miraj' if 'Miraj' in train.route else 'Solapur' if 'Solapur' in train.route else 'Any'

            for pid, p_data in PLATFORMS.items():
                ready_at = max(p_data['free_at'], train.start_needed)
                wait_time = ready_at - train.start_needed
                
                cost_wait = wait_time
                cost_zone = 0
                if pref_zone != 'Any' and p_data['zone'] != pref_zone:
                    cost_zone = 5 if wait_time == 0 else 50 

                cost_load = p_data['free_at'] / 10000.0

                total_cost = cost_wait + cost_zone + cost_load
                
                if total_cost < min_cost:
                    min_cost = total_cost
                    best_pid = pid
            
            train.data_ref['allocated_platform'] = best_pid

        p_data = PLATFORMS[best_pid]
        ready_at = max(p_data['free_at'], train.start_needed)
        actual_start = ready_at
        
        pref_zone = 'Miraj' if 'Miraj' in train.route else 'Solapur' if 'Solapur' in train.route else 'Any'
        if pref_zone != 'Any' and p_data['zone'] != pref_zone:
            is_conflict = True

        end_time = actual_start + train.duration
        PLATFORMS[best_pid]['free_at'] = end_time

        if train.force_platform: status_msg = "MANUAL OVERRIDE"
        elif train.locked_platform: status_msg = "LOCKED"
        elif is_conflict and actual_start == train.start_needed: status_msg = "SMART CROSSOVER"
        elif is_conflict: status_msg = "CROSSOVER"
        elif actual_start > train.start_needed: status_msg = f"DELAYED {actual_start - train.start_needed}m"
        else: status_msg = "ON TIME"

        schedule_results.append({
            "train_no": train.number,
            "name": train.name,
            "arrival": train.time_str,
            "allocated_platform": best_pid,
            "status": status_msg,
            "end_time_str": f"{end_time//60:02d}:{end_time%60:02d}",
            "end_mins": end_time, # Hidden value for auto-delete calculation
            "is_conflict": is_conflict or (train.force_platform and is_conflict)
        })

    return schedule_results

# --- GLOBAL DATA STORE ---

# 1. THE MASTER TIMETABLE (All trains for the day)
MASTER_TIMETABLE = [
    {"number": "11041", "name": "PUNE- SUPAUL EXP", "time": "21:05", "type": "Originating", "route": "Solapur"},
    {"number": "22717", "name": "RAJKOT - SECUNDERABAD EXP", "time": "21:10", "type": "Through", "route": "Solapur"},
    {"number": "01023", "name": "PUNE - KOP SPL",  "time": "21:15", "type": "Originating", "route": "Miraj"},
    {"number": "11009", "name": "SINHGAD EXP",  "time": "21:15", "type": "Terminating", "route": "Mumbai"},
    {"number": "22117", "name": "PUNE - AMI AC EXP",  "time": "21:25", "type": "Originating", "route": "Solapur"},
    {"number": "26102", "name": "AJNI - PUNE VANDE BHARAT EXP",  "time": "21:35", "type": "Terminating", "route": "Solapur"},
    {"number": "12163", "name": "LTT - CHENNAI SF EXP",  "time": "21:45", "type": "Through", "route": "Solapur"},
    # Add your own trains here!
]

# 2. THE ACTIVE BOARD (Trains currently at the station)
train_db = [] 

# --- AUTO UPDATE LOGIC ---
def process_automated_schedule():
    global train_db
    now = datetime.now()
    current_mins = now.hour * 60 + now.minute

    # ACTION 1: AUTO-ADD trains arriving in the next 30 minutes
    for t in MASTER_TIMETABLE:
        th, tm = map(int, t['time'].split(':'))
        t_mins = th * 60 + tm
        
        time_diff = t_mins - current_mins
        
        # If train arrives within 30 mins, and isn't already on the board
        if 0 <= time_diff <= 30:
            if not any(active['number'] == t['number'] for active in train_db):
                new_train = t.copy()
                new_train['allocated_platform'] = None
                new_train['force_platform'] = ""
                train_db.append(new_train)

    # ACTION 2: Run the AI allocation
    current_schedule = run_allocation(train_db)

    # ACTION 3: AUTO-DELETE trains that have departed
    active_trains_to_keep = []
    final_schedule_to_show = []

    for s in current_schedule:
        # If the train's end time is in the future, keep it on the board
        if current_mins < s['end_mins']:
            # Find the original train dict and keep it
            original_train = next(t for t in train_db if t['number'] == s['train_no'])
            active_trains_to_keep.append(original_train)
            final_schedule_to_show.append(s)

    # Update global database
    train_db = active_trains_to_keep

    return final_schedule_to_show


# --- API ENDPOINTS ---
@app.route('/api/schedule', methods=['GET'])
def get_schedule():
    # Every time React asks for data (every 5 seconds), process the automation!
    latest_schedule = process_automated_schedule()
    return jsonify(latest_schedule)

@app.route('/api/add-train', methods=['POST'])
def add_train():
    new_train = request.json
    new_train['allocated_platform'] = None 
    train_db.append(new_train)
    return jsonify({"message": "Added manually"})

@app.route('/api/delete-train/<train_no>', methods=['DELETE'])
def delete_train(train_no):
    global train_db
    train_db = [t for t in train_db if t['number'] != train_no]
    return jsonify({"message": "Deleted manually"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)