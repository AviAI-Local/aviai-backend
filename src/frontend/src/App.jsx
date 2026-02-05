import { BrowserRouter, Routes, Route } from "react-router-dom";
import { SessionProvider } from "./context/SessionContext";
import HomePage from "./pages/HomePage";
import SessionPage from "./pages/SessionPage";

function App() {
  return (
    <SessionProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/session/:sessionId" element={<SessionPage />} />
        </Routes>
      </BrowserRouter>
    </SessionProvider>
  );
}

export default App;