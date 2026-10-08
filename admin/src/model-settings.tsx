import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ApiError, listConfigurationAuditEvents, listProviders, listWorkflowModels, saveProvider, saveWorkflowModel,
} from "./api";

export function ModelSettingsPage() {
  const queryClient = useQueryClient();
  const [token, setToken] = useState("");
  const providers = useQuery({ queryKey: ["providers"], queryFn: listProviders });
  const assignments = useQuery({ queryKey: ["workflow-models"], queryFn: listWorkflowModels });
  const audit = useQuery({ queryKey: ["configuration-audit"], queryFn: listConfigurationAuditEvents });
  const selected = assignments.data?.find((item) => item.workflow_id === "content");
  const [providerId, setProviderId] = useState("openai");
  const [displayName, setDisplayName] = useState("OpenAI");
  const [credentialReference, setCredentialReference] = useState("env:OPENAI_API_KEY");
  const [enabled, setEnabled] = useState(true);
  const [model, setModel] = useState("gpt-4.1-mini");
  const providerOptions = useMemo(() => providers.data || [], [providers.data]);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["providers"] })
    .then(() => queryClient.invalidateQueries({ queryKey: ["workflow-models"] }))
    .then(() => queryClient.invalidateQueries({ queryKey: ["configuration-audit"] }));
  const providerMutation = useMutation({ mutationFn: () => saveProvider(providerId, { display_name: displayName, credential_reference: credentialReference, enabled }, token), onSuccess: refresh });
  const modelMutation = useMutation({ mutationFn: () => saveWorkflowModel("content", { provider_id: providerId, model }, token), onSuccess: refresh });
  const error = providerMutation.error || modelMutation.error;

  const submitProvider = (event: FormEvent) => { event.preventDefault(); providerMutation.mutate(); };
  const submitModel = (event: FormEvent) => { event.preventDefault(); modelMutation.mutate(); };

  return <div className="page"><header className="page-header"><span className="eyebrow">Phase 4.3</span><h1>Model settings</h1><p>Provider records contain a credential reference only. Provider keys never enter this browser, database, or audit history.</p></header>
    <section className="settings-notice"><strong>Local write authorization</strong><span>The control token is kept only in this page’s memory and is sent as a request header for an explicit save.</span><label>Control token<input type="password" value={token} onChange={(event) => setToken(event.target.value)} autoComplete="off" /></label></section>
    {error && <div className="error"><strong>Configuration was not saved.</strong><span>{error instanceof ApiError ? error.message : "Check the local control token and fields."}</span></div>}
    <div className="settings-grid"><form className="settings-form" onSubmit={submitProvider}><div><span className="eyebrow">Provider</span><h2>OpenAI Responses</h2></div><label>Provider ID<input value={providerId} onChange={(event) => setProviderId(event.target.value)} /></label><label>Display name<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label><label>Credential reference<input value={credentialReference} onChange={(event) => setCredentialReference(event.target.value)} /></label><label className="checkbox"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /> Enabled</label><button disabled={!token || providerMutation.isPending} type="submit">{providerMutation.isPending ? "Saving…" : "Save provider"}</button></form>
      <form className="settings-form" onSubmit={submitModel}><div><span className="eyebrow">Workflow assignment</span><h2>Content workflow</h2></div><label>Provider<select value={providerId} onChange={(event) => setProviderId(event.target.value)}>{providerOptions.length ? providerOptions.map((item) => <option key={item.provider_id} value={item.provider_id}>{item.display_name} ({item.provider_id})</option>) : <option value={providerId}>{providerId}</option>}</select></label><label>Model<input value={model} onChange={(event) => setModel(event.target.value)} /></label><p className="form-note">Current assignment: {selected ? `${selected.provider_id} / ${selected.model}` : "not configured"}.</p><button disabled={!token || modelMutation.isPending} type="submit">{modelMutation.isPending ? "Saving…" : "Save assignment"}</button></form></div>
    <section className="section-block audit"><div className="section-heading"><div><span className="eyebrow">Audit history</span><h2>Configuration changes</h2></div></div>{audit.data?.length ? <div className="table-wrap"><table><thead><tr><th>When</th><th>Change</th><th>Resource</th><th>Actor</th></tr></thead><tbody>{audit.data.map((event) => <tr key={event.sequence}><td>{formatDate(event.occurred_at)}</td><td>{event.summary}</td><td>{event.resource_type}: {event.resource_id}</td><td>{event.actor}</td></tr>)}</tbody></table></div> : <div className="empty">No configuration changes have been recorded.</div>}</section>
  </div>;
}

function formatDate(value: string) { return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
