import { redirect } from "next/navigation";

/** The standalone pipeline page became stage 3 of the workspace. */
export default function CandidatesPage() {
  redirect("/workspace/improve");
}
