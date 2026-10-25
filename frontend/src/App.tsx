import { lazy } from "react";
import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import RequireAuth from "./components/RequireAuth";
import AuthPage from "./pages/AuthPage";
import Landing from "./pages/Landing";
import NotFound from "./pages/NotFound";

// Signed-in pages load on demand, so Landing and Log in don't download the map and chart libraries.
const Compare = lazy(() => import("./pages/Compare"));
const MyTrips = lazy(() => import("./pages/MyTrips"));
const NewTrip = lazy(() => import("./pages/NewTrip"));
const PlanDetail = lazy(() => import("./pages/PlanDetail"));
const Profile = lazy(() => import("./pages/Profile"));

export default function App() {
  const guard = (el: JSX.Element) => <RequireAuth>{el}</RequireAuth>;
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<AuthPage mode="login" />} />
        <Route path="/signup" element={<AuthPage mode="signup" />} />
        <Route path="/new" element={guard(<NewTrip />)} />
        <Route path="/trips" element={guard(<MyTrips />)} />
        <Route path="/trips/:id" element={guard(<Compare />)} />
        <Route path="/trips/:id/plan" element={guard(<PlanDetail />)} />
        <Route path="/profile" element={guard(<Profile />)} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
