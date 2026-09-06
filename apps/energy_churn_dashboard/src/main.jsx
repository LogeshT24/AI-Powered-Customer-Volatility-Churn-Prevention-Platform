import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import "./orchestration.css";

const API = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:5000";
const tone = (band) => ({ Stable: "stable", Watch: "watch", High: "high", Critical: "critical" }[band] || "watch");

function App() {
  const [dashboard, setDashboard] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [market, setMarket] = useState(null);
  const [selected, setSelected] = useState(null);
  const [view, setView] = useState("command");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [dash, people, marketData] = await Promise.all([fetch(`${API}/api/dashboard`), fetch(`${API}/api/customers`), fetch(`${API}/api/market`)]);
      setDashboard(await dash.json()); setCustomers(await people.json()); setMarket(await marketData.json());
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);
  const openCustomer = async (id) => setSelected(await (await fetch(`${API}/api/customers/${id}`)).json());
  const updateStatus = async (status) => {
    await fetch(`${API}/api/interventions/${selected.customer_id}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }) });
    setSelected({ ...selected, intervention_status: status }); load();
  };

  if (loading && !dashboard) return <main className="loading">Loading Retention Command Centre…</main>;
  return <main>
    <aside><div className="brand"><span>◈</span> ENERGY PULSE<br/><small>RETENTION INTELLIGENCE</small></div>
      <button className={view === "command" ? "active" : ""} onClick={() => setView("command")}>▦ Command centre</button>
      <button className={view === "agents" ? "active" : ""} onClick={() => setView("agents")}>◌ Agent workspace</button>
      <div className="aside-footer"><br/><span>● SYNTHETIC DATA ONLY</span></div>
    </aside>
    <section className="content">
      <header><div><p className="eyebrow">CUSTOMER RETENTION / UK ENERGY</p><h1>{view === "command" ? "Retention command centre" : "Agent workspace"}</h1></div><button className="refresh" onClick={load}>↻ Refresh intelligence</button></header>
      {view === "command" ? <>
        <div className="banner"><b>AI decision support</b><span>All pricing, payment support, and customer contact actions require human approval.</span></div>
        <div className="metrics"><Metric label="Customers assessed" value={dashboard.portfolio_size}/><Metric label="Average volatility" value={`${dashboard.average_volatility}/100`}/><Metric label="High / critical" value={dashboard.critical_or_high} alert/><Metric label="Interventions pending" value={dashboard.interventions_pending}/></div>
        <div className="grid top-grid"><section className="panel"><h2>Risk distribution</h2><div className="distribution">{Object.entries(dashboard.distribution).map(([band, count]) => <div key={band}><div className="bar-wrap"><i className={tone(band)} style={{height: `${Math.max(12, count * 32)}px`}}/></div><b>{count}</b><small>{band}</small></div>)}</div></section>
          <section className="panel market"><div><p className="eyebrow">MARKET INTELLIGENCE</p><h2>Electricity price signal</h2><strong>${market?.price_eur_mwh ?? "—"}<small> / MWh</small></strong><p>{market?.source}</p></div><div className={`market-status ${market?.source_mode}`}>{market?.source_mode === "live" ? "LIVE" : "FALLBACK"}<small>{market?.retrieved_at?.slice(0, 16).replace("T", " ")}</small></div></section>
        </div>
        <section className="panel table-panel"><div className="panel-head"><div><p className="eyebrow">PRIORITY QUEUE</p><h2>Customers needing attention</h2></div><span>{customers.length} accounts</span></div><table><thead><tr><th>Customer</th><th>Risk</th><th>Volatility</th><th>Churn baseline</th><th>Primary driver</th><th>Recommended next action</th></tr></thead><tbody>{customers.map((customer) => <tr key={customer.customer_id} onClick={() => openCustomer(customer.customer_id)}><td><b>{customer.customer_id}</b></td><td><span className={`pill ${tone(customer.risk_band)}`}>{customer.risk_band}</span></td><td><b>{customer.volatility_score}</b>/100</td><td>{Math.round(customer.baseline_churn_probability * 100)}%</td><td>{Object.entries(customer.drivers).sort((a,b) => b[1]-a[1])[0][0].replaceAll("_", " ")}</td><td>{customer.intervention.recommended_action}</td></tr>)}</tbody></table></section>
      </> : <AgentWorkspace customers={customers} openCustomer={openCustomer}/>} 
    </section>
    {selected && <CustomerDrawer customer={selected} close={() => setSelected(null)} updateStatus={updateStatus}/>} 
  </main>;
}

function Metric({label, value, alert}) { return <section className={`metric ${alert ? "metric-alert" : ""}`}><p>{label}</p><strong>{value}</strong><small>Current demo portfolio</small></section>; }
function AgentWorkspace({customers, openCustomer}) {
  const [id, setId] = useState("C-1002");
  const [question, setQuestion] = useState("Give me details of C-1002");
  const [answer, setAnswer] = useState("");
  const [chatError, setChatError] = useState("");
  const [fallbackReason, setFallbackReason] = useState("");
  const [asking, setAsking] = useState(false);
  const current = customers.find(c => c.customer_id === id);
  const agents = [["01", "Customer Risk Agent", "Customer 360 + deterministic volatility score"], ["02", "Complaint Resolution Agent", "SLA, repeat complaints and escalation health"], ["03", "Sentiment Agent", "Feedback, NPS and CSAT interpretation"], ["04", "Market Intelligence Agent", "Live market-pressure context and source state"], ["05", "Intervention Agent", "Policy-grounded next-best human action"], ["06", "Governance Agent", "Approval, policy and customer-safety checks"]];
  const selectCustomer = (customerId) => { setId(customerId); setQuestion(`Give me details of ${customerId}`); };
  const localFallback = () => {
    if (!current) return "The local dashboard data is unavailable. Refresh the dashboard and try again.";
    const [driver, driverScore] = Object.entries(current.drivers).sort((a, b) => b[1] - a[1])[0];
    return `Assessment for ${current.customer_id}: ${current.risk_band} risk, ${current.volatility_score}/100 volatility and ${Math.round(current.baseline_churn_probability * 100)}% baseline churn probability. Primary driver: ${driver.replaceAll("_", " ")} (${driverScore}/100). Recommended human-approved action: ${current.intervention.recommended_action}.`;
  };
  const askAgent = async (event) => {
    event.preventDefault(); setAsking(true); setAnswer(""); setChatError(""); setFallbackReason("");
    try {
      const response = await fetch(`${API}/api/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message: question, customer_id: id }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "The Energy Churn agent could not answer.");
      setAnswer(payload.answer);
      if (payload.fallback) setFallbackReason(payload.fallback_reason);
    } catch (error) { setAnswer(localFallback()); setFallbackReason("The dashboard could not reach the local agent service."); setChatError(error.message); } finally { setAsking(false); }
  };
  return <div className="agent-grid"><section className="panel orchestration"><p className="eyebrow">NEURO SAN ORCHESTRATION</p><h2>Multi-agent retention workflow</h2><div className="flow-grid">{agents.map(([number, name, description]) => <article key={number}><span>{number}</span><b>{name}</b><small>{description}</small></article>)}</div></section><section className="panel prompt"><p className="eyebrow">ASSESSMENT CONSOLE</p><h2>Assess a customer</h2><select value={id} onChange={event => selectCustomer(event.target.value)}>{customers.map(c => <option key={c.customer_id}>{c.customer_id}</option>)}</select><button className="assess" onClick={() => openCustomer(id)}>View deterministic assessment →</button>{current && <div className="result"><span className={`pill ${tone(current.risk_band)}`}>{current.risk_band}</span><b>{current.volatility_score}/100 volatility</b><p>{current.intervention.recommended_action}</p></div>}<form className="agent-chat" onSubmit={askAgent}><p className="eyebrow">ASK ENERGY AGENT</p><label htmlFor="agent-question">Question for the local Neuro SAN network</label><textarea id="agent-question" value={question} onChange={event => setQuestion(event.target.value)} required/><button className="assess" disabled={asking}>{asking ? "Asking agent…" : "Ask Energy Agent →"}</button>{answer && <div className="agent-answer"><b>{fallbackReason ? "Deterministic assessment" : "Energy agent"}</b><p>{answer}</p></div>}{fallbackReason && <div className="agent-fallback">AI unavailable: {fallbackReason} Showing verified local dashboard data instead.</div>}{chatError && <div className="agent-error">Connection detail: {chatError}</div>}</form></section></div>;
}
function CustomerDrawer({customer, close, updateStatus}) { return <div className="drawer-backdrop" onClick={close}><section className="drawer" onClick={e => e.stopPropagation()}><button className="close" onClick={close}>×</button><p className="eyebrow">CUSTOMER RISK BRIEF / {customer.customer_id}</p><div className="drawer-title"><h2>{customer.risk_band} retention risk</h2><span className={`score ${tone(customer.risk_band)}`}>{customer.volatility_score}</span></div><p className="formula">Volatility score · deterministic decision support</p><div className="driver-list">{Object.entries(customer.drivers).map(([name, value]) => <div key={name}><label>{name.replaceAll("_", " ")}<b>{value}</b></label><i><em style={{width: `${value}%`}}/></i></div>)}</div><section className="recommend"><p className="eyebrow">RECOMMENDED NEXT ACTION</p><h3>{customer.intervention.recommended_action}</h3><p>{customer.intervention.guardrail}</p><div className="citations">{customer.intervention.policy_citations.map(policy => <span key={policy.document}>⌁ {policy.document} · {policy.version}</span>)}</div></section><section className="sentiment"><b>Sentiment: {customer.sentiment.label}</b><span>Urgency: {customer.sentiment.urgency}</span></section><div className="actions"><button onClick={() => updateStatus("approved")}>Mark human-approved</button><button className="secondary" onClick={() => updateStatus("declined")}>Decline</button></div></section></div>; }
createRoot(document.getElementById("root")).render(<App/>);
