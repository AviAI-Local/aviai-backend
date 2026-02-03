import { useState } from "react";
import { useNavigate } from "react-router-dom";

const API_BASE_URL = "http://localhost:8000";

export default function HomePage() {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleConnect = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/session/create`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          scenario_id: "e8a00ed4-4249-4a66-a41f-ec83fc25f731", // TODO: Allow user to select scenario
          account_id: "2b1e70d5-a191-4338-a8ff-77e69912530f",   // TODO: Get from auth
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to create session: ${response.statusText}`);
      }
      // console.log(data)

      const data = await response.json();
      const sessionId = data.session_id;

      // Navigate to session page
      navigate(`/session/${sessionId}`);
    } catch (err) {
      setError(err.message);
      setIsLoading(false);
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
