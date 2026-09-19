import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import { ScheduleChatProvider, useScheduleChat } from "../chat/ScheduleChatContext";
import ScheduleChatDock from "../components/chatbot/ScheduleChatDock";
import * as chatApi from "../services/chatApi";

describe("ScheduleChatDock Component (Portability & UX)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders launcher floating button without requiring ScheduleDashboard", () => {
    render(
      <ScheduleChatProvider>
        <ScheduleChatDock />
      </ScheduleChatProvider>
    );

    const launcherBtn = screen.getByRole("button", { name: /explain this schedule/i });
    expect(launcherBtn).toBeDefined();
  });

  it("opens panel when launcher is clicked and shows context bar", () => {
    render(
      <ScheduleChatProvider initialContext={{ scenario: "A", runId: "sample_run" }}>
        <ScheduleChatDock />
      </ScheduleChatProvider>
    );

    const launcherBtn = screen.getByRole("button", { name: /explain this schedule/i });
    fireEvent.click(launcherBtn);

    expect(screen.getByRole("dialog", { name: /schedule explainer/i })).toBeDefined();
    expect(screen.getByText(/Scenario A/i)).toBeDefined();
    expect(screen.getAllByText(/Mock/i).length).toBeGreaterThan(0);
  });

  it("closes panel via the close button", () => {
    render(
      <ScheduleChatProvider>
        <ScheduleChatDock />
      </ScheduleChatProvider>
    );

    fireEvent.click(screen.getByRole("button", { name: /explain this schedule/i }));
    expect(screen.getByRole("dialog", { name: /schedule explainer/i })).toBeDefined();

    const closeBtn = screen.getByRole("button", { name: /close explainer/i });
    fireEvent.click(closeBtn);

    expect(screen.queryByRole("dialog", { name: /schedule explainer/i })).toBeNull();
  });

  it("closes panel when Escape key is pressed", () => {
    render(
      <ScheduleChatProvider>
        <ScheduleChatDock />
      </ScheduleChatProvider>
    );

    fireEvent.click(screen.getByRole("button", { name: /explain this schedule/i }));
    expect(screen.getByRole("dialog", { name: /schedule explainer/i })).toBeDefined();

    fireEvent.keyDown(window, { key: "Escape", code: "Escape" });
    expect(screen.queryByRole("dialog", { name: /schedule explainer/i })).toBeNull();
  });

  it("sends a message and displays answer with evidence accordion", async () => {
    const mockApiResponse = {
      session_id: "test-session-123",
      answer: "A017 is scheduled in week 19 due to capacity constraints.",
      response_mode: "deterministic_fallback",
      citations: [
        {
          evidence_id: "activity:A017",
          classification: "stored_fact",
          entity_type: "activity",
          entity_id: "A017",
          run_id: "sample_run",
          description: "Activity A017 belongs to C003.",
        },
      ],
      uncertainty: ["no_baseline"],
      provenance: {
        provider: "deterministic",
        model: "test",
        prompt_template_version: "v1",
        instance_revision_id: "rev-1",
        run_id: "sample_run",
      },
      tools_used: [],
    };

    vi.spyOn(chatApi, "sendChatMessage").mockResolvedValue(mockApiResponse);

    render(
      <ScheduleChatProvider initialContext={{ selectedActivityId: "A017" }}>
        <ScheduleChatDock />
      </ScheduleChatProvider>
    );

    fireEvent.click(screen.getByRole("button", { name: /explain this schedule/i }));

    const textarea = screen.getByPlaceholderText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: "Why was A017 scheduled in week 19?" } });

    const sendBtn = screen.getByRole("button", { name: /send question/i });
    fireEvent.click(sendBtn);

    expect(screen.getByText("Why was A017 scheduled in week 19?")).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText(/A017 is scheduled in week 19/i)).toBeDefined();
    });

    expect(screen.getByText(/Verified Schedule Facts/i)).toBeDefined();

    // Verify evidence button
    const evidenceBtn = screen.getByRole("button", { name: /evidence & grounding/i });
    expect(evidenceBtn).toBeDefined();
    fireEvent.click(evidenceBtn);

    expect(screen.getByText("Activity A017 belongs to C003.")).toBeDefined();
  });

  it("supports openScheduleChat external trigger with autoPrompt", async () => {
    function ExternalTriggerTestComponent() {
      const { openScheduleChat } = useScheduleChat();
      return (
        <button
          onClick={() =>
            openScheduleChat({
              runId: "run-999",
              activityId: "A059",
              autoPrompt: "Why was A059 moved?",
            })
          }
        >
          Explain A059
        </button>
      );
    }

    vi.spyOn(chatApi, "sendChatMessage").mockResolvedValue({
      session_id: "session-abc",
      answer: "A059 was moved because of workfront limits.",
      response_mode: "gemini",
      citations: [],
      uncertainty: [],
      provenance: {
        provider: "gemini",
        model: "gemini-3.6-flash",
        prompt_template_version: "v1",
        instance_revision_id: "rev-1",
        run_id: "run-999",
      },
      tools_used: ["get_activity"],
    });

    render(
      <ScheduleChatProvider>
        <ExternalTriggerTestComponent />
        <ScheduleChatDock />
      </ScheduleChatProvider>
    );

    fireEvent.click(screen.getByText("Explain A059"));

    expect(screen.getByRole("dialog", { name: /schedule explainer/i })).toBeDefined();
    expect(screen.getByText(/Activity A059/i)).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText("Why was A059 moved?")).toBeDefined();
    });
  });
});
