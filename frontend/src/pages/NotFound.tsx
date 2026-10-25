import { Link } from "react-router-dom";
import { PageTitle } from "../components/ui";

export default function NotFound() {
  return (
    <div>
      <PageTitle sub="That page doesn't exist.">Not found</PageTitle>
      <Link to="/" className="btn-primary">Go home</Link>
    </div>
  );
}
