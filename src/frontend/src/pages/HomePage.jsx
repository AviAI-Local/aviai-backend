import { useNavigate } from "react-router-dom";
import { useSession } from "../context/SessionContext";

export default function HomePage() {
  const navigate = useNavigate();
  const { createSession, isLoading, error } = useSession();

  const handleConnect = async () => {
    try {
      const sessionId = await createSession(
        "820a81ee-9119-4533-b1ec-c5b5f52ac014", // TODO: Allow user to select scenario
        "73ab2577-92b1-4b74-8def-22ff3e2f30bc"  // TODO: Get from auth
      );
      navigate(`/session/${sessionId}`);
    } catch (err) {
      // Error is already set in context
      console.error("Failed to create session:", err);
    }
  };

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      minHeight: "100vh",
      padding: 40
    }}>
      <h1>Cognitive Interview</h1>
      <p style={{ marginBottom: 30, color: "#666" }}>
        Click connect to start a new interview session
      </p>

      {error && (
        <div style={{ color: "red", marginBottom: 20 }}>
          {error}
        </div>
      )}

      <button
        onClick={handleConnect}
        disabled={isLoading}
        style={{
          padding: "12px 32px",
          fontSize: 18,
          cursor: isLoading ? "not-allowed" : "pointer",
        }}
      >
        {isLoading ? "Connecting..." : "Connect"}
      </button>
    </div>
  );
}
