import { useRef, useState } from "react";

const TTS_SAMPLE_RATE = 24000;
const MIC_SAMPLE_RATE = 16000;

// ========== AUDIO CONVERSION UTILITIES ==========

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

// ========== AUDIO OUTPUT (TTS) ==========

async function initAudioOutput(audioCtxRef) {
  audioCtxRef.current = new AudioContext({ sampleRate: TTS_SAMPLE_RATE });
  await audioCtxRef.current.resume();
}

function playAudio(audioData, audioCtxRef, onPlaybackComplete) {
  const pcm16 = new Int16Array(audioData);
  const float32 = pcm16ToFloat32(pcm16);

  const ctx = audioCtxRef.current;
  const buffer = ctx.createBuffer(1, float32.length, TTS_SAMPLE_RATE);
  buffer.copyToChannel(float32, 0);

  const source = ctx.createBufferSource();
  source.buffer = buffer;
  source.connect(ctx.destination);

  source.onended = onPlaybackComplete;
  source.start();
}

// ========== MICROPHONE INPUT ==========

async function initMicrophone(micCtxRef) {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  micCtxRef.current = new AudioContext({ sampleRate: MIC_SAMPLE_RATE });
  await micCtxRef.current.resume();
  return stream;
}

function setupProcessor(stream, micCtxRef, processorRef, onAudioData) {
  const src = micCtxRef.current.createMediaStreamSource(stream);
  processorRef.current = micCtxRef.current.createScriptProcessor(4096, 1, 1);

  src.connect(processorRef.current);
  processorRef.current.connect(micCtxRef.current.destination);

  processorRef.current.onaudioprocess = (e) => {
    const input = e.inputBuffer.getChannelData(0);
    const pcm16 = float32ToPcm16(input);
    onAudioData(pcm16.buffer);
  };
}

// ========== WEBSOCKET HELPERS ==========

function sendJson(wsRef, message) {
  if (wsRef.current?.readyState === WebSocket.OPEN) {
    wsRef.current.send(JSON.stringify(message));
  }
}

// ========== MAIN COMPONENT ==========

export default function VoiceChat() {
  // WebSocket refs
  const sessionWsRef = useRef(null);
  const conversationWsRef = useRef(null);

  // Audio refs
  const audioCtxRef = useRef(null);
  const micCtxRef = useRef(null);
  const processorRef = useRef(null);
  const speakingRef = useRef(false);

  // State
  const [sessionId, setSessionId] = useState(null);
  const [connected, setConnected] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [latestResponse, setLatestResponse] = useState("");
  const [voice, setVoice] = useState("cosette");
  const [isLoading, setIsLoading] = useState(false)

  const handleMicAudioData = (audioBuffer) => {
    if (!speakingRef.current) return;
    if (!conversationWsRef.current || conversationWsRef.current.readyState !== WebSocket.OPEN) return;

    conversationWsRef.current.send(audioBuffer);
  };

  const connectSession = async () => {
    if (connected) return;
    setIsLoading(true)

    // Initialize audio contexts
    await initAudioOutput(audioCtxRef);

    // 1. Connect to session endpoint
    sessionWsRef.current = new WebSocket("ws://localhost:8000/session/connect");

    sessionWsRef.current.onopen = () => {
      // Send initial voice preference
      sendJson(sessionWsRef, { voice });
    };

    sessionWsRef.current.onmessage = (event) => {
      const msg = JSON.parse(event.data);

      if (msg.type === "session_created") {
        const newSessionId = msg.session_id;
        setSessionId(newSessionId);
        console.log("Session created:", newSessionId, "Voice:", msg.voice);
        setIsLoading(false)

        // 2. Connect to conversation endpoint with session ID
        conversationWsRef.current = new WebSocket("ws://localhost:8000/session/conversation");
        conversationWsRef.current.binaryType = "arraybuffer";

        conversationWsRef.current.onopen = async () => {
          // Send session ID
          sendJson(conversationWsRef, { session_id: newSessionId });

          // Setup microphone
          const stream = await initMicrophone(micCtxRef);
          setupProcessor(stream, micCtxRef, processorRef, handleMicAudioData);

          setConnected(true);
        };

        conversationWsRef.current.onmessage = handleConversationMessage;
      }

      if (msg.type === "voice_updated") {
        console.log("Voice updated to:", msg.voice);
      }
    };
  };

  const handleConversationMessage = (event) => {
    if (typeof event.data === "string") {
      const msg = JSON.parse(event.data);

      if (msg.type === "assistant_text") {
        setLatestResponse(msg.content);
      }

      return;
    }

    // Binary data = TTS audio
    playAudio(event.data, audioCtxRef, () => {
      sendJson(conversationWsRef, { type: "audio_playback_complete" });
    });
  };

  const toggleSpeaking = () => {
    if (!connected) return;

    const next = !speakingRef.current;
    speakingRef.current = next;
    setIsSpeaking(next);

    if (!next) {
      sendJson(conversationWsRef, { type: "end_of_utterance" });
    }
  };

  const disconnect = async () => {
    if (!sessionId) {
      console.log("No sessionId, cannot disconnect");
      return;
    }

    console.log("Starting disconnect for session:", sessionId);

    // Call disconnect endpoint
    try {
      console.log("Creating WebSocket to /session/disconnect");
      const disconnectWs = new WebSocket("ws://localhost:8000/session/disconnect");

      disconnectWs.onopen = () => {
        console.log("Disconnect WebSocket OPENED successfully");
        console.log("Sending session_id:", sessionId);
        sendJson({ current: disconnectWs }, { session_id: sessionId });
      };

      disconnectWs.onmessage = (event) => {
        console.log("Received message from disconnect endpoint:", event.data);
      };

      disconnectWs.onerror = (error) => {
        console.error("Disconnect WebSocket ERROR:", error);
      };

      disconnectWs.onclose = (event) => {
        console.log("Disconnect WebSocket CLOSED:", event.code, event.reason);
      };

      // Close all connections after delay
      setTimeout(() => {
        console.log("Timeout: closing all connections");
        disconnectWs.close();
        sessionWsRef.current?.close();
        conversationWsRef.current?.close();

        setConnected(false);
        setSessionId(null);
        setLatestResponse("");
      }, 500);

    } catch (error) {
      console.error("Error during disconnect:", error);
      // Fallback: close connections directly
      sessionWsRef.current?.close();
      conversationWsRef.current?.close();
      setConnected(false);
      setSessionId(null);
      setLatestResponse("");
    }
  };

  return (
    <div style={{ padding: 40, maxWidth: 600 }}>
      <h2>Voice Chat</h2>

      <div>
        {isLoading ? (
          <div>Loading...</div>
        ) : (
          <button onClick={connectSession} disabled={connected}>
            {connected ? "Connected" : "Connect"}
          </button>
        )}
        {!isLoading && connected && (
          <button onClick={disconnect} style={{ marginLeft: 10 }}>
            Disconnect
          </button>
        )}
      </div>

      <div style={{ marginTop: 20 }}>
        <button onClick={toggleSpeaking} disabled={!connected}>
          {isSpeaking ? "Stop Talking" : "Start Talking"}
        </button>
      </div>

      <div style={{ marginTop: 30 }}>
        <h3>Assistant</h3>
        <div
          style={{
            padding: 12,
            border: "1px solid #ccc",
            minHeight: 120,
            whiteSpace: "pre-wrap"
          }}
        >
          {latestResponse}
        </div>
      </div>
    </div>
  );
}
