import { useCallback, useEffect, useRef, useState } from 'react';
import { createIngestSocket } from './activeLearningApi';

export interface WebcamStreamOptions {
  /** Target frames per second to capture + send. Default 12. */
  fps?: number;
  /** Capture width sent to the server. Default 640 (matches pipeline). */
  width?: number;
  /** Capture height sent to the server. Default 480. */
  height?: number;
  /** JPEG quality, 0..1. Default 0.6 (good enough for pose, keeps bandwidth low). */
  quality?: number;
}

export type WebcamStatus = 'idle' | 'starting' | 'streaming' | 'error';

export interface WebcamStreamState {
  status: WebcamStatus;
  /** Permission/getUserMedia error message, if any. */
  error: string | null;
  /** True once the /ws/ingest socket is open (i.e. the backend is receiving). */
  ingestConnected: boolean;
  /** Frames actually sent to the server in the last second. */
  sentFps: number;
}

export interface WebcamStreamControls {
  /** Attach to a <video autoPlay playsInline muted> to show the local preview. */
  videoRef: React.RefObject<HTMLVideoElement | null>;
  state: WebcamStreamState;
  start: () => Promise<void>;
  stop: () => void;
}

/**
 * Captures this device's webcam, renders a local preview into the supplied
 * <video> element, and streams JPEG frames to the backend over /ws/ingest.
 */
export function useWebcamStream(options: WebcamStreamOptions = {}): WebcamStreamControls {
  const { fps = 12, width = 640, height = 480, quality = 0.6 } = options;

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sendingRef = useRef(false); // true between start() and stop()
  const inFlightRef = useRef(false); // guards against overlapping toBlob encodes

  // fps accounting
  const sentInWindowRef = useRef(0);
  const windowStartRef = useRef(0);

  const [state, setState] = useState<WebcamStreamState>({
    status: 'idle',
    error: null,
    ingestConnected: false,
    sentFps: 0,
  });

  const connectIngest = useCallback(() => {
    if (!sendingRef.current) return;
    let socket: WebSocket;
    try {
      socket = createIngestSocket();
    } catch {
      return;
    }
    socket.binaryType = 'arraybuffer';
    socketRef.current = socket;

    socket.onopen = () => {
      setState((s) => ({ ...s, ingestConnected: true }));
      try {
        socket.send(JSON.stringify({ type: 'hello', format: 'jpeg', width, height }));
      } catch {
        /* ignore */
      }
    };
    socket.onclose = () => {
      if (socketRef.current === socket) socketRef.current = null;
      setState((s) => ({ ...s, ingestConnected: false }));
      // Retry while we're still meant to be streaming (e.g. backend not up yet).
      if (sendingRef.current && !reconnectRef.current) {
        reconnectRef.current = setTimeout(() => {
          reconnectRef.current = null;
          connectIngest();
        }, 2000);
      }
    };
    socket.onerror = () => {
      // onclose handles reconnect; just avoid an unhandled error.
    };
  }, [width, height]);

  const sendFrame = useCallback(() => {
    const video = videoRef.current;
    const socket = socketRef.current;
    if (!video || video.readyState < 2) return; // not enough data yet
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    // Backpressure: skip if the socket is already behind (~512KB buffered).
    if (socket.bufferedAmount > 512 * 1024) return;
    if (inFlightRef.current) return;

    let canvas = canvasRef.current;
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      canvasRef.current = canvas;
    }
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, width, height);

    inFlightRef.current = true;
    canvas.toBlob(
      (blob) => {
        inFlightRef.current = false;
        if (!blob) return;
        const sock = socketRef.current;
        if (!sock || sock.readyState !== WebSocket.OPEN) return;
        blob.arrayBuffer().then((buf) => {
          if (sock.readyState === WebSocket.OPEN) {
            sock.send(buf);
            sentInWindowRef.current += 1;
          }
        }).catch(() => { /* ignore */ });
      },
      'image/jpeg',
      quality,
    );
  }, [width, height, quality]);

  const stop = useCallback(() => {
    sendingRef.current = false;

    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
    if (reconnectRef.current) { clearTimeout(reconnectRef.current); reconnectRef.current = null; }

    if (socketRef.current) {
      try { socketRef.current.close(); } catch { /* ignore */ }
      socketRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) videoRef.current.srcObject = null;

    setState({ status: 'idle', error: null, ingestConnected: false, sentFps: 0 });
  }, []);

  const start = useCallback(async () => {
    if (sendingRef.current) return;
    setState((s) => ({ ...s, status: 'starting', error: null }));

    if (!navigator.mediaDevices?.getUserMedia) {
      setState((s) => ({ ...s, status: 'error', error: 'This browser does not support camera access.' }));
      return;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: width }, height: { ideal: height } },
        audio: false,
      });
    } catch (err) {
      const message =
        err instanceof DOMException && err.name === 'NotAllowedError'
          ? 'Camera permission denied. Allow camera access and try again.'
          : err instanceof Error
            ? err.message
            : 'Unable to access the camera.';
      setState((s) => ({ ...s, status: 'error', error: message }));
      return;
    }

    streamRef.current = stream;
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      try { await videoRef.current.play(); } catch { /* autoplay may already be playing */ }
    }

    sendingRef.current = true;
    sentInWindowRef.current = 0;
    windowStartRef.current = performance.now();
    setState((s) => ({ ...s, status: 'streaming' }));

    connectIngest();

    intervalRef.current = setInterval(() => {
      sendFrame();
      const now = performance.now();
      if (now - windowStartRef.current >= 1000) {
        const measured = sentInWindowRef.current;
        sentInWindowRef.current = 0;
        windowStartRef.current = now;
        setState((s) => (s.sentFps === measured ? s : { ...s, sentFps: measured }));
      }
    }, Math.max(1, Math.round(1000 / fps)));
  }, [connectIngest, sendFrame, fps, width, height]);

  // Stop everything if the component using the hook unmounts.
  useEffect(() => stop, [stop]);

  return { videoRef, state, start, stop };
}
