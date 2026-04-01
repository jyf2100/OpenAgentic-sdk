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
        (rawEvent) => {
          console.log('[SSE] 收到原始事件:', rawEvent);
          // 解析嵌套事件格式: {type: "session.event", session_id: "...", event: {...}}
          let actualEvent: Event;
          if (rawEvent.type === 'session.event' && rawEvent.event) {
            // 提取实际事件
            actualEvent = rawEvent.event as Event;
            console.log('[SSE] 提取嵌套事件:', actualEvent);
          } else if (rawEvent.type === 'server.connected' || rawEvent.type === 'server.heartbeat') {
            // 忽略心跳和连接事件
            console.log('[SSE] 心跳事件，忽略');
            return;
          } else {
            actualEvent = rawEvent;
          }

          // 只处理当前会话的事件
          const eventSessionId = rawEvent.session_id;
          console.log('[SSE] 当前会话:', sessionId, '事件会话:', eventSessionId);
          if (eventSessionId === sessionId || !eventSessionId) {
            setEvents(prev => {
              // 避免重复 (只有 seq 有效时才检查)
              const seq = actualEvent.seq;
              if (seq != null && prev.some(e => e.seq === seq)) {
                console.log('[SSE] 重复事件，跳过');
                return prev;
              }
              console.log('[SSE] 添加事件到列表:', actualEvent.type);
              return [...prev, actualEvent];
            });
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
