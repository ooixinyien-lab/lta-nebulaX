import { useState, useEffect } from "react";
import {
  fetchNetworkContext,
  fetchNetworkTopology,
  fetchNetworkActivities,
} from "../services/networkApi";

export function useNetworkTopology() {
  const [context, setContext] = useState(null);
  const [topology, setTopology] = useState(null);
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadBootstrap() {
      try {
        setLoading(true);
        setError(null);
        const [ctxData, topoData, actData] = await Promise.all([
          fetchNetworkContext(controller.signal),
          fetchNetworkTopology(controller.signal),
          fetchNetworkActivities(controller.signal),
        ]);
        setContext(ctxData);
        setTopology(topoData);
        setActivities(actData);
      } catch (err) {
        if (err.name !== "AbortError") {
          setError(err.message || "Failed to load network data");
        }
      } finally {
        setLoading(false);
      }
    }

    loadBootstrap();

    return () => {
      controller.abort();
    };
  }, []);

  return { context, topology, activities, loading, error };
}
