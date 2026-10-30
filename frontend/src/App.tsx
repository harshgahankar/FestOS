import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import Shell from "./components/Shell";
import Login from "./pages/Login";
import Home from "./pages/Home";
import Control from "./pages/Control";
import Audit from "./pages/Audit";
import People from "./pages/People";
import Participant from "./pages/Participant";
import ContingentDetail from "./pages/ContingentDetail";
import Accommodation from "./pages/Accommodation";
import Schedule from "./pages/Schedule";
import Inventory from "./pages/Inventory";
import Vendors from "./pages/Vendors";
import Disruptions from "./pages/Disruptions";
import { Spinner } from "./components/ui";

function ComingSoon({ module }: { module: string }) {
  return (
    <p className="paper rounded-sm border-2 border-crimson-dark/30 p-6 text-lg font-semibold text-ink/70">
      {module}
    </p>
  );
}

function ParticipantRoute() {
  const { id } = useParams();
  if (!id || !/^\d+$/.test(id)) return <ComeInvalid what="participant id" />;
  return <Participant id={Number(id)} />;
}

function ContingentDetailRoute() {
  const { rawId } = useParams();
  if (!rawId) return <ComeInvalid what="contingent id" />;
  return <ContingentDetail rawId={rawId} />;
}

function ComeInvalid({ what }: { what: string }) {
  return <p className="paper rounded-sm border-2 border-crimson-dark/30 p-6 text-destructive-red text-lg font-semibold text-ink/70">invalid {what} in URL</p>;
}

function Boot() {
  const { loading, user } = useAuth();
  if (loading)
    return (
      <div className="beige flex min-h-screen items-center justify-center gap-4">
        <Spinner label="reconnecting to FestOS…" />
      </div>
    );
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route
        path="/*"
        element={
          user ? (
            <Shell>
              <Routes>
                <Route path="/" element={user.role === "director" ? <Control /> : <Home />} />
                <Route path="/audit" element={<Audit />} />
                <Route path="/people" element={<People />} />
                <Route path="/people/:id" element={<ParticipantRoute />} />
                <Route path="/contingents/:rawId" element={<ContingentDetailRoute />} />
                <Route path="/accommodation" element={<Accommodation />} />
                <Route path="/schedule" element={<Schedule />} />
                <Route path="/inventory" element={<Inventory />} />
                <Route path="/vendors" element={<Vendors />} />
                <Route path="/disruptions" element={<Disruptions />} />
                <Route path="*" element={<ComingSoon module="Unknown page" />} />
              </Routes>
            </Shell>
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Boot />
    </AuthProvider>
  );
}
