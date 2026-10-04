import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { EvidenceProvider } from "./components/EvidenceDrawer";
import { Layout } from "./components/Layout";
import { NotFoundBox } from "./components/ui";
import "./index.css";
import About from "./pages/About";
import Agents from "./pages/Agents";
import Impact from "./pages/Impact";
import Contributors from "./pages/Contributors";
import Campaigns from "./pages/Campaigns";
import ConditionPage from "./pages/ConditionPage";
import GenePage from "./pages/GenePage";
import MapPage from "./pages/MapPage";
import { GroupPage, MechanismPage, SymptomPage } from "./pages/ListPages";

const router = createBrowserRouter([
  // the map is the product: home, a condition, or a gene/symptom/group/mechanism lit up
  { path: "/", element: <MapPage /> },
  { path: "/c/:id", element: <MapPage /> },
  { path: "/explore/:kind/:id", element: <MapPage /> },
  // "Show the science": the detailed pages
  {
    element: <Layout />,
    children: [
      { path: "/about", element: <About /> },
      { path: "/agents", element: <Agents /> },
      { path: "/impact", element: <Impact /> },
      { path: "/contributors", element: <Contributors /> },
      { path: "/campaigns", element: <Campaigns /> },
      { path: "/c/:id/details", element: <ConditionPage /> },
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
