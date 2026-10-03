import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <div className="p-6 text-ink">Трапезная МДА</div>
  </StrictMode>,
);
