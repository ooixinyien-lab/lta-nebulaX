import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import WeeklyScrubber from "../components/network-map/WeeklyScrubber";
import ScenarioSelector from "../components/network-map/ScenarioSelector";
import LayerControls from "../components/network-map/LayerControls";
import NetworkInspector from "../components/network-map/NetworkInspector";
import ActivityFilter from "../components/network-map/ActivityFilter";
import WeekStatusBar from "../components/network-map/WeekStatusBar";
import NetworkSvgCanvas from "../components/network-map/NetworkSvgCanvas";

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

  it("allows jumping directly to a week by clicking its indicator dot", () => {
    const setWeek = vi.fn();
    render(
      <WeeklyScrubber
        week={1}
        setWeek={setWeek}
        horizonWeeks={30}
        startDate="2027-01-04"
        isPlaying={false}
        onTogglePlay={vi.fn()}
      />
    );

    const dotWeek15 = screen.getByRole("button", { name: /jump to week 15/i });
    fireEvent.click(dotWeek15);
    expect(setWeek).toHaveBeenCalledWith(15);
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

  it("decomposes station inspection into EB and WB platforms with capacity meters", () => {
    const mockOccupancy = {
      locationOccupancy: {
        "PLAT:ALP:S05:EB": {
          locationId: "PLAT:ALP:S05:EB",
          supplyCapacity: 2,
          activeActivities: ["A005"],
          peakOccupiedGroupCount: 1,
          coShareGroups: [
            { group: "g1", activities: ["A005"], pmCount: 0, pcCount: 0, cCount: 1, isCompliant: true },
          ],
        },
        "PLAT:ALP:S05:WB": {
          locationId: "PLAT:ALP:S05:WB",
          supplyCapacity: 2,
          activeActivities: [],
          peakOccupiedGroupCount: 0,
          coShareGroups: [],
        },
      },
      protection: { explanations: [] },
    };

    render(
      <NetworkInspector
        selectedEntity={{ type: "station", id: "ALP:S05" }}
        occupancy={mockOccupancy}
        currentWeek={12}
        onSelectActivity={vi.fn()}
      />
    );

    expect(screen.getByText(/Station S05 · Line Alpha/i)).toBeDefined();
    expect(screen.getByText(/EB Platform/i)).toBeDefined();
    expect(screen.getByText(/WB Platform/i)).toBeDefined();
  });

  it("calls onClose when close button is clicked", () => {
    const onClose = vi.fn();
    render(
      <NetworkInspector
        selectedEntity={{ type: "station", id: "ALP:S05" }}
        occupancy={{ locationOccupancy: {}, protection: { explanations: [] } }}
        currentWeek={12}
        onClose={onClose}
      />
    );

    const closeBtn = screen.getByRole("button", { name: /close inspector/i });
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalled();
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
        scheduledWeeks: [14, 15],
      },
    ];

    const onJumpToWeek = vi.fn();

    const { rerender } = render(
      <ActivityFilter
        activities={activities}
        selectedActivityId="A074"
        onSelectActivity={vi.fn()}
        activeActivitiesInWeek={["A074"]}
        currentWeek={12}
        onJumpToWeek={onJumpToWeek}
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
        onJumpToWeek={onJumpToWeek}
      />
    );

    expect(screen.getByText("Inactive W12")).toBeDefined();
    const jumpBtn = screen.getByRole("button", { name: /jump to w14/i });
    expect(jumpBtn).toBeDefined();

    fireEvent.click(jumpBtn);
    expect(onJumpToWeek).toHaveBeenCalledWith(14);
  });
});

describe("WeekStatusBar Component", () => {
  it("displays active activities and occupied location counts", () => {
    const mockOccupancy = {
      available: true,
      activeActivities: ["A001", "A002"],
      locationOccupancy: {
        "SEC:ALP:S01_S02:EB": { supplyCapacity: 2, peakOccupiedGroupCount: 1 },
        "SEC:ALP:S02_S03:EB": { supplyCapacity: 2, peakOccupiedGroupCount: 1 },
      },
    };

    render(
      <WeekStatusBar
        week={12}
        startDate="2027-01-04"
        occupancy={mockOccupancy}
        occLoading={false}
      />
    );

    expect(screen.getByText("Week 12")).toBeDefined();
    expect(screen.getByText("2 activities active")).toBeDefined();
    expect(screen.getByText("2 locations occupied")).toBeDefined();
    expect(screen.getByText("Normal operations")).toBeDefined();
  });

  it("displays error banner and triggers onRetry when clicked", () => {
    const onRetry = vi.fn();
    render(
      <WeekStatusBar
        week={12}
        startDate="2027-01-04"
        occError="Network timeout"
        onRetry={onRetry}
      />
    );

    expect(screen.getByText(/failed to load occupancy data/i)).toBeDefined();
    const retryBtn = screen.getByRole("button", { name: /retry/i });
    fireEvent.click(retryBtn);
    expect(onRetry).toHaveBeenCalled();
  });
});

describe("NetworkSvgCanvas Component", () => {
  it("selects an unselected station and deselects it when clicked again", () => {
    const onSelectEntity = vi.fn();
    const setTooltip = vi.fn();
    const layers = { core: true, buffers: true, mirrored: true, crossLine: true, capacity: true };

    const { rerender } = render(
      <NetworkSvgCanvas
        layers={layers}
        occupancy={{ locationOccupancy: {} }}
        activities={[]}
        selectedEntity={null}
        onSelectEntity={onSelectEntity}
        setTooltip={setTooltip}
      />
    );

    // Click S01 station
    const stnBtn = screen.getByRole("button", { name: /ALP Station S01/i });
    fireEvent.click(stnBtn);
    expect(onSelectEntity).toHaveBeenCalledWith({ type: "station", id: "ALP:S01" });

    // Rerender with S01 as selectedEntity
    rerender(
      <NetworkSvgCanvas
        layers={layers}
        occupancy={{ locationOccupancy: {} }}
        activities={[]}
        selectedEntity={{ type: "station", id: "ALP:S01" }}
        onSelectEntity={onSelectEntity}
        setTooltip={setTooltip}
      />
    );

    // Click S01 again -> should deselect (null)
    fireEvent.click(stnBtn);
    expect(onSelectEntity).toHaveBeenCalledWith(null);
  });
});
