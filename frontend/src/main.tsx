import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// Fonts are bundled with the app, so nothing is fetched from outside the home network.
import "@fontsource-variable/fraunces/opsz.css";
import "@fontsource-variable/inter-tight/index.css";
import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
