import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, BookOpen, ChevronRight, Database, LayoutDashboard, ListFilter, Workflow } from "lucide-react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";

import { ApiError, getRun, listRuns, listWorkflows, type RunListItem } from "./api";

const statuses = ["", "pending", "running", "completed", "blocked", "failed", "awaiting_approval"];
const docsUrl = import.meta.env.VITE_DOCS_URL || "http://localhost:3000";

export function App() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" to="/">
          <span className="brand-mark"><Activity size={18} /></span>
          <span>Personal AI Agent</span>
        </Link>
        <nav>
          <NavLink to="/" icon={<LayoutDashboard size={17} />} label="Overview" />
          <NavLink to="/runs" icon={<Database size={17} />} label="Runs" />
          <NavLink to="/workflows" icon={<Workflow size={17} />} label="Workflows" />
        </nav>
        <div className="sidebar-note">
          <span className="eyebrow">Control plane</span>
          <p>Read-only runtime history. Changes and publishing remain outside this interface.</p>
          <a href={docsUrl} target="_blank" rel="noreferrer"><BookOpen size={14} /> Learning guides</a>
        </div>
      </aside>
      <main className="main-content">
        <Routes>
          <Route path="/" element={<OverviewPage />} />
          <Route path="/runs" element={<RunsPage />} />
          <Route path="/runs/:runId" element={<RunDetailPage />} />
          <Route path="/workflows" element={<WorkflowsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

function NavLink({ to, icon, label }: { to: string; icon: ReactNode; label: string }) {
  const location = useLocation();
  const active = to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);
  return <Link to={to} className={active ? "nav-link active" : "nav-link"}>{icon}<span>{label}</span></Link>;
}

function OverviewPage() {
  const runs = useQuery({ queryKey: ["runs", "overview"], queryFn: () => listRuns({ limit: 25 }) });
  const summary = useMemo(() => {
    const items = runs.data?.items || [];
    return [
      { label: "Recent runs", value: items.length, detail: "Current history page" },
      { label: "Needs attention", value: items.filter((run) => ["blocked", "failed"].includes(run.status)).length, detail: "Blocked or failed" },
      { label: "In progress", value: items.filter((run) => ["pending", "running", "awaiting_approval"].includes(run.status)).length, detail: "Current history page" },
    ];
  }, [runs.data]);
  return <Page title="Runtime overview" description="A factual view of the run history currently available from the API.">
    <QueryState query={runs}>
      <div className="metric-grid">{summary.map((metric) => <section className="metric" key={metric.label}><span>{metric.label}</span><strong>{metric.value}</strong><small>{metric.detail}</small></section>)}</div>
      <section className="section-block"><div className="section-heading"><div><span className="eyebrow">Recent activity</span><h2>Latest runs</h2></div><Link className="text-link" to="/runs">All runs <ChevronRight size={15} /></Link></div><RunTable items={runs.data?.items || []} compact /></section>
    </QueryState>
  </Page>;
}

function RunsPage() {
  const [status, setStatus] = useState("");
  const [cursor, setCursor] = useState<string | undefined>();
  const runs = useQuery({ queryKey: ["runs", status, cursor], queryFn: () => listRuns({ status: status || undefined, cursor }) });
  return <Page title="Runs" description="Durable workflow history. Filters and pagination are served by the runtime API.">
    <div className="toolbar"><label><ListFilter size={15} /> Status<select value={status} onChange={(event) => { setStatus(event.target.value); setCursor(undefined); }}>{statuses.map((option) => <option key={option} value={option}>{option || "All statuses"}</option>)}</select></label></div>
    <QueryState query={runs}>
      <RunTable items={runs.data?.items || []} />
      <div className="pagination"><span>{runs.data?.next_cursor ? "More history is available." : "End of available history."}</span>{runs.data?.next_cursor && <button onClick={() => setCursor(runs.data?.next_cursor || undefined)}>Load more</button>}</div>
    </QueryState>
  </Page>;
}

function RunDetailPage() {
  const { runId = "" } = useParams();
  const navigate = useNavigate();
  const run = useQuery({ queryKey: ["run", runId], queryFn: () => getRun(runId) });
  return <Page title="Run detail" description="Current checkpoint and immutable transition history."><button className="back-link" onClick={() => navigate("/runs")}>Back to runs</button><QueryState query={run}>
    {run.data && <div className="detail-layout"><section><div className="detail-title"><div><span className="eyebrow">{run.data.workflow}</span><h2>{run.data.subject}</h2><code>{run.data.run_id}</code></div><StatusBadge status={run.data.status} /></div><dl className="details"><div><dt>Created</dt><dd>{formatDate(run.data.created_at)}</dd></div><div><dt>Updated</dt><dd>{formatDate(run.data.updated_at)}</dd></div><div><dt>Current step</dt><dd>{run.data.current_step || "Finished"}</dd></div></dl><h3>Stages</h3><div className="stage-list">{run.data.stages.map((stage) => <article key={stage.name} className="stage"><div><strong>{stage.name}</strong><span>{stage.artifact_name}</span></div><div><StatusBadge status={stage.status} /><small>{stage.attempts} attempt{stage.attempts === 1 ? "" : "s"}</small></div>{stage.message && <p>{stage.message}</p>}</article>)}</div></section><section className="timeline"><span className="eyebrow">Timeline</span><h3>Execution events</h3>{run.data.events.map((event) => <article key={event.sequence} className="event"><span className="event-dot"/><div><strong>{event.event_type}</strong><small>{formatDate(event.occurred_at)}{event.stage_name ? ` · ${event.stage_name}` : ""}</small></div></article>)}</section></div>}
  </QueryState></Page>;
}

function WorkflowsPage() {
  const workflows = useQuery({ queryKey: ["workflows"], queryFn: listWorkflows });
  return <Page title="Workflows" description="The fixed runtime workflow currently exposed by the API."><QueryState query={workflows}>{workflows.data?.map((workflow) => <section className="workflow-card" key={workflow.workflow_id}><div><span className="eyebrow">{workflow.workflow_id}</span><h2>{workflow.display_name}</h2></div><ol>{workflow.stages.map((stage) => <li key={stage.name}><span>{stage.name}</span><small>{stage.capability} · {stage.artifact_name}</small></li>)}</ol></section>)}</QueryState></Page>;
}

function RunTable({ items, compact = false }: { items: RunListItem[]; compact?: boolean }) {
  if (!items.length) return <div className="empty">No runs match the current view.</div>;
  return <div className="table-wrap"><table><thead><tr><th>Run</th><th>Status</th><th>Created</th>{!compact && <><th>Current step</th><th>Attempts</th></>}<th /></tr></thead><tbody>{items.map((run) => <tr key={run.run_id}><td><Link to={`/runs/${run.run_id}`}><strong>{run.run_id}</strong><span>{run.model || "No model metadata"}</span></Link></td><td><StatusBadge status={run.status} /></td><td>{formatDate(run.created_at)}</td>{!compact && <><td>{run.current_step || "Finished"}</td><td>{run.stage_attempt_count}</td></>}<td><Link className="row-link" to={`/runs/${run.run_id}`} aria-label={`Open ${run.run_id}`}><ChevronRight size={17} /></Link></td></tr>)}</tbody></table></div>;
}

function QueryState({ query, children }: { query: { isLoading: boolean; error: Error | null }; children: ReactNode }) {
  if (query.isLoading) return <div className="loading">Loading runtime data…</div>;
  if (query.error) return <div className="error"><strong>Unable to load this view.</strong><span>{query.error instanceof ApiError ? query.error.message : "Check that the API is running and ready."}</span></div>;
  return <>{children}</>;
}

function Page({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return <div className="page"><header className="page-header"><span className="eyebrow">Personal AI Agent</span><h1>{title}</h1><p>{description}</p></header>{children}</div>;
}

function StatusBadge({ status }: { status: string }) { return <span className={`status status-${status}`}>{status.replaceAll("_", " ")}</span>; }
function formatDate(value: string) { return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
