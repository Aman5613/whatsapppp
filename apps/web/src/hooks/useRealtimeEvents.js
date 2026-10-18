import { useEffect, useState, useRef } from 'react';

/**
 * Hook to connect to Server-Sent Events (SSE) for real-time dashboard events.
 * Emits window-level 'app-realtime-event' for decoupled components.
 */
export function useRealtimeEvents(businessId, onEvent) {
  const [connected, setConnected] = useState(false);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!businessId) return;

    let eventSource = null;
    let reconnectTimeout = null;

    const connect = () => {
      const url = `/api/events?business_id=${businessId}`;
      eventSource = new EventSource(url);

      eventSource.addEventListener('connected', () => {
        setConnected(true);
      });

      const handleEvent = (type) => (e) => {
        try {
          const data = e.data ? JSON.parse(e.data) : {};
          if (onEventRef.current) {
            onEventRef.current(type, data);
          }
          window.dispatchEvent(
            new CustomEvent('app-realtime-event', {
              detail: { type, data },
            })
          );
        } catch {
          // ignore parsing error
        }
      };

      eventSource.addEventListener('new_message', handleEvent('new_message'));
      eventSource.addEventListener('conversation_updated', handleEvent('conversation_updated'));

      eventSource.onerror = () => {
        setConnected(false);
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }
        // Attempt reconnect after 5 seconds
        reconnectTimeout = setTimeout(connect, 5000);
      };
    };

    connect();

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
      setConnected(false);
    };
  }, [businessId]);

  return { connected };
}
