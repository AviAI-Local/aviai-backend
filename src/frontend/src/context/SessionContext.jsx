import { createContext, useContext, useRef, useState, useCallback } from "react";

const API_BASE_URL = "http://localhost:8000";
const WS_BASE_URL = "ws://localhost:8000";
const TTS_SAMPLE_RATE = 24000;
const MIC_SAMPLE_RATE = 16000;

// Audio conversion utilities
function pcm16ToFloat32(pcm16Array) {
  const float32 = new Float32Array(pcm16Array.length);
  for (let i = 0; i < pcm16Array.length; i++) {
    float32[i] = pcm16Array[i] / 32768;
  }
  return float32;
}

function float32ToPcm16(float32Array) {
  const pcm16 = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return pcm16;
}

const SessionContext = createContext(null);

export function SessionProvider({ children }) {
  // Session state
  const [sessionId, setSessionId] = useState(null);
  const [status, setStatus] = useState("idle"); // idle, connecting, listening, speaking, disconnected, error
  const [connected, setConnected] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [latestResponse, setLatestResponse] = useState("");
  const [voiceInstructions, setVoiceInstructions] = useState("neutral");
  const [avatarInstructions, setAvatarInstructions] = useState("neutral");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Refs for WebSocket and audio
  const conversationWsRef = useRef(null);
  const audioCtxRef = useRef(null);
  const micCtxRef = useRef(null);
  const processorRef = useRef(null);
  const speakingRef = useRef(false);
  const streamRef = useRef(null);

  // Send JSON message via WebSocket
  const sendJson = useCallback((message) => {
    if (conversationWsRef.current?.readyState === WebSocket.OPEN) {
      conversationWsRef.current.send(JSON.stringify(message));
    }
  }, []);

  // Initialize audio output
  const initAudioOutput = useCallback(async () => {
    audioCtxRef.current = new AudioContext({ sampleRate: TTS_SAMPLE_RATE });
    await audioCtxRef.current.resume();
  }, []);

  // Play TTS audio
  const playAudio = useCallback((audioData, onComplete) => {
    const pcm16 = new Int16Array(audioData);
    const float32 = pcm16ToFloat32(pcm16);
    const ctx = audioCtxRef.current;
    const buffer = ctx.createBuffer(1, float32.length, TTS_SAMPLE_RATE);
    buffer.copyToChannel(float32, 0);
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    source.onended = onComplete;
    source.start();
  }, []);

  // Initialize microphone
  const initMicrophone = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    micCtxRef.current = new AudioContext({ sampleRate: MIC_SAMPLE_RATE });
    await micCtxRef.current.resume();
    return stream;
  }, []);

  // Setup audio processor
  const setupProcessor = useCallback((stream, onAudioData) => {
    const src = micCtxRef.current.createMediaStreamSource(stream);
    processorRef.current = micCtxRef.current.createScriptProcessor(4096, 1, 1);
    src.connect(processorRef.current);
    processorRef.current.connect(micCtxRef.current.destination);
    processorRef.current.onaudioprocess = (e) => {
      const input = e.inputBuffer.getChannelData(0);
      const pcm16 = float32ToPcm16(input);
      onAudioData(pcm16.buffer);
    };
  }, []);

  // Handle mic audio data
  const handleMicAudioData = useCallback((audioBuffer) => {
    if (!speakingRef.current) return;
    if (!conversationWsRef.current || conversationWsRef.current.readyState !== WebSocket.OPEN) return;
    conversationWsRef.current.send(audioBuffer);
  }, []);

  // Handle conversation messages from WebSocket
  const handleConversationMessage = useCallback((event) => {
    if (typeof event.data === "string") {
      const msg = JSON.parse(event.data);
      if (msg.type === "assistant_text") {
        setLatestResponse(msg.content);
        setVoiceInstructions(msg.voice_instructions || "neutral");
        setAvatarInstructions(msg.avatar_instructions || "neutral");
      }
      if (msg.type === "status") {
        setStatus(msg.state);
      }
      return;
    }
    // Binary audio data
    playAudio(event.data, () => {
      sendJson({ type: "audio_playback_complete" });
    });
  }, [playAudio, sendJson]);

  // Create a new session
  const createSession = useCallback(async (scenarioId, accountId) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/session/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scenario_id: scenarioId,
          account_id: accountId,
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to create session: ${response.statusText}`);
      }

      const data = await response.json();
      setSessionId(data.session_id);
      setIsLoading(false);
      return data.session_id;
    } catch (err) {
      setError(err.message);
      setIsLoading(false);
      throw err;
    }
  }, []);

  // Connect to conversation WebSocket
  const connectConversation = useCallback(async (sessionIdToConnect) => {
    const id = sessionIdToConnect || sessionId;
    if (!id) {
      throw new Error("No session ID provided");
    }

    setStatus("connecting");

    try {
      await initAudioOutput();

      conversationWsRef.current = new WebSocket(
        `${WS_BASE_URL}/api/v1/session/${id}/conversation`
      );
      conversationWsRef.current.binaryType = "arraybuffer";

      conversationWsRef.current.onopen = async () => {
        console.log("WebSocket connected for session:", id);
        const stream = await initMicrophone();
        setupProcessor(stream, handleMicAudioData);
        setConnected(true);
        setStatus("listening");
      };

      conversationWsRef.current.onmessage = handleConversationMessage;

      conversationWsRef.current.onclose = () => {
        console.log("WebSocket closed");
        setConnected(false);
        setStatus("disconnected");
      };

      conversationWsRef.current.onerror = (error) => {
        console.error("WebSocket error:", error);
        setStatus("error");
      };
    } catch (err) {
      console.error("Failed to connect:", err);
      setStatus("error");
      throw err;
    }
  }, [sessionId, initAudioOutput, initMicrophone, setupProcessor, handleMicAudioData, handleConversationMessage]);

  // Toggle speaking (push-to-talk)
  const toggleSpeaking = useCallback(() => {
    if (!connected) return;
    const next = !speakingRef.current;
    speakingRef.current = next;
    setIsSpeaking(next);
    if (!next) {
      sendJson({ type: "end_of_utterance" });
    }
  }, [connected, sendJson]);

  // Send text message directly (skip STT)
  const sendTextMessage = useCallback((text) => {
    if (!connected || !text.trim()) return;
    sendJson({ type: "text_message", text: text.trim() });
  }, [connected, sendJson]);

  // Disconnect and cleanup
  const disconnect = useCallback(() => {
    // Close WebSocket
    conversationWsRef.current?.close();
    conversationWsRef.current = null;

    // Stop microphone stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    // Disconnect audio processor
    processorRef.current?.disconnect();
    processorRef.current = null;

    // Close audio contexts
    micCtxRef.current?.close();
    micCtxRef.current = null;
    audioCtxRef.current?.close();
    audioCtxRef.current = null;

    // Reset state
    setConnected(false);
    setIsSpeaking(false);
    speakingRef.current = false;
    setStatus("disconnected");
    setLatestResponse("");
    setVoiceInstructions("neutral");
    setAvatarInstructions("neutral");
  }, []);

  // Reset session (for creating a new one)
  const resetSession = useCallback(() => {
    disconnect();
    setSessionId(null);
    setStatus("idle");
    setError(null);
  }, [disconnect]);

  const value = {
    // State
    sessionId,
    status,
    connected,
    isSpeaking,
    latestResponse,
    voiceInstructions,
    avatarInstructions,
    isLoading,
    error,
    // Actions
    createSession,
    connectConversation,
    toggleSpeaking,
    sendTextMessage,
    disconnect,
    resetSession,
  };

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used within a SessionProvider");
  }
  return context;
}
