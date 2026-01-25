import { useRef, useState } from "react";

/*
 * VoiceChat Component - Voice conversation with AI assistant
 *
 * Connection Flow:
 * 1. User clicks "Connect" -> connectSession() is called
 * 2. Client connects to /session/connect WebSocket
 * 3. Server creates session, sends back session_id
 * 4. Client connects to /session/conversation with session_id
 * 5. Microphone is initialized, ready for voice input
 *
 * Voice Flow:
 * 1. User clicks "Start Talking" -> toggleSpeaking()
 * 2. Mic audio is captured and sent to server via handleMicAudioData()
 * 3. User clicks "Stop Talking" -> sends "end_of_utterance"
 * 4. Server transcribes audio, generates response, sends text + TTS audio
 * 5. Client displays text and plays audio
 * 6. When audio finishes, client sends "audio_playback_complete"
 * 7. Server goes back to listening state
 *
 * Ping/Pong Heartbeat:
 * - Client sends ping every 15 seconds to keep connection alive
 * - Server has 30s timeout, sends its own ping as backup safety net
 * - If connection drops, onclose handler auto-disconnects everything
 */

const TTS_SAMPLE_RATE = 24000;  // Sample rate for TTS audio from server
const MIC_SAMPLE_RATE = 16000;  // Sample rate for microphone input

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
  // ==================== REFS ====================
  // WebSocket connections (refs because we don't want re-renders when they change)
  const sessionWsRef = useRef(null);       // /session/connect - session management
  const conversationWsRef = useRef(null);  // /session/conversation - voice data
  const pingIntervalRef = useRef(null);    // Interval ID for ping heartbeat

  // Audio contexts and processor
  const audioCtxRef = useRef(null);   // For playing TTS audio from server
  const micCtxRef = useRef(null);     // For capturing microphone input
  const processorRef = useRef(null);  // Audio processor that sends mic data
  const speakingRef = useRef(false);  // Ref for immediate access in audio callback

  // ==================== STATE ====================
  const [sessionId, setSessionId] = useState(null);      // Server-assigned session ID
  const [connected, setConnected] = useState(false);     // Are we fully connected?
  const [isSpeaking, setIsSpeaking] = useState(false);   // Is user currently talking?
  const [latestResponse, setLatestResponse] = useState(""); // Assistant's latest text
  const [voice, setVoice] = useState("serena");         // TTS voice preference
  const [isLoading, setIsLoading] = useState(false)      // Loading state for connect

  // ==================== HANDLE MIC AUDIO DATA ====================
  // Called continuously by the audio processor when user is talking
  // Sends raw audio chunks to server for transcription
  const handleMicAudioData = (audioBuffer) => {
    // Only send audio when user is actively speaking (button pressed)
    if (!speakingRef.current) return;
    // Make sure WebSocket is connected
    if (!conversationWsRef.current || conversationWsRef.current.readyState !== WebSocket.OPEN) return;

    // Send raw PCM audio bytes to server
    // Server accumulates these in a buffer until "end_of_utterance" is received
    conversationWsRef.current.send(audioBuffer);
  };

  // ==================== CONNECT SESSION ====================
  // This function establishes the connection to the server.
  // It creates TWO WebSocket connections:
  //   1. sessionWs (/session/connect) - for session management and keepalive
  //   2. conversationWs (/session/conversation) - for actual voice data exchange
  const connectSession = async () => {
    // Prevent duplicate connections
    if (connected) return;
    setIsLoading(true)

    // Initialize audio context for playing TTS audio from server
    await initAudioOutput(audioCtxRef);

    // STEP 1: Connect to session endpoint
    // This creates a new session on the server and returns a session_id
    sessionWsRef.current = new WebSocket("ws://localhost:8000/session/connect");

    // When session WebSocket opens successfully
    sessionWsRef.current.onopen = () => {
      // Send initial config (voice preference) to server
      // Server uses this to configure TTS voice for this session
      sendJson(sessionWsRef, { voice });

      // Start ping interval every 15 seconds to keep connection alive
      // This prevents the server from thinking the client disconnected
      // Server has 30s timeout, so 15s ping ensures we stay connected
      pingIntervalRef.current = setInterval(() => {
        sendJson(sessionWsRef, { type: "ping" });
      }, 15000);
    };

    // Handle session WebSocket close (server disconnected or network issue)
    // This triggers auto-disconnect: clean up everything and reset UI
    sessionWsRef.current.onclose = () => {
      console.log("Session WebSocket closed by server");

      // Stop the ping interval since connection is closed
      clearInterval(pingIntervalRef.current);

      // Also close the conversation WebSocket since session is dead
      conversationWsRef.current?.close();

      // Reset all state to disconnected
      speakingRef.current = false;
      setIsSpeaking(false);
      setConnected(false);
      setSessionId(null);
      setLatestResponse("");
      setIsLoading(false);
    };

    // Handle session WebSocket errors (network failure, etc.)
    // Clean up ping interval and close connection on error
    sessionWsRef.current.onerror = (error) => {
      console.error("Session WebSocket error:", error);
      clearInterval(pingIntervalRef.current);
      sessionWsRef.current?.close(); // This will trigger onclose handler above
    };

    // Handle messages from session WebSocket
    sessionWsRef.current.onmessage = (event) => {
      const msg = JSON.parse(event.data);

      // Server sends ping to check if client is alive (backup safety net)
      // Respond with pong to let server know we're still here
      if (msg.type === "ping") {
        sendJson(sessionWsRef, { type: "pong" });
        return;
      }

      // Server created session successfully, now we can start conversation
      if (msg.type === "session_created") {
        const newSessionId = msg.session_id;
        setSessionId(newSessionId);
        console.log("Session created:", newSessionId, "Voice:", msg.voice);
        setIsLoading(false)

        // STEP 2: Connect to conversation endpoint
        // This is a separate WebSocket for voice data (audio in/out)
        // We need session_id to link this conversation to our session
        conversationWsRef.current = new WebSocket("ws://localhost:8000/session/conversation");
        // Set to arraybuffer so we can receive binary audio data
        conversationWsRef.current.binaryType = "arraybuffer";

        // When conversation WebSocket opens, authenticate with session_id
        conversationWsRef.current.onopen = async () => {
          // Tell server which session this conversation belongs to
          // Server uses this to lookup the correct Session instance
          sendJson(conversationWsRef, { session_id: newSessionId });

          // Initialize microphone and start capturing audio
          // Audio data flows: Mic -> Processor -> handleMicAudioData -> Server
          const stream = await initMicrophone(micCtxRef);
          setupProcessor(stream, micCtxRef, processorRef, handleMicAudioData);

          // Now fully connected and ready for voice conversation
          setConnected(true);
        };

        // Handle messages from conversation WebSocket (text responses + audio)
        conversationWsRef.current.onmessage = handleConversationMessage;

        // If conversation WebSocket closes, stop speaking
        conversationWsRef.current.onclose = () => {
          console.log("Conversation WebSocket closed");
          speakingRef.current = false;
          setIsSpeaking(false);
        };

        conversationWsRef.current.onerror = (error) => {
          console.error("Conversation WebSocket error:", error);
        };
      }

      // Server confirms voice was changed (response to update_voice request)
      if (msg.type === "voice_updated") {
        console.log("Voice updated to:", msg.voice);
      }
    };
  };

  // ==================== HANDLE CONVERSATION MESSAGES ====================
  // This handles two types of messages from server:
  // 1. JSON string - text response from assistant
  // 2. Binary data - TTS audio to play
  const handleConversationMessage = (event) => {
    // JSON message = text response
    if (typeof event.data === "string") {
      const msg = JSON.parse(event.data);

      // Display assistant's text response in the UI
      if (msg.type === "assistant_text") {
        setLatestResponse(msg.content);
      }

      return;
    }

    // Binary data = TTS audio from server
    // Play the audio, and when done, notify server so it can go back to listening
    playAudio(event.data, audioCtxRef, () => {
      // Tell server we finished playing audio
      // Server will then switch back to "listening" state
      sendJson(conversationWsRef, { type: "audio_playback_complete" });
    });
  };

  // ==================== TOGGLE SPEAKING ====================
  // User presses button to start/stop talking
  // When stopped, sends "end_of_utterance" to tell server to process the audio
  const toggleSpeaking = () => {
    if (!connected) return;

    const next = !speakingRef.current;
    speakingRef.current = next;  // Ref for immediate access in audio callback
    setIsSpeaking(next);         // State for UI update

    // When user stops talking, tell server the audio is complete
    // Server will then transcribe the audio and generate a response
    if (!next) {
      sendJson(conversationWsRef, { type: "end_of_utterance" });
    }
  };

  // ==================== DISCONNECT ====================
  // Manually disconnect from server (user clicks Disconnect button)
  // Calls server's disconnect endpoint and cleans up all connections
  const disconnect = async () => {
    if (!sessionId) {
      console.log("No sessionId, cannot disconnect");
      return;
    }

    console.log("Starting disconnect for session:", sessionId);

    // Tell server to cleanup this session
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

      // Wait a bit for server to process disconnect, then cleanup client-side
      // This ensures server has time to receive and handle the disconnect request
      setTimeout(() => {
        console.log("Timeout: closing all connections");
        clearInterval(pingIntervalRef.current);  // Stop ping heartbeat
        disconnectWs.close();                     // Close disconnect WebSocket
        sessionWsRef.current?.close();            // Close session WebSocket
        conversationWsRef.current?.close();       // Close conversation WebSocket

        // Reset all state to disconnected
        setConnected(false);
        setSessionId(null);
        setLatestResponse("");
      }, 500);

    } catch (error) {
      console.error("Error during disconnect:", error);
      // Fallback: if disconnect endpoint fails, still cleanup client-side
      clearInterval(pingIntervalRef.current);
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
