import React, { useState, useEffect } from 'react';
import './App.css';

// --- SHARED COMPONENTS ---

function LiveClock() {
  const [time, setTime] = useState(() => new Date().toLocaleTimeString('en-GB'));
  useEffect(() => {
    const id = setInterval(() => setTime(new Date().toLocaleTimeString('en-GB')), 1000);
    return () => clearInterval(id);
  }, []);
  return <span className="live-clock">{time}</span>;
}

function StatusBadge({ isConflict, label }) {
  return <span className={isConflict ? 'badge badge-conflict' : 'badge badge-ontime'}>{label}</span>;
}

function zoneLabel(route) {
  if (route === 'Miraj' || route === 'Solapur') {
    return <span className="zone-label">{route}</span>;
  }
  return null;
}

// --- PUNE JN TAB ---

const AI_OPTIONS = [
  { value: 'hold_5_8',  text: '⏳ Hold at outer for 5–8 min',  cls: 'ai-hold' },
  { value: 'hold_10',   text: '⏳ Hold at outer for 10 min',    cls: 'ai-hold' },
  { value: 'hold_15',   text: '⏳ Hold at outer for 15 min',    cls: 'ai-hold-long' },
  { value: 'depart',    text: '✅ Depart on time',              cls: 'ai-depart' },
];

function PuneJnTab({ schedule, loading, error, newTrain, setNewTrain, handleAddTrain, handleDelete }) {
  const [aiOverride, setAiOverride]       = useState(false);
  const [aiSelections, setAiSelections]   = useState({});   // { train_no: value }
  const [liveStatus, setLiveStatus]       = useState({});   // { train_no: { last_station, delay } }

  // Fetch live status for all trains in schedule (once per schedule update)
  useEffect(() => {
    schedule.forEach(row => {
      if (liveStatus[row.train_no] !== undefined) return; // already fetched
      fetch(`http://127.0.0.1:5000/api/live-status/${row.train_no}`)
        .then(r => r.json())
        .then(data => setLiveStatus(prev => ({ ...prev, [row.train_no]: data })))
        .catch(() => setLiveStatus(prev => ({ ...prev, [row.train_no]: null })));
    });
  }, [schedule]); // eslint-disable-line react-hooks/exhaustive-deps

  const getPlatformStatus = (pid) => {
    const train = schedule.find(t => t.allocated_platform === pid);
    if (train) {
      const isOriginating = train.train_type === 'Origin' || train.train_type === 'Originating';
      return {
        status: 'occupied',
        trainName: train.name,
        trainNo: train.train_no,
        arrival: isOriginating ? null : train.arrival,
        departure: train.end_time_str,
        isOriginating,
      };
    }
    return { status: 'free', trainName: 'Empty', trainNo: '', arrival: null, departure: null, isOriginating: false };
  };

  const getDefaultAiSuggestion = (row) => {
    const type = row.train_type;
    if (type === 'Origin' || type === 'Originating') return 'depart';
    if (type === 'Terminating') {
      const occupiedCount = schedule.filter(t => t.allocated_platform).length;
      return occupiedCount >= 6 ? 'hold_15' : 'hold_10';
    }
    return 'hold_5_8';
  };

  const getAiDisplay = (row) => {
    const val = aiSelections[row.train_no] || getDefaultAiSuggestion(row);
    return AI_OPTIONS.find(o => o.value === val) || AI_OPTIONS[0];
  };

  return (
    <>
      {/* ADD TRAIN FORM */}
      <div className="form-container">
        <div className="form-header-row">
          <h3 className="form-title">➕ Add / Force Train</h3>
          <button
            className={`btn-override ${aiOverride ? 'btn-override-active' : ''}`}
            onClick={() => setAiOverride(v => !v)}
          >
            {aiOverride ? '🔒 Lock AI Suggestions' : '✏️ Override AI Suggestions'}
          </button>
        </div>
        <div className="form-row">
          <input placeholder="No." value={newTrain.number} onChange={e => setNewTrain({...newTrain, number: e.target.value})} className="form-input form-input-no" />
          <input placeholder="Name" value={newTrain.name} onChange={e => setNewTrain({...newTrain, name: e.target.value})} className="form-input form-input-name" />
          <input type="time" value={newTrain.time} onChange={e => setNewTrain({...newTrain, time: e.target.value})} className="form-input" />
          <select value={newTrain.route} onChange={e => setNewTrain({...newTrain, route: e.target.value})} className="form-select">
            <option value="Solapur">Solapur Side</option>
            <option value="Miraj">Miraj Side</option>
            <option value="Mumbai">Mumbai Side</option>
          </select>
          <select value={newTrain.type} onChange={e => setNewTrain({...newTrain, type: e.target.value})} className="form-select">
            <option value="Through">Through (15m)</option>
            <option value="Terminating">Terminating (30m)</option>
            <option value="Origin">Originating (45m)</option>
          </select>
          <select value={newTrain.force_platform} onChange={e => setNewTrain({...newTrain, force_platform: e.target.value})} className="form-select-force">
            <option value="">Auto Assign</option>
            <option value="1">Force P1</option>
            <option value="2">Force P2</option>
            <option value="3">Force P3</option>
            <option value="4">Force P4</option>
            <option value="5">Force P5</option>
            <option value="6">Force P6</option>
          </select>
          <button onClick={handleAddTrain} className="btn-add">ADD</button>
        </div>
      </div>

      {loading ? (
        <div className="spinner" />
      ) : error ? (
        <p className="error-message">{error}</p>
      ) : (
        <>
          {/* PLATFORM SCHEMATIC DIAGRAM */}
          <div className="platform-schematic">

            {/* Left zone labels */}
            <div className="schematic-labels-left">
              <span className="zone-label-side miraj-label">◀ Miraj</span>
              <span className="zone-label-side solapur-label">◀ Solapur</span>
            </div>

            {/* Platform tracks */}
            <div className="schematic-tracks">
              {[1, 2, 3, 4, 5, 6].map(pid => {
                const { status, trainName, trainNo, arrival, departure, isOriginating } = getPlatformStatus(pid);
                return (
                  <React.Fragment key={pid}>
                    {pid === 4 && <div className="zone-divider" />}
                    <div className={`platform-card ${status}`}>
                      <h3>P{pid}</h3>
                      <h1>{trainNo || '--'}</h1>
                      <p>{trainName}</p>
                      <p className="platform-times">
                        {departure
                          ? isOriginating
                            ? `Dep: ${departure}`
                            : arrival
                              ? `Arr: ${arrival} · Dep: ${departure}`
                              : `Dep: ${departure}`
                          : '--'}
                      </p>
                    </div>
                  </React.Fragment>
                );
              })}
            </div>

            {/* Right label — Mumbai common for all */}
            <div className="schematic-labels-right">
              <span className="zone-label-side mumbai-label">Mumbai ▶</span>
            </div>

          </div>

          {/* SCHEDULE TABLE */}
          <div className="table-wrapper">
            <table className="train-table">
              <thead>
                <tr>
                  <th>No</th>
                  <th>Name</th>
                  <th>Time</th>
                  <th>Allocated</th>
                  <th>ML Platform</th>
                  <th>Pred. Delay</th>
                  <th>Status</th>
                  <th>Running Status</th>
                  <th>AI Suggestion</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {schedule.map((row, index) => (
                  <tr key={index}>
                    <td>{row.train_no}</td>
                    <td>{row.name}</td>
                    <td>
                      {(row.train_type === 'Origin' || row.train_type === 'Originating')
                        ? <span className="dep-label">Dep: {row.end_time_str}</span>
                        : row.arrival}
                    </td>
                    <td><strong>P{row.allocated_platform}</strong>{zoneLabel(row.route)}</td>
                    <td>
                      <span className={`ml-platform-badge ${row.ml_suggested_platform === row.allocated_platform ? 'ml-match' : 'ml-diff'}`}>
                        P{row.ml_suggested_platform}
                        {row.ml_suggested_platform === row.allocated_platform
                          ? ' ✓' : ' ↗'}
                      </span>
                    </td>
                    <td>
                      {row.predicted_delay_mins > 0
                        ? <span className="delay-badge">~{row.predicted_delay_mins} min late</span>
                        : <span className="ontime-badge">On time</span>}
                    </td>
                    <td><StatusBadge isConflict={row.is_conflict} label={row.status} /></td>
                    <td>
                      {(() => {
                        const ls = liveStatus[row.train_no];
                        if (!ls) return <span className="running-status-loading">Fetching…</span>;
                        if (!ls.last_station) return <span className="running-status-na">N/A</span>;
                        return (
                          <span className="running-status">
                            📍 {ls.last_station}
                            {ls.delay > 0 && <span className="running-delay"> (+{ls.delay}m)</span>}
                          </span>
                        );
                      })()}
                    </td>
                    <td>
                      {aiOverride ? (
                        <select
                          className="ai-override-select"
                          value={aiSelections[row.train_no] || getDefaultAiSuggestion(row)}
                          onChange={e => setAiSelections(prev => ({ ...prev, [row.train_no]: e.target.value }))}
                        >
                          {AI_OPTIONS.map(o => (
                            <option key={o.value} value={o.value}>{o.text}</option>
                          ))}
                        </select>
                      ) : (
                        (() => { const s = getAiDisplay(row); return <span className={`ai-suggestion ${s.cls}`}>{s.text}</span>; })()
                      )}
                    </td>
                    <td>
                      <button onClick={() => handleDelete(row.train_no)} className="btn-delete">
                        Delete 🗑️
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}

// --- NEARBY STATIONS TAB ---

const STATION_CONFIG = {
  Hadapsar:     { route: 'Solapur', platforms: 4, distance: '5 km', emoji: '🟠' },
  Shivajinagar: { route: 'Mumbai',  platforms: 2, distance: '3 km', emoji: '🔵' },
  Ghorpuri:     { route: 'Miraj',   platforms: 2, distance: '2 km', emoji: '🟢' },
};

function NearbyStationPanel({ stationName, trains }) {
  const cfg = STATION_CONFIG[stationName];

  return (
    <div className="nearby-panel">
      <div className="nearby-header">
        <span className="nearby-title">{cfg.emoji} {stationName}</span>
        <span className="nearby-meta">{cfg.distance} from Pune Jn · {cfg.platforms} platforms · {cfg.route} corridor</span>
      </div>

      {trains.length === 0 ? (
        <p className="nearby-empty">No upcoming trains in the next 2 hours.</p>
      ) : (
        <div className="table-wrapper">
          <table className="train-table">
            <thead>
              <tr>
                <th>No</th>
                <th>Name</th>
                <th>Pune Jn Time</th>
                <th>Type</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {trains.map((t, i) => {
                const isArrivingNow = t.status === 'ARRIVING NOW';
                const isArrivingSoon = t.status === 'ARRIVING SOON';
                return (
                  <tr key={i} className={isArrivingNow ? 'row-arriving-now' : ''}>
                    <td>{t.train_no}</td>
                    <td>{t.name}</td>
                    <td>{t.pune_time}</td>
                    <td><span className="type-badge">{t.type}</span></td>
                    <td>
                      {isArrivingNow
                        ? <span className="badge badge-arriving-now">🚨 ARRIVING NOW</span>
                        : isArrivingSoon
                          ? <span className="badge badge-arriving-soon">⚡ ARRIVING SOON</span>
                          : <span className="badge badge-upcoming">{t.status}</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function NearbyStationsTab({ nearbyData, nearbyLoading }) {
  const [subTab, setSubTab] = useState('Hadapsar');
  const stations = ['Hadapsar', 'Shivajinagar', 'Ghorpuri'];

  return (
    <div>
      <div className="subtab-bar">
        {stations.map(s => (
          <button
            key={s}
            className={`subtab-btn ${subTab === s ? 'subtab-active' : ''}`}
            onClick={() => setSubTab(s)}
          >
            {STATION_CONFIG[s].emoji} {s}
          </button>
        ))}
      </div>

      {nearbyLoading ? (
        <div className="spinner" />
      ) : (
        <NearbyStationPanel
          stationName={subTab}
          trains={nearbyData[subTab] || []}
        />
      )}
    </div>
  );
}

// --- ROOT APP ---

function App({ loggedInUser, onLogout }) {
  const [activeTab, setActiveTab] = useState('pune');
  const [schedule, setSchedule] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [nearbyData, setNearbyData] = useState({});
  const [nearbyLoading, setNearbyLoading] = useState(true);

  const [newTrain, setNewTrain] = useState({
    number: '', name: '', time: '', type: 'Through', route: 'Solapur', force_platform: ''
  });

  const fetchSchedule = () => {
    fetch('http://127.0.0.1:5000/api/schedule')
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(data => {
        // Sort chronologically with midnight wrap
        const nowMins = new Date().getHours() * 60 + new Date().getMinutes();
        const toMins = (timeStr) => {
          if (!timeStr) return 9999;
          const [h, m] = timeStr.split(':').map(Number);
          let mins = h * 60 + m;
          if (mins < nowMins - 60) mins += 1440; // next-day train
          return mins;
        };
        data.sort((a, b) => toMins(a.arrival) - toMins(b.arrival));
        setSchedule(data);
        setLoading(false);
        setError(null);
      })
      .catch(() => { setLoading(false); setError('Failed to load schedule. Check that the backend is running.'); });
  };

  const fetchNearby = () => {
    fetch('http://127.0.0.1:5000/api/nearby-stations')
      .then(r => r.json())
      .then(data => { setNearbyData(data); setNearbyLoading(false); })
      .catch(() => setNearbyLoading(false));
  };

  useEffect(() => {
    fetchSchedule();
    fetchNearby();
    const i1 = setInterval(fetchSchedule, 5000);
    const i2 = setInterval(fetchNearby, 3000); // poll nearby more often for "ARRIVING NOW"
    return () => { clearInterval(i1); clearInterval(i2); };
  }, []);

  const handleAddTrain = () => {
    if (!newTrain.number || !newTrain.name || !newTrain.time) return alert('Fill all fields');
    fetch('http://127.0.0.1:5000/api/add-train', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newTrain),
    }).then(() => {
      fetchSchedule();
      setNewTrain({ ...newTrain, number: '', name: '', time: '', force_platform: '' });
    });
  };

  const handleDelete = (trainNo) => {
    setSchedule(prev => prev.filter(t => t.train_no !== trainNo));
    fetch(`http://127.0.0.1:5000/api/delete-train/${trainNo}`, { method: 'DELETE' })
      .then(() => { fetchSchedule(); fetchNearby(); })
      .catch(() => { fetchSchedule(); fetchNearby(); });
  };

  return (
    <div className="App">
      {/* ── HUD HEADER BAR ── */}
      <div className="hud-header">
        <div className="hud-left">
          <span className="hud-logo">🚂</span>
          <div className="hud-logo-text">
            <span className="hud-org">Indian Railways</span>
            <span className="hud-zone">Central Railway · Pune Division</span>
          </div>
        </div>
        <div className="hud-center">
          <span className="hud-station-name">🏛️ Pune Junction</span>
          <span className="hud-station-sub">Station Control Dashboard</span>
        </div>
        <div className="hud-right">
          <LiveClock />
          {loggedInUser && (
            <div className="hud-user">
              <span className="hud-user-name">👤 {loggedInUser}</span>
              <button className="hud-logout" onClick={onLogout}>Logout</button>
            </div>
          )}
        </div>
      </div>

      {/* MAIN TAB BAR */}
      <div className="tab-bar">
        <button className={`tab-btn ${activeTab === 'pune' ? 'tab-active' : ''}`} onClick={() => setActiveTab('pune')}>
          🏛️ Pune Junction
        </button>
        <button className={`tab-btn ${activeTab === 'nearby' ? 'tab-active' : ''}`} onClick={() => setActiveTab('nearby')}>
          📡 Nearby Stations
        </button>
      </div>

      {/* TAB CONTENT */}
      {activeTab === 'pune' ? (
        <PuneJnTab
          schedule={schedule}
          loading={loading}
          error={error}
          newTrain={newTrain}
          setNewTrain={setNewTrain}
          handleAddTrain={handleAddTrain}
          handleDelete={handleDelete}
        />
      ) : (
        <NearbyStationsTab nearbyData={nearbyData} nearbyLoading={nearbyLoading} />
      )}
    </div>
  );
}

export default App;
