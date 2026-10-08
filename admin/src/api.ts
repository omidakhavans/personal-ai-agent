import { z } from "zod";

const dateTime = z.string().datetime({ offset: true });

const eventSchema = z.object({
  sequence: z.number().int(),
  event_type: z.string(),
  occurred_at: dateTime,
  stage_name: z.string().nullable(),
  schema_version: z.number().int(),
  payload: z.record(z.unknown()),
});

const stageSchema = z.object({
  name: z.string(),
  status: z.string(),
  artifact_name: z.string(),
  attempts: z.number().int(),
  started_at: dateTime.nullable(),
  finished_at: dateTime.nullable(),
  message: z.string(),
});

export const runListItemSchema = z.object({
  run_id: z.string(),
  workflow: z.string(),
  status: z.string(),
  created_at: dateTime,
  started_at: dateTime.nullable(),
  finished_at: dateTime.nullable(),
  duration_seconds: z.number().nullable(),
  current_step: z.string().nullable(),
  stage_attempt_count: z.number().int(),
  error_summary: z.string().nullable(),
  model: z.string().nullable(),
});

const runPageSchema = z.object({
  items: z.array(runListItemSchema),
  next_cursor: z.string().nullable(),
});

const runDetailSchema = z.object({
  run_id: z.string(),
  workflow: z.string(),
  subject: z.string(),
  status: z.string(),
  created_at: dateTime,
  updated_at: dateTime,
  current_step: z.string().nullable(),
  input_summary: z.record(z.unknown()),
  stages: z.array(stageSchema),
  events: z.array(eventSchema),
});

const workflowSchema = z.object({
  workflow_id: z.string(),
  display_name: z.string(),
  stages: z.array(
    z.object({ name: z.string(), artifact_name: z.string(), capability: z.string() }),
  ),
});

const workflowListSchema = z.object({ items: z.array(workflowSchema) });

const providerSchema = z.object({
  provider_id: z.string(), display_name: z.string(), provider_type: z.literal("openai_responses"),
  credential_reference: z.string(), enabled: z.boolean(), created_at: dateTime, updated_at: dateTime,
});
const workflowModelSchema = z.object({ workflow_id: z.string(), provider_id: z.string(), model: z.string(), updated_at: dateTime });
const auditEventSchema = z.object({
  sequence: z.number().int(), action: z.string(), resource_type: z.string(), resource_id: z.string(),
  actor: z.string(), occurred_at: dateTime, summary: z.string(),
});

export type RunListItem = z.infer<typeof runListItemSchema>;
export type RunPage = z.infer<typeof runPageSchema>;
export type RunDetail = z.infer<typeof runDetailSchema>;
export type Workflow = z.infer<typeof workflowSchema>;
export type ProviderConfiguration = z.infer<typeof providerSchema>;
export type WorkflowModelConfiguration = z.infer<typeof workflowModelSchema>;
export type ConfigurationAuditEvent = z.infer<typeof auditEventSchema>;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request(path: string, init: RequestInit = {}): Promise<unknown> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers: { Accept: "application/json", ...init.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { message?: string } | null;
    throw new ApiError(response.status, body?.message || "The control plane could not load this data.");
  }
  return response.json();
}

export async function listRuns(params: { status?: string; cursor?: string; limit?: number } = {}): Promise<RunPage> {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.cursor) query.set("cursor", params.cursor);
  query.set("limit", String(params.limit || 25));
  const suffix = query.size ? `?${query.toString()}` : "";
  return runPageSchema.parse(await request(`/runs${suffix}`));
}

export async function getRun(runId: string): Promise<RunDetail> {
  return runDetailSchema.parse(await request(`/runs/${encodeURIComponent(runId)}`));
}

export async function listWorkflows(): Promise<Workflow[]> {
  return workflowListSchema.parse(await request("/workflows")).items;
}

export async function listProviders(): Promise<ProviderConfiguration[]> {
  return z.object({ items: z.array(providerSchema) }).parse(await request("/configuration/providers")).items;
}

export async function listWorkflowModels(): Promise<WorkflowModelConfiguration[]> {
  return z.object({ items: z.array(workflowModelSchema) }).parse(await request("/configuration/workflow-models")).items;
}

export async function listConfigurationAuditEvents(): Promise<ConfigurationAuditEvent[]> {
  return z.object({ items: z.array(auditEventSchema) }).parse(await request("/configuration/audit-events")).items;
}

function authenticatedHeaders(token: string): HeadersInit {
  return { "Content-Type": "application/json", "X-Admin-Token": token };
}

export async function saveProvider(
  providerId: string,
  value: { display_name: string; credential_reference: string; enabled: boolean },
  token: string,
): Promise<ProviderConfiguration> {
  return providerSchema.parse(await request(`/configuration/providers/${encodeURIComponent(providerId)}`, {
    method: "PUT", headers: authenticatedHeaders(token), body: JSON.stringify(value),
  }));
}

export async function saveWorkflowModel(
  workflowId: string, value: { provider_id: string; model: string }, token: string,
): Promise<WorkflowModelConfiguration> {
  return workflowModelSchema.parse(await request(`/configuration/workflow-models/${encodeURIComponent(workflowId)}`, {
    method: "PUT", headers: authenticatedHeaders(token), body: JSON.stringify(value),
  }));
}
