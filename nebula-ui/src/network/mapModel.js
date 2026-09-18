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

  return { type: "unknown", locationId: locId, label: locId, bound: "", lineCode: "" };
}
