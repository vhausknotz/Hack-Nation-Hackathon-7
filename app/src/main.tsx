import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { EvidenceProvider } from "./components/EvidenceDrawer";
import { Layout } from "./components/Layout";
import { NotFoundBox } from "./components/ui";
import "./index.css";
import About from "./pages/About";
import ConditionPage from "./pages/ConditionPage";
import GenePage from "./pages/GenePage";
import Home from "./pages/Home";
import { GroupPage, MechanismPage, SymptomPage } from "./pages/ListPages";

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/about", element: <About /> },
      { path: "/c/:id", element: <ConditionPage /> },
      { path: "/g/:symbol", element: <GenePage /> },
      { path: "/s/:id", element: <SymptomPage /> },
      { path: "/group/:id", element: <GroupPage /> },
      { path: "/m/:id", element: <MechanismPage /> },
      { path: "*", element: <NotFoundBox what="this page" /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <EvidenceProvider>
      <RouterProvider router={router} />
    </EvidenceProvider>
  </StrictMode>,
);
