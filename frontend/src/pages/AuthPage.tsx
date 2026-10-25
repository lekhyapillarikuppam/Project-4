import { PageTitle } from "../components/ui";

export default function AuthPage({ mode }: { mode: "login" | "signup" }) {
  return <PageTitle>{mode === "login" ? "Log in" : "Sign up"}</PageTitle>;
}
