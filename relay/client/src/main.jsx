import React, { useState, useRef, useEffect } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useNavigate,
} from "react-router-dom";
import {
  QueryClient,
  QueryClientProvider,
  useQueryClient,
} from "@tanstack/react-query";
import { useApi } from "./hooks/useApi";
import { api } from "./api";
import Auth from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import Onboarding from "./pages/Onboarding";
import { Skeleton, ErrorState, Toast } from "./components/Common";
import "./styles/tokens.css";
const cache = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (n, e) => e.status !== 401 && n < 1,
      refetchOnWindowFocus: true,
    },
  },
});
function App() {
  const auth = useApi("/auth/me"),
    queryClient = useQueryClient(),
    navigate = useNavigate();
  const [message, setMessage] = useState("");
  const timer = useRef();
  useEffect(() => () => clearTimeout(timer.current), []);
  function toast(text) {
    setMessage(text);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setMessage(""), 3500);
  }
  async function logout() {
    try {
      await api("/auth/logout", { method: "POST" });
      queryClient.clear();
      navigate("/");
    } catch (e) {
      toast(e.message);
    }
  }
  function theme() {
    const d = document.documentElement;
    d.dataset.theme =
      getComputedStyle(d).getPropertyValue("--bg").trim() === "#0e0f11"
        ? "light"
        : "dark";
    localStorage.setItem("relay-theme", d.dataset.theme);
  }
  useEffect(() => {
    const theme = localStorage.getItem("relay-theme");
    if (theme) document.documentElement.dataset.theme = theme;
  }, []);
  if (auth.isPending) return <Skeleton />;
  if (auth.isError && auth.error.status !== 401)
    return <ErrorState query={auth} />;
  if (!auth.data) return <Auth />;
  const props = { user: auth.data, toast, logout, theme };
  return (
    <>
      <Routes>
        <Route path="/" element={<Dashboard {...props} />} />
        <Route path="/threads/:id" element={<Dashboard {...props} />} />
        <Route
          path="/accounts"
          element={
            auth.data.role === "assistant" ? (
              <Dashboard {...props} settings />
            ) : (
              <Navigate to="/" />
            )
          }
        />
        <Route
          path="/onboarding"
          element={
            auth.data.role === "assistant" ? (
              <Onboarding toast={toast} />
            ) : (
              <Navigate to="/" />
            )
          }
        />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
      <Toast message={message} />
    </>
  );
}
createRoot(document.getElementById("root")).render(
  <QueryClientProvider client={cache}>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </QueryClientProvider>,
);
