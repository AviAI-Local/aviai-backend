import { useRef } from "react";

export default function VoiceChat() {
  const wsRef = useRef(null);
  const audioCtxRef = useRef(null);
  const micCtxRef = useRef(null);
  const allowMicRef = useRef(true);
  const processorRef = useRef(null);

  const TTS_SAMPLE_RATE = 24000;

  const start = async () => {
    audioCtxRef.current = new AudioContext({ sampleRate: TTS_SAMPLE_RATE });
    await audioCtxRef.current.resume();

    wsRef.current = new WebSocket("ws://localhost:8000/voice");
    wsRef.current.binaryType = "arraybuffer";

    wsRef.current.onmessage = (event) => {
      if (typeof event.data === "string") {
        const msg = JSON.parse(event.data);
        if (msg.type === "status") {
          allowMicRef.current = msg.state === "listening";
        }
        return;
      }

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

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    micCtxRef.current = new AudioContext({ sampleRate: 16000 });
    await micCtxRef.current.resume();

    const src = micCtxRef.current.createMediaStreamSource(stream);

    processorRef.current =
      micCtxRef.current.createScriptProcessor(4096, 1, 1);

    src.connect(processorRef.current);
    processorRef.current.connect(micCtxRef.current.destination);

    processorRef.current.onaudioprocess = (e) => {
  if (!allowMicRef.current) return;
  if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

  const input = e.inputBuffer.getChannelData(0);

  // Float32 → Int16 PCM
  const pcm = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }

  wsRef.current.send(pcm.buffer);
};

  };

  return (
    <div style={{ padding: 40 }}>
      <button onClick={start}>Start Talking</button>
    </div>
  );
}
