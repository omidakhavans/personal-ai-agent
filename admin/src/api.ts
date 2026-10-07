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

export type RunListItem = z.infer<typeof runListItemSchema>;
export type RunPage = z.infer<typeof runPageSchema>;
export type RunDetail = z.infer<typeof runDetailSchema>;
export type Workflow = z.infer<typeof workflowSchema>;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request(path: string): Promise<unknown> {
  const response = await fetch(`/api/v1${path}`, { headers: { Accept: "application/json" } });
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
