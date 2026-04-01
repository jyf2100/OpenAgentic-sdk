export interface Session {
  id: string;
  created_at: number;
  metadata: {
    title?: string;
    cwd?: string;
    provider_name?: string;
    model?: string;
    [key: string]: unknown;
  };
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

export interface Event {
  type: string;
  ts: number;
  seq: number;
  session_id?: string;
  text?: string;
  name?: string;
  input?: Record<string, unknown>;
  result?: unknown;
  usage?: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  };
  [key: string]: unknown;
}

export interface TokenUsage {
  input: number;
  output: number;
  total: number;
}

export interface WorkerStatus {
  ok: boolean;
  node_name?: string;
  provider_ready?: boolean;
  provider_profiles?: string[];
  cwd?: string;
  git_revision?: string;
}

export type ConnectionState = 'connected' | 'reconnecting' | 'offline';
