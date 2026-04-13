"use client";

import { useEffect, useRef } from "react";
import { connectGkfyRealtime } from "@/lib/gkfyRealtime";
import type { GkfyRealtimeMessage } from "@/types/realtime";

/**
 * Subscribes to the API WebSocket; handler always sees the latest callback via ref.
 */
export function useGkfyRealtime(
  onMessage: (msg: GkfyRealtimeMessage) => void,
  options?: { onOpen?: () => void; onClose?: () => void },
): void {
  const handlerRef = useRef(onMessage);
  const onOpenRef = useRef(options?.onOpen);
  const onCloseRef = useRef(options?.onClose);
  handlerRef.current = onMessage;
  onOpenRef.current = options?.onOpen;
  onCloseRef.current = options?.onClose;

  useEffect(() => {
    const conn = connectGkfyRealtime(
      (msg) => {
        handlerRef.current(msg);
      },
      {
        onOpen: () => onOpenRef.current?.(),
        onClose: () => onCloseRef.current?.(),
      },
    );
    return () => conn.close();
  }, []);
}
