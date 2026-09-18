import { useState, useEffect, useRef } from "react";
import { fetchNetworkOccupancy } from "../services/networkApi";

export function useNetworkOccupancy(scenario, week, selectedActivityId = null) {
  const [occupancy, setOccupancy] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);

  // Request race token to prevent older responses from overwriting newer ones
  const requestSeqRef = useRef(0);

  const retry = () => setRetryCount((c) => c + 1);

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
          // Keep previous occupancy intact to avoid flashing blank state
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
  }, [scenario, week, selectedActivityId, retryCount]);

  return { occupancy, loading, error, retry };
}
