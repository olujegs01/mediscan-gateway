import { useEffect, useRef, useCallback, useState } from "react";

/**
 * Persistent WebSocket hook with automatic reconnect.
 * onMessage receives a parsed JSON object.
 */
export function useWebSocket(url, onMessage) {
  const wsRef = useRef(null);
  const onMsgRef = useRef(onMessage);
  const [connected, setConnected] = useState(false);
  const reconnectTimer = useRef(null);

  // Keep callback ref current without triggering reconnects
  useEffect(() => { onMsgRef.current = onMessage; }, [onMessage]);

  const connect = useCallback(() => {
    if (!url) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
    };

    ws.onmessage = (e) => {
      try {
        onMsgRef.current(JSON.parse(e.data));
      } catch (err) {
        console.warn("WS parse error:", err);
      }
    };

    ws.onclose = (e) => {
      setConnected(false);
      if (e.code !== 4001) {
        // Exponential backoff: 2s, 4s, 8s, max 30s
        const delay = Math.min(30000, 2000 * Math.pow(1.5, Math.floor(Math.random() * 4)));
        reconnectTimer.current = setTimeout(connect, delay);
      }
    };

    ws.onerror = () => ws.close();
  }, [url]);

  useEffect(() => {
    connect();
    // Ping every 25s to keep connection alive through load balancers
    const ping = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send("ping");
      }
    }, 25000);
    return () => {
      clearInterval(ping);
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close(1000);
    };
  }, [connect]);

  return { connected };
}
