/**
 * Helper functions for date ranges and location identities.
 * Week 1 begins on startDate (Monday 2027-01-04) and ends on Sunday 2027-01-10.
 */
export function getWeekDateRange(startDateStr, week) {
  if (!startDateStr || !week) return "";
  const start = new Date(startDateStr);
  const startOffsetDays = (week - 1) * 7;
  const endOffsetDays = startOffsetDays + 6;

  const weekStart = new Date(start.getTime() + startOffsetDays * 86400000);
  const weekEnd = new Date(start.getTime() + endOffsetDays * 86400000);

  const options = { day: "2-digit", month: "short", year: "numeric" };
  const startFormatted = weekStart.toLocaleDateString("en-GB", options);
  const endFormatted = weekEnd.toLocaleDateString("en-GB", options);

  return `${startFormatted} – ${endFormatted}`;
}

/**
 * Resolves human-readable entity title and subtitle from location ID.
 */
export function resolveLocationDetails(locId) {
  if (!locId) return { type: "unknown", label: "None", bound: "", lineCode: "" };

  if (locId.startsWith("PLAT:")) {
    // PLAT:ALP:H01:EB
    const [, lineCode, stnId, bound] = locId.split(":");
    return {
      type: "platform",
      locationId: locId,
      stationId: stnId,
      lineCode,
      bound,
      label: `${lineCode} Station ${stnId} Platform (${bound})`,
      stationKey: `${lineCode}:${stnId}`,
    };
  }

  if (locId.startsWith("SEC:")) {
    // SEC:ALP:S01_S02:EB
    const [, lineCode, slug, bound] = locId.split(":");
    const [fromStn, toStn] = slug.split("_");
    return {
      type: "sector",
      locationId: locId,
      sectorId: `SEC:${lineCode}:${slug}`,
      slug,
      lineCode,
      bound,
      fromStn,
      toStn,
      label: `${lineCode} Sector ${slug} (${bound})`,
    };
  }

  // Station Key e.g. "ALP:S01", "BET:S12", "ALP:H01"
  if (locId.includes(":")) {
    const [lineCode, stnId] = locId.split(":");
    const isInterchange = stnId === "H01" || stnId === "H02";
    return {
      type: "station",
      locationId: locId,
      stationId: stnId,
      lineCode,
      isInterchange,
      bound: "Both (EB & WB)",
      label: isInterchange
        ? `Station ${stnId} · Interchange (${lineCode})`
        : `Station ${stnId} · Line ${lineCode === "ALP" ? "Alpha" : "Beta"}`,
      stationKey: locId,
    };
  }

  // Plain station ID e.g. "H01", "S01"
  return {
    type: "station",
    locationId: locId,
    stationId: locId,
    lineCode: "",
    isInterchange: locId === "H01" || locId === "H02",
    label: `Station ${locId}`,
    stationKey: locId,
    bound: "",
  };
}

/**
 * Returns EB and WB platform IDs for a given station.
 */
export function getStationPlatforms(lineCode, stationId) {
  if (!lineCode || !stationId) return { ebPlatId: "", wbPlatId: "" };
  return {
    ebPlatId: `PLAT:${lineCode}:${stationId}:EB`,
    wbPlatId: `PLAT:${lineCode}:${stationId}:WB`,
  };
}

/**
 * Finds next scheduled week after currentWeek from a sorted list of weeks.
 * If no week is strictly greater, returns the first scheduled week.
 */
export function findNextScheduledWeek(scheduledWeeks = [], currentWeek = 1) {
  if (!scheduledWeeks || scheduledWeeks.length === 0) return null;
  const futureWeek = scheduledWeeks.find((w) => w > currentWeek);
  if (futureWeek !== undefined) return futureWeek;
  return scheduledWeeks[0];
}

