import { describe, expect, it, vi } from "vitest";

import { ApiError, listRuns } from "./api";

describe("listRuns", () => {
  it("requests a cursor and validates a response from the runtime API", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      items: [{ run_id: "run-123", workflow: "content", status: "completed", created_at: "2026-10-07T10:00:00+00:00", started_at: null, finished_at: null, duration_seconds: null, current_step: null, stage_attempt_count: 0, error_summary: null, model: null }],
      next_cursor: null,
    }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await listRuns({ limit: 25, status: "completed" });

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/runs?status=completed&limit=25", expect.anything());
    expect(response.items[0]?.run_id).toBe("run-123");
  });

  it("does not mask an API failure as a successful empty result", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ message: "Service unavailable" }), { status: 503 })));

    await expect(listRuns()).rejects.toMatchObject({ status: 503, message: "Service unavailable" } satisfies Partial<ApiError>);
  });
});
