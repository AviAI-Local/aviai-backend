import { useRef, useState } from "react";

export default function VoiceChat() {
  const wsRef = useRef(null);
  const audioCtxRef = useRef(null);
  const micCtxRef = useRef(null);
  const processorRef = useRef(null);
  const allowMicRef = useRef(true);
  const speakingRef = useRef(false);

  const [isSpeaking, setIsSpeaking] = useState(false);
  const [connected, setConnected] = useState(false);
  const [latestResponse, setLatestResponse] = useState("");

  const TTS_SAMPLE_RATE = 24000;
  const MIC_SAMPLE_RATE = 16000;

  const start = async () => {
    if (connected) return;

    // ---------- OUTPUT AUDIO ----------
    audioCtxRef.current = new AudioContext({ sampleRate: TTS_SAMPLE_RATE });
    await audioCtxRef.current.resume();

    // ---------- WEBSOCKET ----------
    wsRef.current = new WebSocket("ws://localhost:8000/voice");
    wsRef.current.binaryType = "arraybuffer";

    wsRef.current.onopen = () => {
      setConnected(true);
    };

    wsRef.current.onmessage = (event) => {
      if (typeof event.data === "string") {
        const msg = JSON.parse(event.data);

        if (msg.type === "status") {
          allowMicRef.current = msg.state === "listening";
        }

        if (msg.type === "assistant_text") {
          setLatestResponse(msg.content);
        }

        return;
      }

      // ---------- PLAY TTS AUDIO ----------
      const pcm = new Int16Array(event.data);
      const f32 = new Float32Array(pcm.length);

      for (let i = 0; i < pcm.length; i++) {
        f32[i] = pcm[i] / 32768;
      }

      const ctx = audioCtxRef.current;
      const buffer = ctx.createBuffer(1, f32.length, TTS_SAMPLE_RATE);
      buffer.copyToChannel(f32, 0);

      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);

      source.onended = () => {
        wsRef.current?.send(
          JSON.stringify({ type: "audio_playback_complete" })
        );
      };

      source.start();
    };

    // ---------- MIC ----------
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    micCtxRef.current = new AudioContext({ sampleRate: MIC_SAMPLE_RATE });
    await micCtxRef.current.resume();

    const src = micCtxRef.current.createMediaStreamSource(stream);

    processorRef.current =
      micCtxRef.current.createScriptProcessor(4096, 1, 1);

    src.connect(processorRef.current);
    processorRef.current.connect(micCtxRef.current.destination);

    processorRef.current.onaudioprocess = (e) => {
      if (!speakingRef.current) return;
      if (!allowMicRef.current) return;
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

      const input = e.inputBuffer.getChannelData(0);
      const pcm = new Int16Array(input.length);

      for (let i = 0; i < input.length; i++) {
        const s = Math.max(-1, Math.min(1, input[i]));
        pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }

      wsRef.current.send(pcm.buffer);
    };
  };

  const toggleSpeaking = () => {
    if (!connected) return;

    const next = !speakingRef.current;
    speakingRef.current = next;
    setIsSpeaking(next);

    if (!next) {
      wsRef.current?.send(
        JSON.stringify({ type: "end_of_utterance" })
      );
    }
  };

  return (
    <div style={{ padding: 40, maxWidth: 600 }}>
      <button onClick={start} disabled={connected}>
        {connected ? "Connected" : "Connect"}
      </button>

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
