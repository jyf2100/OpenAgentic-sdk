import { useState, useCallback } from 'react';
import type { Session } from '../types';
import { createSession as apiCreateSession } from '../api/client';

export function useSession() {
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(false);

  const createNewSession = useCallback(async (title?: string) => {
    setLoading(true);
    try {
      const session = await apiCreateSession(title);
      setCurrentSessionId(session.id);
      setSessions(prev => [session, ...prev]);
      return session;
    } finally {
      setLoading(false);
    }
  }, []);

  const switchSession = useCallback((sessionId: string) => {
    setCurrentSessionId(sessionId);
  }, []);

  return {
    currentSessionId,
    sessions,
    loading,
    createNewSession,
    switchSession,
  };
}
