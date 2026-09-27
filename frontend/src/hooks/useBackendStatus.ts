import { useEffect, useState } from "react";
import { apiClient, type HealthResponse, type VersionResponse } from "../services/api";

type ConnectionState = "loading" | "ready" | "error";

/**
 * Polls Django health/version so the shell can show API status without
 * putting connection logic inside every page.
 */
export const useBackendStatus = () => {
  const [state, setState] = useState<ConnectionState>("loading");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [version, setVersion] = useState<VersionResponse | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [healthPayload, versionPayload] = await Promise.all([
          apiClient.get<HealthResponse>("/health/"),
          apiClient.get<VersionResponse>("/version/"),
        ]);
        if (cancelled) {
          return;
        }
        setHealth(healthPayload);
        setVersion(versionPayload);
        setState("ready");
      } catch (error) {
        if (cancelled) {
          return;
        }
        setState("error");
        setMessage(error instanceof Error ? error.message : "Unable to reach the local API.");
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return { state, health, version, message };
};
