import { useState, useEffect, useCallback, useRef } from 'react';
import { JulesClient } from './client';
import type { Session, Activity } from './client';

export type PollingStatus = 'idle' | 'polling' | 'error';

export function useJulesSession(apiKey: string | null, sessionId: string | null, pollIntervalMs = 5000) {
  const [session, setSession] = useState<Session | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [status, setStatus] = useState<PollingStatus>('idle');
  const [error, setError] = useState<string | null>(null);

  const clientRef = useRef<JulesClient | null>(null);
  const pollingRef = useRef<number | null>(null);

  useEffect(() => {
    if (apiKey) {
      clientRef.current = new JulesClient(apiKey);
    } else {
      clientRef.current = null;
    }
  }, [apiKey]);

  const fetchSessionData = useCallback(async () => {
    if (!clientRef.current || !sessionId) return;

    try {
      const fetchedSession = await clientRef.current.getSession(sessionId);
      setSession(fetchedSession);

      const fetchedActivities = await clientRef.current.listActivities(sessionId);
      setActivities(fetchedActivities.activities || []);

      setStatus('polling');
      setError(null);
    } catch (err) {
      console.error("Polling error:", err);
      setStatus('error');
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [sessionId]);

  const startPolling = useCallback(() => {
    if (!pollingRef.current) {
      fetchSessionData(); // Initial fetch
      pollingRef.current = window.setInterval(fetchSessionData, pollIntervalMs);
      setTimeout(() => setStatus('polling'), 0);
    }
  }, [fetchSessionData, pollIntervalMs]);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      window.clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    setTimeout(() => setStatus('idle'), 0);
  }, []);

  // Auto-start polling if session ID changes and we have a key
  useEffect(() => {
    if (sessionId && apiKey) {
      startPolling();
    } else {
      stopPolling();
      setTimeout(() => {
        setSession(null);
        setActivities([]);
      }, 0);
    }

    return () => stopPolling();
  }, [sessionId, apiKey, startPolling, stopPolling]);

  // Actions
  const approvePlan = async () => {
    if (!clientRef.current || !sessionId) throw new Error("Client or session not initialized");
    const updated = await clientRef.current.approvePlan(sessionId);
    setSession(updated);
    fetchSessionData();
  };

  const sendMessage = async (prompt: string) => {
    if (!clientRef.current || !sessionId) throw new Error("Client or session not initialized");
    const updated = await clientRef.current.sendMessage(sessionId, { prompt });
    setSession(updated);
    fetchSessionData();
  };

  const getClient = () => clientRef.current;

  return {
    session,
    activities,
    status,
    error,
    startPolling,
    stopPolling,
    approvePlan,
    sendMessage,
    getClient,
    refresh: fetchSessionData
  };
}
