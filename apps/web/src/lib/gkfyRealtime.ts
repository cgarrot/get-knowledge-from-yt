"use client";

import { getWsApiBase } from "@/lib/api";
import type { GkfyRealtimeMessage } from "@/types/realtime";

function parseMessage(raw: string): GkfyRealtimeMessage | null {
  try {
    const msg = JSON.parse(raw) as GkfyRealtimeMessage;
    if (msg && typeof msg.type === "string") return msg;
  } catch {
    /* ignore */
  }
  return null;
}

export interface GkfyRealtimeConnection {
  close: () => void;
}

/**
 * Single WebSocket to `/ws` with auto-reconnect. Safe to call from the browser only.
 */
export function connectGkfyRealtime(
  onMessage: (msg: GkfyRealtimeMessage) => void,
  options?: {
    onOpen?: () => void;
    onClose?: () => void;
  },
): GkfyRealtimeConnection {
  let stopped = false;
  let ws: WebSocket | null = null;
  let attempt = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  const clearTimer = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  };

  const scheduleReconnect = () => {
    if (stopped) return;
    clearTimer();
    const delay = Math.min(30_000, 800 * 2 ** attempt);
    attempt += 1;
    reconnectTimer = setTimeout(connect, delay);
  };

  function connect() {
    if (stopped || typeof window === "undefined") return;
    clearTimer();
    const url = `${getWsApiBase()}/ws`;
    try {
      ws = new WebSocket(url);
    } catch {
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      attempt = 0;
      options?.onOpen?.();
    };

    ws.onmessage = (ev) => {
      const msg = parseMessage(String(ev.data));
      if (msg) onMessage(msg);
    };

    ws.onerror = () => {
      ws?.close();
    };

    ws.onclose = () => {
      ws = null;
      options?.onClose?.();
      if (!stopped) scheduleReconnect();
    };
  }

  connect();

  return {
    close: () => {
      stopped = true;
      clearTimer();
      ws?.close();
      ws = null;
    },
  };
}
