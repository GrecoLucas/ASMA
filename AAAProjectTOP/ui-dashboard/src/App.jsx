import { useState, useEffect, useRef } from 'react'
import './index.css'

function App() {
  const [connected, setConnected] = useState(false);
  const [state, setState] = useState({
    hour: 0,
    price: 0,
    solar_kw: 0,
    battery_soc: 0.3
  });
  
  const [logs, setLogs] = useState([]);
  const [agents, setAgents] = useState({
    solar: { status: 'OFF', power: 0 },
    battery: { status: 'OFF', power: 0, source: 'grid' },
    washing: { status: 'OFF', power: 0 },
    heater: { status: 'OFF', power: 0 }
  });
  const [totalCost, setTotalCost] = useState(0);

  const logsEndRef = useRef(null);

  useEffect(() => {
    let ws = new WebSocket('ws://localhost:8080');
    
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'STATE') {
        setState({
          hour: data.hour,
          price: data.price,
          solar_kw: data.solar_kw,
          battery_soc: data.battery_soc
        });
        
        // Reset agents for new hour to prevent old state bleeding
        setAgents(prev => {
           let np = { ...prev };
           for(let k in np) {
             np[k] = { ...np[k], status: 'OFF', power: 0 };
           }
           np.solar = { status: data.solar_kw > 0 ? 'ON' : 'OFF', power: data.solar_kw };
           return np;
        });

      } else if (data.type === 'ACTION') {
        const p = data.entry;
        setLogs(prev => [...prev, p]);
        
        if (p.running) {
          setTotalCost(prev => prev + p.cost_eur);
          setAgents(prev => ({
            ...prev,
            [p.agent]: {
              status: 'ON',
              power: p.power_kw,
              source: p.source,
              cost: p.cost_eur,
              note: p.note
            }
          }));
        } else {
            setAgents(prev => ({
                ...prev,
                [p.agent]: {
                  status: 'OFF',
                  power: 0,
                  note: p.note
                }
              }));
        }
      }
    };

    return () => ws.close();
  }, []);

  useEffect(() => {
    if (logsEndRef.current) {
        logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  const formatHour = (h) => `${h.toString().padStart(2, '0')}:00`;
  const formatSoc = (soc) => (soc * 100).toFixed(1);

  const getPriceClass = (price) => {
      if (price <= 0.10) return 'price-cheap';
      if (price > 0.17) return 'price-expensive';
      return 'price-medium';
  };

  const getPriceLabel = (price) => {
      if (price <= 0.10) return 'CHEAP';
      if (price > 0.17) return 'PEAK';
      return 'NORMAL';
  };

  return (
    <>
      <div className="bg-decor"></div>
      <div className="dashboard-container">
        
        <header>
          <h1>🏠 Smart Home Simulation</h1>
          <div className="status-badge">
            <div className={`pulse ${!connected ? 'error' : ''}`}></div>
            {connected ? 'Live - Connected via WebSocket' : 'Waiting for Simulation (python main.py)...'}
          </div>
        </header>

        <section className="global-stats">
          <div className="glass-panel">
            <div className="stat-item">
              <h3>Time</h3>
              <div className="value">
                {formatHour(state.hour)}
              </div>
            </div>
          </div>
          <div className="glass-panel">
            <div className="stat-item">
              <h3>Grid Price</h3>
              <div className="value">
                 {state.price.toFixed(3)}
                 <span className="unit">€/kWh</span>
                 <span className={`price-label ${getPriceClass(state.price)}`}>{getPriceLabel(state.price)}</span>
              </div>
            </div>
          </div>
          <div className="glass-panel">
            <div className="stat-item">
              <h3>Total Cost</h3>
              <div className="value" style={{ color: '#facc15' }}>
                {totalCost.toFixed(4)}
                <span className="unit">€</span>
              </div>
            </div>
          </div>
        </section>

        <section className="agents-grid">
            
          {/* SOLAR PANEL */}
          <div className="glass-panel">
            <div className="agent-header">
                <div className="agent-title"><span className="icon">☀️</span> Solar Panel</div>
                <div className={`agent-status-label ${agents.solar.status === 'ON' ? 'status-on' : 'status-off'}`}>
                    {agents.solar.status}
                </div>
            </div>
            <div className="value-blocks">
                <div className="v-block">
                    <span className="v-label">Generation</span>
                    <span className="v-value">{agents.solar.power.toFixed(1)} kW</span>
                </div>
            </div>
          </div>

          {/* BATTERY */}
          <div className="glass-panel">
            <div className="agent-header">
                <div className="agent-title"><span className="icon">🔋</span> Battery Storage</div>
                <div className={`agent-status-label ${agents.battery.status === 'ON' ? 'status-on' : 'status-off'}`}>
                    {agents.battery.status === 'ON' ? 'ACTIVE' : 'IDLE'}
                </div>
            </div>
            <div className="value-blocks">
                <div className="v-block">
                    <span className="v-label">State of Charge (SoC)</span>
                    <span className="v-value">{formatSoc(state.battery_soc)}%</span>
                </div>
                <div className="battery-bar">
                    <div className="battery-fill" style={{ width: `${formatSoc(state.battery_soc)}%` }}></div>
                </div>
                {agents.battery.status === 'ON' && (
                    <div className="v-block" style={{ marginTop: '8px' }}>
                        <span className="v-label">Power ({agents.battery.source})</span>
                        <span className="v-value" style={{ color: '#5e6ad2' }}>{agents.battery.power.toFixed(2)} kW</span>
                    </div>
                )}
            </div>
          </div>

          {/* HEATER */}
          <div className="glass-panel">
            <div className="agent-header">
                <div className="agent-title"><span className="icon">🌡️</span> Heater</div>
                <div className={`agent-status-label ${agents.heater.status === 'ON' ? 'status-on' : 'status-off'}`}>
                    {agents.heater.status}
                </div>
            </div>
            <div className="value-blocks">
                <div className="v-block">
                    <span className="v-label">Consumption</span>
                    <span className="v-value">{agents.heater.power.toFixed(2)} kW</span>
                </div>
                <div className="v-block">
                    <span className="v-label">Status</span>
                    <span className="v-value">{agents.heater.status === 'ON' ? 'Heating' : 'Coasting'}</span>
                </div>
                <div className="v-block" style={{ fontSize: '12px', color: 'rgba(255,255,255,0.5)', marginTop: '8px' }}>
                    {agents.heater.note || 'No notes'}
                </div>
            </div>
          </div>

           {/* WASHING MACHINE */}
           <div className="glass-panel">
            <div className="agent-header">
                <div className="agent-title"><span className="icon">🧺</span> Washing Machine</div>
                <div className={`agent-status-label ${agents.washing.status === 'ON' ? 'status-on' : 'status-off'}`}>
                    {agents.washing.status}
                </div>
            </div>
            <div className="value-blocks">
                <div className="v-block">
                    <span className="v-label">Consumption</span>
                    <span className="v-value">{agents.washing.power.toFixed(2)} kW</span>
                </div>
                <div className="v-block">
                    <span className="v-label">Power Source</span>
                    <span className="v-value" style={{ textTransform: 'capitalize' }}>
                         {agents.washing.status === 'ON' ? agents.washing.source : '-'}
                    </span>
                </div>
                <div className="v-block" style={{ fontSize: '12px', color: 'rgba(255,255,255,0.5)', marginTop: '8px' }}>
                    {agents.washing.note || 'Idle'}
                </div>
            </div>
          </div>

        </section>

        {/* LOG SECTION */}
        <section className="glass-panel action-log">
            <h3 style={{ marginBottom: '16px', fontSize: '16px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '12px' }}>Simulation Log</h3>
            {logs.length === 0 ? <p style={{ color: 'rgba(255,255,255,0.5)' }}>Awaiting events...</p> : null}
            
            <div style={{ display: 'flex', flexDirection: 'column' }}>
               {logs.map((log, idx) => (
                   <div key={idx} className="action-item">
                       <span className="action-time">[{formatHour(log.hour)}]</span>
                       <span className="action-agent">{log.agent}</span>
                       <span className="action-power">{log.running ? log.power_kw.toFixed(1) + 'kW' : 'OFF'}</span>
                       <span className="action-note">{log.note} {log.running ? `(via ${log.source})` : ''}</span>
                       <span className="action-cost">{log.running && log.cost_eur > 0 ? `+€${log.cost_eur.toFixed(4)}` : ''}</span>
                   </div>
               ))}
               <div ref={logsEndRef} />
            </div>
        </section>

      </div>
    </>
  )
}

export default App
