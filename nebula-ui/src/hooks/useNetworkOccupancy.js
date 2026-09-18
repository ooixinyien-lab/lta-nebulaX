import { useState, useEffect, useRef } from "react";
import { fetchNetworkOccupancy } from "../services/networkApi";

export function useNetworkOccupancy(scenario, week, selectedActivityId = null) {
  const [occupancy, setOccupancy] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Request race token to prevent older responses from overwriting newer ones
  const requestSeqRef = useRef(0);

  useEffect(() => {
    if (!scenario || !week) return;

    const controller = new AbortController();
    const currentSeq = ++requestSeqRef.current;

    async function loadOccupancy() {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchNetworkOccupancy(
          scenario,
          week,
          selectedActivityId,
          controller.signal
        );

        if (currentSeq === requestSeqRef.current) {
          setOccupancy(data);
        }
      } catch (err) {
        if (err.name !== "AbortError" && currentSeq === requestSeqRef.current) {
          setError(err.message || "Failed to load occupancy");
        }
      } finally {
        if (currentSeq === requestSeqRef.current) {
          setLoading(false);
        }
      }
    }

    loadOccupancy();

    return () => {
      controller.abort();
    };
  }, [scenario, week, selectedActivityId]);

  return { occupancy, loading, error };
}
