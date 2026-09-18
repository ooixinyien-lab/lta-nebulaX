/**
 * Visual coordinates registry exactly calibrated to references/network_diagram.svg
 * viewBox="0 0 1060 380" inside group transform="translate(0, 40)"
 */

export const SVG_TRANSFORM = { x: 0, y: 40 };

export const stationLayout = {
  // ALP Line stations (cy = 104)
  "ALP:S01": { x: 200, y: 104, lineCode: "ALP", stationId: "S01", isInterchange: false },
  "ALP:S02": { x: 270, y: 104, lineCode: "ALP", stationId: "S02", isInterchange: false },
  "ALP:S03": { x: 340, y: 104, lineCode: "ALP", stationId: "S03", isInterchange: false },
  "ALP:S04": { x: 410, y: 104, lineCode: "ALP", stationId: "S04", isInterchange: false },
  "ALP:H01": { x: 478, y: 104, lineCode: "ALP", stationId: "H01", isInterchange: true, rectX: 466, rectY: 82, width: 24, height: 44 },
  "ALP:H02": { x: 578, y: 104, lineCode: "ALP", stationId: "H02", isInterchange: true, rectX: 566, rectY: 82, width: 24, height: 44 },
  "ALP:S05": { x: 650, y: 104, lineCode: "ALP", stationId: "S05", isInterchange: false },
  "ALP:S06": { x: 720, y: 104, lineCode: "ALP", stationId: "S06", isInterchange: false },
  "ALP:S07": { x: 790, y: 104, lineCode: "ALP", stationId: "S07", isInterchange: false },
  "ALP:S08": { x: 860, y: 104, lineCode: "ALP", stationId: "S08", isInterchange: false },

  // BET Line stations (cy = 280)
  "BET:S11": { x: 200, y: 280, lineCode: "BET", stationId: "S11", isInterchange: false },
  "BET:S12": { x: 270, y: 280, lineCode: "BET", stationId: "S12", isInterchange: false },
  "BET:S13": { x: 340, y: 280, lineCode: "BET", stationId: "S13", isInterchange: false },
  "BET:S14": { x: 410, y: 280, lineCode: "BET", stationId: "S14", isInterchange: false },
  "BET:H01": { x: 478, y: 280, lineCode: "BET", stationId: "H01", isInterchange: true, rectX: 466, rectY: 258, width: 24, height: 44 },
  "BET:H02": { x: 578, y: 280, lineCode: "BET", stationId: "H02", isInterchange: true, rectX: 566, rectY: 258, width: 24, height: 44 },
  "BET:S15": { x: 650, y: 280, lineCode: "BET", stationId: "S15", isInterchange: false },
  "BET:S16": { x: 720, y: 280, lineCode: "BET", stationId: "S16", isInterchange: false },
  "BET:S17": { x: 790, y: 280, lineCode: "BET", stationId: "S17", isInterchange: false },
  "BET:S18": { x: 860, y: 280, lineCode: "BET", stationId: "S18", isInterchange: false },
};

// Track Y coordinates for bounds
export const TRACK_Y = {
  ALP: { EB: 92, WB: 116 },
  BET: { EB: 268, WB: 292 },
};

// Build sector layout coordinates from station positions
function buildSectorLayout() {
  const sectors = {};
  const alpSectors = [
    ["S01_S02", "S01", "S02"],
    ["S02_S03", "S02", "S03"],
    ["S03_S04", "S03", "S04"],
    ["S04_H01", "S04", "H01"],
    ["H01_H02", "H01", "H02"],
    ["H02_S05", "H02", "S05"],
    ["S05_S06", "S05", "S06"],
    ["S06_S07", "S06", "S07"],
    ["S07_S08", "S07", "S08"],
  ];

  alpSectors.forEach(([slug, fromStn, toStn]) => {
    const fromLayout = stationLayout[`ALP:${fromStn}`];
    const toLayout = stationLayout[`ALP:${toStn}`];
    const secId = `SEC:ALP:${slug}`;

    // EB bound (y = 92)
    sectors[`${secId}:EB`] = {
      locationId: `${secId}:EB`,
      sectorId: secId,
      lineCode: "ALP",
      slug,
      bound: "EB",
      fromStn,
      toStn,
      x1: fromLayout.x,
      x2: toLayout.x,
      y: TRACK_Y.ALP.EB,
      midX: (fromLayout.x + toLayout.x) / 2,
    };

    // WB bound (y = 116)
    sectors[`${secId}:WB`] = {
      locationId: `${secId}:WB`,
      sectorId: secId,
      lineCode: "ALP",
      slug,
      bound: "WB",
      fromStn,
      toStn,
      x1: fromLayout.x,
      x2: toLayout.x,
      y: TRACK_Y.ALP.WB,
      midX: (fromLayout.x + toLayout.x) / 2,
    };
  });

  const betSectors = [
    ["S11_S12", "S11", "S12"],
    ["S12_S13", "S12", "S13"],
    ["S13_S14", "S13", "S14"],
    ["S14_H01", "S14", "H01"],
    ["H01_H02", "H01", "H02"],
    ["H02_S15", "H02", "S15"],
    ["S15_S16", "S15", "S16"],
    ["S16_S17", "S16", "S17"],
    ["S17_S18", "S17", "S18"],
  ];

  betSectors.forEach(([slug, fromStn, toStn]) => {
    const fromLayout = stationLayout[`BET:${fromStn}`];
    const toLayout = stationLayout[`BET:${toStn}`];
    const secId = `SEC:BET:${slug}`;

    // EB bound (y = 268)
    sectors[`${secId}:EB`] = {
      locationId: `${secId}:EB`,
      sectorId: secId,
      lineCode: "BET",
      slug,
      bound: "EB",
      fromStn,
      toStn,
      x1: fromLayout.x,
      x2: toLayout.x,
      y: TRACK_Y.BET.EB,
      midX: (fromLayout.x + toLayout.x) / 2,
    };

    // WB bound (y = 292)
    sectors[`${secId}:WB`] = {
      locationId: `${secId}:WB`,
      sectorId: secId,
      lineCode: "BET",
      slug,
      bound: "WB",
      fromStn,
      toStn,
      x1: fromLayout.x,
      x2: toLayout.x,
      y: TRACK_Y.BET.WB,
      midX: (fromLayout.x + toLayout.x) / 2,
    };
  });

  return sectors;
}

export const sectorLayout = buildSectorLayout();

// Platform layout coordinates
function buildPlatformLayout() {
  const platforms = {};
  Object.values(stationLayout).forEach((stn) => {
    const line = stn.lineCode;
    const sid = stn.stationId;
    const yEB = TRACK_Y[line].EB;
    const yWB = TRACK_Y[line].WB;

    platforms[`PLAT:${line}:${sid}:EB`] = {
      locationId: `PLAT:${line}:${sid}:EB`,
      lineCode: line,
      stationId: sid,
      bound: "EB",
      x: stn.x,
      y: yEB,
      isInterchange: stn.isInterchange,
    };

    platforms[`PLAT:${line}:${sid}:WB`] = {
      locationId: `PLAT:${line}:${sid}:WB`,
      lineCode: line,
      stationId: sid,
      bound: "WB",
      x: stn.x,
      y: yWB,
      isInterchange: stn.isInterchange,
    };
  });
  return platforms;
}

export const platformLayout = buildPlatformLayout();

export const CROSSOVER_BOX = {
  x: 450,
  y: 70,
  width: 160,
  height: 240,
  rx: 12,
  arrows: [
    { x: 478, y1: 126, y2: 232 },
    { x: 578, y1: 126, y2: 232 },
  ],
  badge: {
    x: 530,
    y: 180,
    width: 156,
    height: 34,
    rx: 6,
    title: "Live-only crossover",
    subtitle: "Non-Live: fully independent",
  },
};
