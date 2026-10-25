import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import RequireAuth from "./components/RequireAuth";
import AuthPage from "./pages/AuthPage";
import Compare from "./pages/Compare";
import Landing from "./pages/Landing";
import MyTrips from "./pages/MyTrips";
import NewTrip from "./pages/NewTrip";
import NotFound from "./pages/NotFound";
import PlanDetail from "./pages/PlanDetail";
import Profile from "./pages/Profile";

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
