import { Link } from "react-router-dom";
import { PageTitle } from "../components/ui";
import { useDocumentTitle } from "../lib/title";

export default function NotFound() {
  useDocumentTitle("Not found");
  return (
    <div>
      <PageTitle sub="That page doesn't exist.">Not found</PageTitle>
      <Link to="/" className="btn-primary">Go home</Link>
    </div>
  );
}
