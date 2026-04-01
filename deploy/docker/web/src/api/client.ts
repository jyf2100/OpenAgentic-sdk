import type { Session, Event, WorkerStatus } from '../types';

const API_BASE = '';  // 使用 Vite proxy

export async function createSession(title?: string): Promise<Session> {
  const res = await fetch(`${API_BASE}/session`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(title ? { title } : {}),
  });
  if (!res.ok) throw new Error(`Failed to create session: ${res.status}`);
  return res.json();
}

export async function getSession(sessionId: string): Promise<Session> {
  const res = await fetch(`${API_BASE}/session/${sessionId}`);
  if (!res.ok) throw new Error(`Failed to get session: ${res.status}`);
  return res.json();
}

export async function sendMessage(sessionId: string, prompt: string): Promise<void> {
  const res = await fetch(`${API_BASE}/session/${sessionId}/prompt_async`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
  });
  if (!res.ok) throw new Error(`Failed to send message: ${res.status}`);
  // 204 No Content
}

export async function getEvents(sessionId: string): Promise<{ entries: Event[] }> {
  const res = await fetch(`${API_BASE}/session/${sessionId}/events`);
  if (!res.ok) throw new Error(`Failed to get events: ${res.status}`);
  return res.json();
}

export async function getHealth(): Promise<WorkerStatus> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error(`Failed to get health: ${res.status}`);
  return res.json();
}

export function connectEventStream(
  onMessage: (event: Event) => void,
  onError?: (error: Error) => void
): EventSource {
  const es = new EventSource(`${API_BASE}/event`);

  es.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data);
      onMessage(data);
    } catch (err) {
      console.error('Failed to parse event:', err);
    }
  };

  es.onerror = (e) => {
    console.error('SSE error:', e);
    if (onError) onError(new Error('SSE connection error'));
  };

  return es;
}
