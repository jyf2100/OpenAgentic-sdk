import { useState, useEffect } from 'react';
import type { WorkerStatus } from '../types';
import { getHealth } from '../api/client';

export function useWorkerStatus(intervalMs = 10000) {
  const [status, setStatus] = useState<WorkerStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const check = async () => {
      try {
        const health = await getHealth();
        setStatus(health);
      } catch {
        setStatus(null);
      } finally {
        setLoading(false);
      }
    };

    check();
    const id = setInterval(check, intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);

  return { status, loading };
}
