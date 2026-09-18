import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ErrorBoundary from "../components/ErrorBoundary";

function BrokenComponent() {
  throw new Error("synthetic network-map render failure");
}

describe("ErrorBoundary", () => {
  it("shows a visible diagnostic when a child throws during render", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <ErrorBoundary>
        <BrokenComponent />
      </ErrorBoundary>
    );

    expect(screen.getByRole("alert")).toBeDefined();
    expect(screen.getByText("The network map could not render")).toBeDefined();
    expect(screen.getByTestId("render-error-message").textContent).toContain(
      "synthetic network-map render failure"
    );

    consoleError.mockRestore();
  });
});
