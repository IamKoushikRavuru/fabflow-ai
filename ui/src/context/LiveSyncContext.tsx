import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import { fetchApi } from '@/lib/api';

interface LiveSyncContextType {
  isLive: boolean;
  intervalSeconds: number;
  lastSyncTime: Date | null;
  latencyMs: number;
  isSyncing: boolean;
  triggerSync: () => Promise<void>;
  setIsLive: (live: boolean) => void;
  setIntervalSeconds: (seconds: number) => void;
}

const LiveSyncContext = createContext<LiveSyncContextType | undefined>(undefined);

export function LiveSyncProvider({ children }: { children: React.ReactNode }) {
  const [isLive, setIsLiveState] = useState<boolean>(() => {
    const saved = localStorage.getItem('fabflow_live_sync');
    return saved !== null ? saved === 'true' : true;
  });

  const [intervalSeconds, setIntervalSecondsState] = useState<number>(() => {
    const saved = localStorage.getItem('fabflow_sync_interval');
    return saved ? Number(saved) : 3;
  });

  const [lastSyncTime, setLastSyncTime] = useState<Date | null>(new Date());
  const [latencyMs, setLatencyMs] = useState<number>(42);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const timerRef = useRef<number | null>(null);

  const setIsLive = (live: boolean) => {
    setIsLiveState(live);
    localStorage.setItem('fabflow_live_sync', String(live));
  };

  const setIntervalSeconds = (sec: number) => {
    setIntervalSecondsState(sec);
    localStorage.setItem('fabflow_sync_interval', String(sec));
  };

  const triggerSync = useCallback(async () => {
    setIsSyncing(true);
    const start = performance.now();
    try {
      await fetchApi<{ status: string; db_connected: boolean }>('/health');
      const elapsed = Math.max(1, Math.round(performance.now() - start));
      setLatencyMs(elapsed);
      setLastSyncTime(new Date());
      // Broadcast sync event to all active views
      window.dispatchEvent(new CustomEvent('fabflow:sync'));
    } catch (err) {
      console.warn('Live sync ping error:', err);
    } finally {
      setIsSyncing(false);
    }
  }, []);

  useEffect(() => {
    if (!isLive) {
      if (timerRef.current) clearInterval(timerRef.current);
      return;
    }

    // Trigger immediate sync
    triggerSync();

    timerRef.current = window.setInterval(() => {
      triggerSync();
    }, intervalSeconds * 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isLive, intervalSeconds, triggerSync]);

  return (
    <LiveSyncContext.Provider
      value={{
        isLive,
        intervalSeconds,
        lastSyncTime,
        latencyMs,
        isSyncing,
        triggerSync,
        setIsLive,
        setIntervalSeconds,
      }}
    >
      {children}
    </LiveSyncContext.Provider>
  );
}

export function useLiveSync() {
  const context = useContext(LiveSyncContext);
  if (!context) {
    throw new Error('useLiveSync must be used within a LiveSyncProvider');
  }
  return context;
}
