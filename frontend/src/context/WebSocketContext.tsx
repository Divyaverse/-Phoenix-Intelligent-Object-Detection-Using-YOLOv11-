import React, { createContext, useContext, useEffect, useState, useRef } from 'react';
import type { EventEnvelope } from '../types/phoenix';
import { useAuth } from '../context/AuthContext';

interface WebSocketContextType {
  isConnected: boolean;
  lastEvent: EventEnvelope | null;
  eventsHistory: EventEnvelope[];
  error: string | null;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

export const WebSocketProvider: React.FC<{ buildingId?: string; children: React.ReactNode }> = ({
  buildingId = 'bldg-hq-01',
  children,
}) => {
  const { token, isAuthenticated } = useAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<EventEnvelope | null>(null);
  const [eventsHistory, setEventsHistory] = useState<EventEnvelope[]>([]);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!isAuthenticated || !token) {
      if (socketRef.current) {
        socketRef.current.close();
      }
      setIsConnected(false);
      return;
    }

    const wsUrl = `ws://localhost:8000/ws/v1/buildings/${buildingId}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    ws.onmessage = (event) => {
      if (event.data === '{"type": "pong"}') return;
      try {
        const envelope: EventEnvelope = JSON.parse(event.data);
        setLastEvent(envelope);
        setEventsHistory((prev) => [envelope, ...prev.slice(0, 49)]);
      } catch (err) {
        // Ignore non-JSON ping/pong frames
      }
    };

    ws.onerror = () => {
      setError('Live WebSocket Connection Error');
    };

    ws.onclose = () => {
      setIsConnected(false);
    };

    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping');
      }
    }, 15000);

    return () => {
      clearInterval(pingInterval);
      ws.close();
    };
  }, [isAuthenticated, token, buildingId]);

  return (
    <WebSocketContext.Provider value={{ isConnected, lastEvent, eventsHistory, error }}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};
