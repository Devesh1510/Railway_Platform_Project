from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import time
from ml_models import predict_delay, predict_platform
from database import init_db, update_train_record, get_all_trains

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION ---
# Trains are kept on the board until their calculated end_time passes

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
        
        # Updated to catch "Originating" from your new timetable
        if self.type in ['Origin', 'Originating']:
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

    now_mins = datetime.now().hour * 60 + datetime.now().minute

    def _sort_key(x):
        s = x.start_needed
        # If start_needed is more than 60 mins in the past relative to now,
        # it's a next-day train — push it to the end of the sort order
        if s < now_mins - 60:
            s += 1440
        return (0 if x.force_platform else 1, s)

    train_objs = [Train(t) for t in train_data]
    train_objs.sort(key=_sort_key)
    num_active = len(train_objs)

    # Track which platforms are hard-claimed by force assignments at what time ranges
    # so displaced trains can be detected and re-routed
    force_claimed = {}  # pid -> (start, end, train_number)

    for train in train_objs:
        best_pid = -1
        status_msg = ""
        is_conflict = False

        h, m = train.mins // 60, train.mins % 60
        predicted_delay = predict_delay(h, m, train.type, train.route)
        ml_suggested_platform = predict_platform(h, m, train.type, train.route, num_active)

        if train.force_platform:
            best_pid = train.force_platform
            # Clear the locked_platform on any other train that was sitting here
            # so the cost function re-assigns them freely
            for other in train_objs:
                if (other.number != train.number and
                        other.locked_platform == best_pid):
                    other.locked_platform = None
                    other.data_ref['allocated_platform'] = None

        elif train.locked_platform:
            # Only honour the lock if no force train has claimed this platform
            # during an overlapping time window
            pid = train.locked_platform
            if pid in force_claimed:
                fc = force_claimed[pid]
                overlap = not (train.start_needed >= fc[1] or
                               (train.start_needed + train.duration) <= fc[0])
                if overlap:
                    # Displaced — fall through to cost function
                    train.locked_platform = None
                    train.data_ref['allocated_platform'] = None
                    best_pid = -1
                else:
                    best_pid = pid
            else:
                best_pid = pid

        if best_pid == -1:
            # Cost-function assignment
            min_cost = float('inf')
            pref_zone = ('Miraj' if 'Miraj' in train.route
                         else 'Solapur' if 'Solapur' in train.route
                         else 'Any')

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

        pref_zone = ('Miraj' if 'Miraj' in train.route
                     else 'Solapur' if 'Solapur' in train.route
                     else 'Any')
        if pref_zone != 'Any' and p_data['zone'] != pref_zone:
            is_conflict = True

        end_time = actual_start + train.duration
        PLATFORMS[best_pid]['free_at'] = end_time

        if train.force_platform:
            force_claimed[best_pid] = (actual_start, end_time, train.number)
            status_msg = "MANUAL OVERRIDE"
        elif train.locked_platform:
            status_msg = "LOCKED"
        elif is_conflict and actual_start == train.start_needed:
            status_msg = "SMART CROSSOVER"
        elif is_conflict:
            status_msg = "CROSSOVER"
        elif actual_start > train.start_needed:
            status_msg = f"DELAYED {actual_start - train.start_needed}m"
        else:
            status_msg = "ON TIME"

        schedule_results.append({
            "train_no":              train.number,
            "name":                  train.name,
            "arrival":               train.time_str,
            "route":                 train.route,
            "train_type":            train.type,
            "allocated_platform":    best_pid,
            "ml_suggested_platform": ml_suggested_platform,
            "predicted_delay_mins":  predicted_delay,
            "status":                status_msg,
            "end_time_str":          f"{end_time//60:02d}:{end_time%60:02d}",
            "is_conflict":           is_conflict or bool(train.force_platform and is_conflict),
        })

        # ── Persist to SQLite ────────────────────────────────────────────────
        update_train_record(
            train_no          = train.number,
            name              = train.name,
            train_type        = train.type,
            route             = train.route,
            scheduled_arrival = train.time_str,
            predicted_delay   = predicted_delay,
            platform_assigned = best_pid,
            departure_time    = f"{end_time//60:02d}:{end_time%60:02d}",
            status            = status_msg,
        )

    return schedule_results

# --- GLOBAL DATA STORE ---

# 1. THE MASTER TIMETABLE (All trains for the day)
MASTER_TIMETABLE = [
    # --- EARLY MORNING & MORNING ---
    {"number": "17318", "name": "DADAR - HUBBALLI EXPRESS", "time": "00:05", "type": "Through", "route": "Miraj", "journey_days": 0},
    {"number": "17411", "name": "CSMT - KOLHAPUR MAHALAXMI EXPRESS", "time": "00:15", "type": "Through", "route": "Miraj", "journey_days": 0},
    {"number": "16339", "name": "CSMT - NAGERCOIL EXP", "time": "00:25", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "16351", "name": "CSMT - NAGERCOIL EXP", "time": "00:25", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "22107", "name": "CSMT - LATUR EXP", "time": "00:30", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "18519", "name": "VISAKHAPATNAM - LTT EXP", "time": "00:35", "type": "Through", "route": "Solapur", "journey_days": 1},
    {"number": "11021", "name": "DADAR - TIRUNELVELI EXP", "time": "00:45", "type": "Through", "route": "Miraj", "journey_days": 0},
    {"number": "12702", "name": "HYDERABAD - CSMT HUSSAINSAGAR EXP", "time": "00:45", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "11139", "name": "CSMT - HOSPET EXP", "time": "01:00", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "11140", "name": "HOSPET - CSMT EXP", "time": "01:00", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "12701", "name": "CSMT - HYDERABAD HUSSAINSAGAR EXP", "time": "01:05", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "22718", "name": "SECUNDERABAD - RAJKOT EXP", "time": "01:20", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "22158", "name": "CHENNAI - CSMT SF EXP", "time": "01:45", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "11013", "name": "LTT - COIMBATORE EXP", "time": "01:55", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "11038", "name": "GORAKHPUR - PUNE EXP", "time": "02:15", "type": "Terminating", "route": "Solapur", "journey_days": 0},
    {"number": "22846", "name": "HATIA - PUNE EXP", "time": "02:15", "type": "Terminating", "route": "Solapur", "journey_days": 0},
    {"number": "12115", "name": "CSMT - SOLAPUR SIDDHESHWAR EXP", "time": "02:35", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "22157", "name": "CSMT - CHENNAI SF EXP", "time": "02:50", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "20822", "name": "SANTRAGACHI - PUNE HUMSAFAR", "time": "02:45", "type": "Terminating", "route": "Mumbai", "journey_days": 0},
    {"number": "17317", "name": "HUBBALLI - DADAR EXPRESS", "time": "02:55", "type": "Through", "route": "Miraj", "journey_days": 0},
    {"number": "17412", "name": "KOLHAPUR - CSMT MAHALAXMI EXPRESS", "time": "03:20", "type": "Through", "route": "Miraj", "journey_days": 0},
    {"number": "11040", "name": "GONDIA - KOLHAPUR MAHARASHTRA EXPRESS", "time": "03:25", "type": "Through", "route": "Miraj", "journey_days": 0},
    {"number": "11010", "name": "PUNE - MUMBAI SINHGAD EXPRESS", "time": "06:05", "type": "Originating", "route": "Mumbai", "journey_days": 0},
    {"number": "12025", "name": "PUNE - HYDERABAD SHATABDI EXP", "time": "06:05", "type": "Originating", "route": "Solapur", "journey_days": 0},
    {"number": "26101", "name": "PUNE - AJNI VANDE BHARAT", "time": "06:25", "type": "Originating", "route": "Solapur", "journey_days": 0},
    {"number": "12124", "name": "PUNE - CSMT DECCAN QUEEN", "time": "07:15", "type": "Originating", "route": "Mumbai", "journey_days": 0},
    {"number": "12126", "name": "PUNE - CSMT PRAGATI EXPRESS", "time": "07:50", "type": "Originating", "route": "Mumbai", "journey_days": 0},
    {"number": "22944", "name": "INDORE - DAUND EXPRESS", "time": "08:45", "type": "Through", "route": "Solapur", "journey_days": 1},
    {"number": "22105", "name": "MUMBAI - PUNE INDRAYANI EXPRESS", "time": "09:05", "type": "Terminating", "route": "Mumbai", "journey_days": 0},
    {"number": "22226", "name": "SOLAPUR - MUMBAI VANDE BHARAT EXPRESS", "time": "09:15", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "12127", "name": "MUMBAI - PUNE INTERCIY EXPRESS", "time": "09:30", "type": "Terminating", "route": "Mumbai", "journey_days": 0},
    {"number": "12169", "name": "PUNE - SOLAPUR SF", "time": "09:30", "type": "Originating", "route": "Solapur", "journey_days": 0},
    {"number": "12114", "name": "NAGPUR - PUNE GARIBRATH", "time": "09:30", "type": "Terminating", "route": "Solapur", "journey_days": 0},
    {"number": "12136", "name": "NAGPUR - PUNE SUPERFAST", "time": "09:30", "type": "Terminating", "route": "Solapur", "journey_days": 0},
    {"number": "12849", "name": "BILASPUR - PUNE EXP", "time": "09:30", "type": "Terminating", "route": "Solapur", "journey_days": 0},
    {"number": "16587", "name": "YESVANTPUR - BIKANER EXPRESS", "time": "09:35", "type": "Through", "route": "Solapur", "journey_days": 2},
    {"number": "11014", "name": "COIMBATORE-LTT EXPRESS", "time": "10:15", "type": "Through", "route": "Solapur", "journey_days": 2},
    {"number": "18520", "name": "LTT - VISAKHAPATNAM EXPRESS", "time": "10:15", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "12158", "name": "SOLAPUR - PUNE HUTATMA EXPRESS", "time": "10:30", "type": "Terminating", "route": "Solapur", "journey_days": 0},
    {"number": "20821", "name": "PUNE - SANTRAGACHI HUMSAFAR", "time": "10:40", "type": "Originating", "route": "Mumbai", "journey_days": 0},
    {"number": "11007", "name": "CSMT - PUNE DECCAN EXPRESS", "time": "11:05", "type": "Terminating", "route": "Mumbai", "journey_days": 0},
    {"number": "22152", "name": "KAZIPET - PUNE SF EXP", "time": "10:50", "type": "Terminating", "route": "Solapur", "journey_days": 1},
    {"number": "11025", "name": "PUNE - AMRAVATI EXPRESS", "time": "11:05", "type": "Originating", "route": "Solapur", "journey_days": 0},
    {"number": "12263", "name": "PUNE - H.NIZAMUDDIN DURONTO EXPRESS", "time": "11:10", "type": "Originating", "route": "Mumbai", "journey_days": 0},
    {"number": "12103", "name": "PUNE - LUCKNOW SF EXPRESS", "time": "11:15", "type": "Originating", "route": "Solapur", "journey_days": 0},
    {"number": "20161", "name": "PUNE - JABALPUR EXPRESS", "time": "11:20", "type": "Originating", "route": "Solapur", "journey_days": 0},
    {"number": "22686", "name": "YESVANTPUR KARNATAKA SAMPARK KRANTI EXPRESS", "time": "11:20", "type": "Through", "route": "Miraj", "journey_days": 1},
    {"number": "22140", "name": "AJNI - PUNE HUMSAFAR", "time": "11:30", "type": "Terminating", "route": "Solapur", "journey_days": 1},
    {"number": "11026", "name": "AMRAVATI - PUNE EXPRESS", "time": "11:40", "type": "Terminating", "route": "Solapur", "journey_days": 1},
    {"number": "11301", "name": "CSMT - BENGALURU UDYAN EXPRESS", "time": "11:40", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "12164", "name": "MADRAS - LTT SF EXPRESS", "time": "11:45", "type": "Through", "route": "Solapur", "journey_days": 1},

    # --- AFTERNOON ---
    {"number": "11059", "name": "LTT -  CHHAPRA EXPRESS", "time": "12:20", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "22360", "name": "CSMT - PATNA SF EXPRESS", "time": "12:45", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "11012", "name": "DHULE - CSMT  EXPRESS", "time": "12:50", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "20705", "name": "NANDED - CSMT VANDE BHARAT", "time": "12:55", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "11029", "name": "CSMT - KOLHAPUR KOYNA EXPRESS", "time": "12:40", "type": "Through", "route": "Miraj", "journey_days": 0},
    {"number": "20673", "name": "KOLHAPUR - PUNE VANDE BHARAT", "time": "13:30", "type": "Terminating", "route": "Miraj", "journey_days": 0},
    {"number": "20669", "name": "HUBBALLI - PUNE VANDE BHARAT", "time": "13:30", "type": "Terminating", "route": "Miraj", "journey_days": 0},
    {"number": "20674", "name": "PUNE - KOLHAPUR VANDE BHARAT", "time": "14:10", "type": "Originating", "route": "Miraj", "journey_days": 0},
    {"number": "20670", "name": "PUNE - HUBBALLI VANDE BHARAT", "time": "14:10", "type": "Originating", "route": "Miraj", "journey_days": 0},
    {"number": "16340", "name": "NAGERCOIL - LTT EXPRESS", "time": "15:05", "type": "Through", "route": "Solapur", "journey_days": 1},
    {"number": "22123", "name": "PUNE - AJNI AC EXPRESS", "time": "15:15", "type": "Originating", "route": "Solapur", "journey_days": 0},
    {"number": "12221", "name": "PUNE - HOWRAH DURONTO", "time": "15:15", "type": "Originating", "route": "Solapur", "journey_days": 0},
    {"number": "11008", "name": "PUNE - MUMBAI DECCAN EXPRESS", "time": "15:15", "type": "Originating", "route": "Mumbai", "journey_days": 0},
    {"number": "22943", "name": "DAUND - INDORE SF EXPRESS", "time": "15:25", "type": "Through", "route": "Mumbai", "journey_days": 0},
    {"number": "11030", "name": "MUMBAI KOYNA EXPRESS", "time": "15:45", "type": "Through", "route": "Mumbai", "journey_days": 0},
    {"number": "11302", "name": "BENGALURU - CSMT UDYAN EXPRESS", "time": "15:55", "type": "Through", "route": "Solapur", "journey_days": 1},
    {"number": "11078", "name": "JAMMUTAWI - PUNE JHELUM EXP", "time": "16:00", "type": "Terminating", "route": "Solapur", "journey_days": 2},
    {"number": "22159", "name": "CSMT - CHENNAI SF EXPRESS", "time": "16:20", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "22101", "name": "LTT - MADURAI EXPRESS", "time": "16:35", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "19667", "name": "UDAIPUR - MYSORE PALACE QUEEN HUMSAFAR EXPRESS", "time": "16:40", "type": "Through", "route": "Miraj", "journey_days": 2},

    # --- EVENING ---
    {"number": "12780", "name": "VASCO DA GAMA GOA EXPRESS", "time": "17:10", "type": "Through", "route": "Miraj", "journey_days": 1},
    {"number": "11077", "name": "PUNE - JAMMUTAWI JHELUM EXP", "time": "17:20", "type": "Originating", "route": "Solapur", "journey_days": 0},
    {"number": "12135", "name": "PUNE - NAGPUR SF EXPRESS", "time": "17:35", "type": "Originating", "route": "Solapur", "journey_days": 0},
    {"number": "12113", "name": "PUNE - NAGPUR GARIBRATH", "time": "17:35", "type": "Originating", "route": "Solapur", "journey_days": 0},
    {"number": "12157", "name": "SOLAPUR HUTATMA EXPRESS", "time": "17:50", "type": "Originating", "route": "Solapur", "journey_days": 0},
    {"number": "12128", "name": "PUNE - CSMT INTERCITY EXP", "time": "17:55", "type": "Originating", "route": "Mumbai", "journey_days": 0},
    {"number": "11019", "name": "BHUBANESHWAR KONARK EXP", "time": "17:55", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "22732", "name": "CSMT - HYDERABAD SF", "time": "18:05", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "12170", "name": "SOLAPUR - PUNE INTERCITY", "time": "18:05", "type": "Terminating", "route": "Solapur", "journey_days": 0},
    {"number": "12129", "name": "PUNE - HOWRAH AZAD HIND EXP", "time": "18:30", "type": "Originating", "route": "Solapur", "journey_days": 0},
    {"number": "22106", "name": "PUNE - CSMT INDRAYANI EXPRESS", "time": "18:35", "type": "Originating", "route": "Mumbai", "journey_days": 0},
    {"number": "22225", "name": "CSMT - SOLAPUR VANDE BHARAT", "time": "19:05", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "17613", "name": "PANVEL - NANDED EXPRESS", "time": "19:15", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "12125", "name": "CSMT - PUNE PRAGATI EXPRESS", "time": "19:50", "type": "Terminating", "route": "Mumbai", "journey_days": 0},
    {"number": "12123", "name": "CSMT - PUNE DECCAN QUEEN", "time": "20:25", "type": "Terminating", "route": "Mumbai", "journey_days": 0},

    # --- NIGHT ---
    {"number": "11401", "name": "PUNE - SUPAUL EXP", "time": "21:00", "type": "Originating", "route": "Solapur", "journey_days": 0},
    {"number": "16613", "name": "RAJKOT - COIMBATORE EXP", "time": "21:10", "type": "Through", "route": "Solapur", "journey_days": 1},
    {"number": "22717", "name": "RAJKOT - SECUNDERABAD EXP", "time": "21:20", "type": "Through", "route": "Solapur", "journey_days": 1},
    {"number": "26102", "name": "AJNI - PUNE VANDE BHARAT", "time": "21:50", "type": "Terminating", "route": "Solapur", "journey_days": 0},
    {"number": "11009", "name": "CSMT - PUNE SINHGAD EXPRESS", "time": "21:55", "type": "Terminating", "route": "Mumbai", "journey_days": 0},
    {"number": "22117", "name": "PUNE - AMRAVATI AC EXP", "time": "22:00", "type": "Originating", "route": "Solapur", "journey_days": 0},
    {"number": "22141", "name": "PUNE - NAGPUR HUMSAFAR EXP", "time": "22:00", "type": "Originating", "route": "Solapur", "journey_days": 0},
    {"number": "22139", "name": "PUNE - AJNI HUMSAFAR EXP", "time": "22:00", "type": "Originating", "route": "Solapur", "journey_days": 0},
    {"number": "12163", "name": "LTT - CHENNAI SF EXP", "time": "22:10", "type": "Through", "route": "Solapur", "journey_days": 0},
    {"number": "16507", "name": "JODHPUR - BENGALURU EXPRESS", "time": "22:25", "type": "Through", "route": "Miraj", "journey_days": 1},
    {"number": "12026", "name": "HYDERABAD - PUNE SHATABDI", "time": "23:10", "type": "Terminating", "route": "Solapur", "journey_days": 0},
    {"number": "11424", "name": "SAINAGAR SHIRDI - PUNE EXP", "time": "23:50", "type": "Terminating", "route": "Solapur", "journey_days": 0},
    {"number": "11020", "name": "BHUBANESHWAR - CSMT KONARK EXP", "time": "23:35", "type": "Through", "route": "Solapur", "journey_days": 1}
]

# 2. THE ACTIVE BOARD (Trains currently at the station)
train_db = []

# 3. MANUALLY DELETED TRAINS (blocked from auto re-add for the session)
deleted_numbers = set()

# 4. TRAINS DEPARTED FROM PUNE JN — tracked for nearby station "ARRIVING NOW" display
# { train_no: departed_at_timestamp }
departed_trains = {}

# ── Initialise SQLite DB with master timetable ────────────────────────────────
init_db(MASTER_TIMETABLE)

# --- AUTO UPDATE LOGIC ---
def process_automated_schedule():
    global train_db
    now = datetime.now()
    current_mins = now.hour * 60 + now.minute
    current_time_sec = time.time()

    # Flush stale trains — with midnight wrap awareness
    def _end_mins(t):
        try:
            th2, tm2 = map(int, t['time'].split(':'))
            t_mins2 = th2 * 60 + tm2
            train_type = t.get('type', 'Through')
            dur = 45 if train_type in ['Origin', 'Originating'] else 30 if train_type == 'Terminating' else 15
            end = t_mins2 + dur
            # If the train's scheduled time is earlier than now by more than 1 hr,
            # it's a next-day train — shift end_mins forward by 1440
            if t_mins2 < current_mins - 60:
                end += 1440
            return end
        except Exception:
            return current_mins + 1

    if not any(t.get('manually_added') for t in train_db):
        train_db = [t for t in train_db if current_mins < _end_mins(t)]

    # ACTION 1: AUTO-ADD trains arriving within the next 3 hours
    # Handle midnight rollover: if t_mins < current_mins, the train is next day
    for t in MASTER_TIMETABLE:
        th, tm = map(int, t['time'].split(':'))
        t_mins = th * 60 + tm

        # Adjust for midnight wrap: if train time is earlier in the day,
        # it's actually tomorrow — add 1440 to get correct forward difference
        time_diff = t_mins - current_mins
        if time_diff < -60:          # clearly in the past by more than 1 hr → next day
            time_diff += 1440

        if 0 <= time_diff <= 180:
            if not any(active['number'] == t['number'] for active in train_db):
                if t['number'] not in deleted_numbers:
                    new_train = t.copy()
                    new_train['allocated_platform'] = None
                    new_train['force_platform'] = ""
                    new_train['added_at'] = current_time_sec
                    train_db.append(new_train)

    # ACTION 2: Run the allocation
    current_schedule = run_allocation(train_db)

    # ACTION 3: AUTO-DELETE trains whose platform time has fully elapsed
    active_trains_to_keep = []
    final_schedule_to_show = []

    for s in current_schedule:
        original_train = next((t for t in train_db if t['number'] == s['train_no']), None)
        if original_train:
            try:
                th2, tm2 = map(int, original_train['time'].split(':'))
                t_mins2 = th2 * 60 + tm2
                train_type = original_train.get('type', 'Through')
                if train_type in ['Origin', 'Originating']:
                    duration = 45
                elif train_type == 'Terminating':
                    duration = 30
                else:
                    duration = 15
                end_mins = t_mins2 + duration
                # Midnight wrap: next-day train
                if t_mins2 < current_mins - 60:
                    end_mins += 1440
            except (ValueError, KeyError):
                end_mins = current_mins + 1

            # Manually added trains: keep alive based on their scheduled end time
            # (same logic as auto trains), but never drop them before dwell completes
            if original_train.get('manually_added'):
                added_at = original_train.get('added_at', current_time_sec)
                alive_mins = (current_time_sec - added_at) / 60
                # Keep if still within dwell duration OR scheduled end hasn't passed
                if alive_mins < duration or current_mins < end_mins:
                    active_trains_to_keep.append(original_train)
                    final_schedule_to_show.append(s)
                continue

            if current_mins < end_mins:
                active_trains_to_keep.append(original_train)
                final_schedule_to_show.append(s)
            elif end_mins > 1440 and current_mins < (end_mins - 1440):
                # Midnight wrap: end_mins crossed midnight, current_mins is early morning
                active_trains_to_keep.append(original_train)
                final_schedule_to_show.append(s)

    train_db = active_trains_to_keep
    return final_schedule_to_show

# --- API ENDPOINTS ---
@app.route('/api/schedule', methods=['GET'])
def get_schedule():
    # Every time React asks for data, process the automation!
    latest_schedule = process_automated_schedule()
    return jsonify(latest_schedule)

@app.route('/api/add-train', methods=['POST'])
def add_train():
    new_train = request.json
    new_train['allocated_platform'] = None
    new_train['added_at'] = time.time()
    new_train['manually_added'] = True  # flag so auto-delete never drops it prematurely
    # Unblock from deleted/departed sets so it shows everywhere
    train_no = new_train.get('number', '')
    deleted_numbers.discard(train_no)
    departed_trains.pop(train_no, None)
    train_db.append(new_train)
    return jsonify({"message": "Added manually"})

@app.route('/api/delete-train/<train_no>', methods=['DELETE'])
def delete_train(train_no):
    global train_db
    deleted_numbers.add(train_no)
    # Record departure time for nearby station "ARRIVING NOW" display
    departed_trains[train_no] = time.time()
    train_db = [t for t in train_db if t['number'] != train_no]
    return jsonify({"message": "Deleted manually"})

@app.route('/api/nearby-stations', methods=['GET'])
def get_nearby_stations():
    now = datetime.now()
    current_mins = now.hour * 60 + now.minute
    current_time_sec = time.time()

    # Station config: name -> route keyword, distance_mins (travel time from Pune Jn)
    NEARBY = {
        'Hadapsar':     {'route': 'Solapur', 'travel_mins': 8},
        'Shivajinagar': {'route': 'Mumbai',  'travel_mins': 5},
        'Ghorpuri':     {'route': 'Miraj',   'travel_mins': 4},
    }

    result = {}
    ARRIVING_NOW_WINDOW = 8  # seconds after delete to show "ARRIVING NOW"

    # Build lookup of manually added trains by number (these override master data)
    manual_by_number = {t['number']: t for t in train_db if t.get('manually_added')}

    # Build unified source: master timetable entries, overridden by manual re-adds
    all_trains = []
    master_numbers_seen = set()
    for t in MASTER_TIMETABLE:
        num = t['number']
        master_numbers_seen.add(num)
        if num in manual_by_number:
            all_trains.append(manual_by_number[num])  # use re-added version
        else:
            all_trains.append(t)
    # Add any manual trains whose number isn't in master at all
    for num, t in manual_by_number.items():
        if num not in master_numbers_seen:
            all_trains.append(t)

    for station, cfg in NEARBY.items():
        trains = []
        seen = set()  # avoid duplicates if a manual train matches master number

        for t in all_trains:
            if cfg['route'] not in t['route']:
                continue
            if t['number'] in seen:
                continue

            th, tm = map(int, t['time'].split(':'))
            t_mins = th * 60 + tm
            time_diff = t_mins - current_mins
            if time_diff < 0:
                time_diff += 1440

            if -cfg['travel_mins'] <= time_diff <= 180:
                departed_at = departed_trains.get(t['number'])
                if departed_at:
                    elapsed = current_time_sec - departed_at
                    if elapsed <= ARRIVING_NOW_WINDOW:
                        status = 'ARRIVING NOW'
                    else:
                        departed_trains.pop(t['number'], None)
                        continue
                elif t['number'] in deleted_numbers:
                    # Blocked — but if it's back in train_db (manually re-added), show it
                    if not any(db_t['number'] == t['number'] for db_t in train_db):
                        continue
                    mins_away = max(0, time_diff) + cfg['travel_mins']
                    status = 'ARRIVING SOON' if mins_away <= 5 else f'In {mins_away} min'
                elif time_diff < 0:
                    continue
                else:
                    mins_away = time_diff + cfg['travel_mins']
                    status = 'ARRIVING SOON' if mins_away <= 5 else f'In {mins_away} min'

                seen.add(t['number'])
                trains.append({
                    'train_no': t['number'],
                    'name': t['name'],
                    'pune_time': t['time'],
                    'type': t['type'],
                    'route': t['route'],
                    'status': status,
                })

        result[station] = trains

    return jsonify(result)


@app.route('/api/db/trains', methods=['GET'])
def get_db_trains():
    """Return all train records from SQLite as JSON."""
    return jsonify(get_all_trains())


@app.route('/api/live-status/<train_no>', methods=['GET'])
def get_live_status(train_no):
    """Fetch live running status using journey_days from MASTER_TIMETABLE."""
    try:
        import re
        from railsutra import get_live_train_status
        from datetime import datetime as dt, timedelta

        # Look up journey_days from master timetable
        master_entry = next((t for t in MASTER_TIMETABLE if t['number'] == train_no), None)
        journey_days = master_entry.get('journey_days', 0) if master_entry else 0

        query_date = (dt.now() - timedelta(days=journey_days)).strftime('%d-%m-%Y')
        result = get_live_train_status(train_no, query_date)

        if not result or result[0] is None:
            return jsonify({'last_station': None, 'delay': None, 'dep_time': None})

        msg = result[0]
        delay_match   = re.search(r'late by (\d+) Minutes', msg)
        station_match = re.search(r'departed (.+?) \(', msg)
        time_match    = re.search(r'at (\d{2}:\d{2})', msg)
        return jsonify({
            'last_station': station_match.group(1).strip() if station_match else None,
            'delay':        int(delay_match.group(1)) if delay_match else 0,
            'dep_time':     time_match.group(1) if time_match else None,
            'journey_days': journey_days,
        })
    except Exception as e:
        return jsonify({'last_station': None, 'delay': None, 'dep_time': None, 'error': str(e)})


if __name__ == '__main__':
    app.run(debug=True, port=5000)