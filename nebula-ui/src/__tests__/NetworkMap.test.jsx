import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import WeeklyScrubber from "../components/network-map/WeeklyScrubber";
import ScenarioSelector from "../components/network-map/ScenarioSelector";
import LayerControls from "../components/network-map/LayerControls";
import NetworkInspector from "../components/network-map/NetworkInspector";
import ActivityFilter from "../components/network-map/ActivityFilter";

describe("WeeklyScrubber Component", () => {
  it("initializes at Week 1 with Previous disabled", () => {
    const setWeek = vi.fn();
    const togglePlay = vi.fn();

    render(
      <WeeklyScrubber
        week={1}
        setWeek={setWeek}
        horizonWeeks={30}
        startDate="2027-01-04"
        isPlaying={false}
        onTogglePlay={togglePlay}
      />
    );

    expect(screen.getByText("Week 1 / 30")).toBeDefined();
    const prevBtn = screen.getByRole("button", { name: /previous week/i });
    expect(prevBtn.disabled).toBe(true);

    const nextBtn = screen.getByRole("button", { name: /next week/i });
    expect(nextBtn.disabled).toBe(false);
  });

  it("advances week when Next is clicked and decrements on Prev", () => {
    let currentWeek = 5;
    const setWeek = vi.fn((fnOrVal) => {
      currentWeek = typeof fnOrVal === "function" ? fnOrVal(currentWeek) : fnOrVal;
    });
    const togglePlay = vi.fn();

    const { rerender } = render(
      <WeeklyScrubber
        week={currentWeek}
        setWeek={setWeek}
        horizonWeeks={30}
        startDate="2027-01-04"
        isPlaying={false}
        onTogglePlay={togglePlay}
      />
    );

    const nextBtn = screen.getByRole("button", { name: /next week/i });
    fireEvent.click(nextBtn);
    expect(setWeek).toHaveBeenCalled();
    expect(currentWeek).toBe(6);

    rerender(
      <WeeklyScrubber
        week={currentWeek}
        setWeek={setWeek}
        horizonWeeks={30}
        startDate="2027-01-04"
        isPlaying={false}
        onTogglePlay={togglePlay}
      />
    );

    const prevBtn = screen.getByRole("button", { name: /previous week/i });
    fireEvent.click(prevBtn);
    expect(currentWeek).toBe(5);
  });

  it("disables Next at final week (week 30)", () => {
    render(
      <WeeklyScrubber
        week={30}
        setWeek={vi.fn()}
        horizonWeeks={30}
        startDate="2027-01-04"
        isPlaying={false}
        onTogglePlay={vi.fn()}
      />
    );

    const nextBtn = screen.getByRole("button", { name: /next week/i });
    expect(nextBtn.disabled).toBe(true);
  });

  it("toggles play/pause state", () => {
    const togglePlay = vi.fn();
    render(
      <WeeklyScrubber
        week={10}
        setWeek={vi.fn()}
        horizonWeeks={30}
        startDate="2027-01-04"
        isPlaying={true}
        onTogglePlay={togglePlay}
      />
    );

    const pauseBtn = screen.getByRole("button", { name: /pause timeline/i });
    fireEvent.click(pauseBtn);
    expect(togglePlay).toHaveBeenCalled();
  });
});

describe("ScenarioSelector Component", () => {
  it("enables available scenarios and disables mock-unavailable scenarios", () => {
    const scenarios = [
      { scenario: "A", available: true, source: "mock" },
      { scenario: "B", available: false },
      { scenario: "C", available: false },
    ];
    const onSelect = vi.fn();

    render(
      <ScenarioSelector
        scenarios={scenarios}
        selectedScenario="A"
        onSelectScenario={onSelect}
      />
    );

    const btnA = screen.getByRole("button", { name: /select scenario a/i });
    expect(btnA.disabled).toBe(false);

    const btnB = screen.getByRole("button", { name: /scenario b: no mock output/i });
    expect(btnB.disabled).toBe(true);

    const btnC = screen.getByRole("button", { name: /scenario c: no mock output/i });
    expect(btnC.disabled).toBe(true);
  });
});

describe("LayerControls Component", () => {
  it("toggles overlays independently", () => {
    const layers = {
      core: true,
      buffers: true,
      mirrored: false,
      crossLine: true,
      capacity: true,
    };
    const onToggle = vi.fn();

    render(<LayerControls layers={layers} onToggleLayer={onToggle} />);

    const coreCheckbox = screen.getByLabelText(/core work/i);
    expect(coreCheckbox.checked).toBe(true);

    const mirroredCheckbox = screen.getByLabelText(/opposite mirrored/i);
    expect(mirroredCheckbox.checked).toBe(false);

    fireEvent.click(coreCheckbox);
    expect(onToggle).toHaveBeenCalledWith("core");
  });
});

describe("NetworkInspector Component", () => {
  it("displays bound-specific sector inspection with correct location ID and capacity", () => {
    const mockOccupancy = {
      locationOccupancy: {
        "SEC:ALP:H01_H02:EB": {
          locationId: "SEC:ALP:H01_H02:EB",
          supplyCapacity: 2,
          activeActivities: ["A003"],
          coShareGroups: [
            {
              group: "b1",
              activities: ["A003"],
              pmCount: 0,
              pcCount: 0,
              cCount: 1,
              isCompliant: true,
            },
          ],
          occupiedGroupCount: 1,
          peakOccupiedGroupCount: 1,
          capacityExceeded: false,
        },
      },
      protection: { explanations: [] },
    };

    render(
      <NetworkInspector
        selectedEntity={{ type: "sector", id: "SEC:ALP:H01_H02:EB" }}
        occupancy={mockOccupancy}
        currentWeek={12}
        onSelectActivity={vi.fn()}
      />
    );

    expect(screen.getByText("ALP Sector H01_H02 (EB)")).toBeDefined();
    expect(screen.getByText("[1 / 2]")).toBeDefined();
    expect(screen.getByText(/legal mix/i)).toBeDefined();
  });

  it("retains composite line identity for interchange stations", () => {
    render(
      <NetworkInspector
        selectedEntity={{ type: "station", id: "PLAT:ALP:H01:EB" }}
        occupancy={{ locationOccupancy: {}, protection: { explanations: [] } }}
        currentWeek={12}
        onSelectActivity={vi.fn()}
      />
    );

    expect(screen.getByText("ALP Station H01 Platform (EB)")).toBeDefined();
    expect(screen.getByText("ALP • EB")).toBeDefined();
  });
});

describe("ActivityFilter Component", () => {
  it("displays active vs inactive status message for selected activity in current week", () => {
    const activities = [
      {
        activityId: "A074",
        contractNumber: "C013",
        natureOfActivity: "Live",
        activityType: "Rail Grinding",
      },
    ];

    const { rerender } = render(
      <ActivityFilter
        activities={activities}
        selectedActivityId="A074"
        onSelectActivity={vi.fn()}
        activeActivitiesInWeek={["A074"]}
        currentWeek={12}
      />
    );

    expect(screen.getByText("Active W12")).toBeDefined();

    // Rerender with activity not active in week
    rerender(
      <ActivityFilter
        activities={activities}
        selectedActivityId="A074"
        onSelectActivity={vi.fn()}
        activeActivitiesInWeek={[]}
        currentWeek={12}
      />
    );

    expect(screen.getByText("Inactive W12")).toBeDefined();
  });
});
