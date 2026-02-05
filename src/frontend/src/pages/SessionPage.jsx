import { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useSession } from "../context/SessionContext";

export default function SessionPage() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const {
    status,
    connected,
    isSpeaking,
    latestResponse,
    connectConversation,
    toggleSpeaking,
    disconnect,
    resetSession,
  } = useSession();

  // Connect to WebSocket on mount
  useEffect(() => {
    if (!sessionId) return;

    connectConversation(sessionId).catch((err) => {
      console.error("Failed to connect:", err);
    });

    // Cleanup on unmount
    return () => {
      disconnect();
    };
  }, [sessionId]);

  const handleDisconnect = () => {
    resetSession();
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
