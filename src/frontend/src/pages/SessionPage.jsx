import { useRef, useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";

const TTS_SAMPLE_RATE = 24000;
const MIC_SAMPLE_RATE = 16000;
const WS_BASE_URL = "ws://localhost:8000";

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

function sendJson(wsRef, message) {
  if (wsRef.current?.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify(message));
  }
}

export default function SessionPage() {
  const { sessionId } = useParams();
  const navigate = useNavigate();

  // WebSocket and audio refs
  const conversationWsRef = useRef(null);
  const audioCtxRef = useRef(null);
  const micCtxRef = useRef(null);
  const processorRef = useRef(null);
  const speakingRef = useRef(false);

  // State
  const [connected, setConnected] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [latestResponse, setLatestResponse] = useState("");
  const [status, setStatus] = useState("connecting");

  // Initialize audio output
  const initAudioOutput = async () => {
    audioCtxRef.current = new AudioContext({ sampleRate: TTS_SAMPLE_RATE });
    await audioCtxRef.current.resume();
  };

  // Play TTS audio
  const playAudio = (audioData, onComplete) => {
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
  };

  // Initialize microphone
  const initMicrophone = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    micCtxRef.current = new AudioContext({ sampleRate: MIC_SAMPLE_RATE });
    await micCtxRef.current.resume();
    return stream;
  };

  // Setup audio processor
  const setupProcessor = (stream, onAudioData) => {
    const src = micCtxRef.current.createMediaStreamSource(stream);
    processorRef.current = micCtxRef.current.createScriptProcessor(4096, 1, 1);
    src.connect(processorRef.current);
    processorRef.current.connect(micCtxRef.current.destination);
    processorRef.current.onaudioprocess = (e) => {
      const input = e.inputBuffer.getChannelData(0);
      const pcm16 = float32ToPcm16(input);
      onAudioData(pcm16.buffer);
    };
  };

  // Handle mic audio data
  const handleMicAudioData = (audioBuffer) => {
    if (!speakingRef.current) return;
    if (!conversationWsRef.current || conversationWsRef.current.readyState !== WebSocket.OPEN) return;
    conversationWsRef.current.send(audioBuffer);
  };

  // Handle conversation messages
  const handleConversationMessage = (event) => {
    if (typeof event.data === "string") {
      const msg = JSON.parse(event.data);
      if (msg.type === "assistant_text") {
        setLatestResponse(msg.content);
      }
      if (msg.type === "status") {
        setStatus(msg.state);
      }
      return;
    }
    // Binary audio data
    playAudio(event.data, () => {
      sendJson(conversationWsRef, { type: "audio_playback_complete" });
    });
  };

  // Connect to WebSocket
  useEffect(() => {
    if (!sessionId) return;

    const connect = async () => {
      try {
        await initAudioOutput();

        conversationWsRef.current = new WebSocket(`${WS_BASE_URL}/session/${sessionId}/conversation`);
        conversationWsRef.current.binaryType = "arraybuffer";

        conversationWsRef.current.onopen = async () => {
          console.log("WebSocket connected for session:", sessionId);
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
      }
    };

    connect();

    return () => {
      conversationWsRef.current?.close();
      processorRef.current?.disconnect();
      micCtxRef.current?.close();
      audioCtxRef.current?.close();
    };
  }, [sessionId]);

  // Toggle speaking
  const toggleSpeaking = () => {
    if (!connected) return;
    const next = !speakingRef.current;
    speakingRef.current = next;
    setIsSpeaking(next);
    if (!next) {
      sendJson(conversationWsRef, { type: "end_of_utterance" });
    }
  };

  // Disconnect and go back
  const handleDisconnect = async () => {
    try {
      // Notify backend to save conversation history
      await fetch(`${API_BASE_URL}/session/${sessionId}/cleanup`, {
        method: "POST"
      });
    } catch (err) {
      console.error("Cleanup failed:", err);
    }
    
    conversationWsRef.current?.close();
    navigate("/");
  };

  return (
    <div style={{ padding: 40, maxWidth: 600 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Session</h2>
        <button onClick={handleDisconnect}>
          Disconnect
        </button>
      </div>

      <p style={{ color: "#666", fontSize: 12 }}>
        ID: {sessionId}
      </p>

      <div style={{ marginTop: 20 }}>
        <span style={{
          padding: "4px 12px",
          borderRadius: 12,
          backgroundColor: connected ? "#e6f7e6" : "#ffe6e6",
          color: connected ? "#2e7d32" : "#c62828"
        }}>
          {status}
        </span>
      </div>

      <div style={{ marginTop: 30 }}>
        <button
          onClick={toggleSpeaking}
          disabled={!connected}
          style={{
            padding: "12px 24px",
            fontSize: 16,
            backgroundColor: isSpeaking ? "#ef5350" : "#4caf50",
            color: "white",
            border: "none",
            borderRadius: 8,
            cursor: connected ? "pointer" : "not-allowed",
          }}
        >
          {isSpeaking ? "Stop Talking" : "Start Talking"}
        </button>
      </div>

      <div style={{ marginTop: 30 }}>
        <h3>Assistant</h3>
        <div style={{
          padding: 16,
          border: "1px solid #ccc",
          borderRadius: 8,
          minHeight: 120,
          whiteSpace: "pre-wrap",
          backgroundColor: "#f9f9f9"
        }}>
          {latestResponse || "Waiting for response..."}
        </div>
      </div>
    </div>
  );
}
