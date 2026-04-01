import { useState, useEffect, useCallback, useRef } from 'react';
import type { Event, ConnectionState } from '../types';
import { connectEventStream, getEvents } from '../api/client';

export function useEventStream(sessionId: string | null) {
  const [events, setEvents] = useState<Event[]>([]);
  const [connectionState, setConnectionState] = useState<ConnectionState>('offline');
  const esRef = useRef<EventSource | null>(null);
  const retryCountRef = useRef(0);

  // 加载历史事件
  useEffect(() => {
    if (!sessionId) return;
    getEvents(sessionId)
      .then(data => setEvents(data.entries))
      .catch(console.error);
  }, [sessionId]);

  // SSE 连接
  useEffect(() => {
    const connect = () => {
      const es = connectEventStream(
        (event) => {
          // 只处理当前会话的事件
          if (event.session_id === sessionId || !event.session_id) {
            setEvents(prev => [...prev, event]);
          }
        },
        (error) => {
          console.error('SSE error:', error);
          setConnectionState('reconnecting');
          // 指数退避重连
          const delay = Math.min(1000 * Math.pow(2, retryCountRef.current), 30000);
          retryCountRef.current++;
          setTimeout(connect, delay);
        }
      );
      esRef.current = es;
      setConnectionState('connected');
      retryCountRef.current = 0;
    };

    connect();

    return () => {
      esRef.current?.close();
    };
  }, [sessionId]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { events, connectionState, clearEvents };
}
