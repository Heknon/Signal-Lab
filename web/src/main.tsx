import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/500.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./styles/app.css";
import { LabProvider } from "./context";
import Home from "./pages/Home";
import LessonPage from "./pages/LessonPage";
import StackPage from "./pages/StackPage";
import CommandPalette from "./components/CommandPalette";
import ScenarioDrawer from "./components/ScenarioDrawer";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <LabProvider>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/learn/:pack/:slug" element={<LessonPage />} />
          <Route path="/stack" element={<StackPage />} />
          <Route path="*" element={<Home />} />
        </Routes>
        <CommandPalette />
        <ScenarioDrawer />
      </LabProvider>
    </BrowserRouter>
  </StrictMode>,
);
