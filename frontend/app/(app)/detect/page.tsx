import { redirect } from "next/navigation";

/** The standalone detection page became stage 1 of the workspace. */
export default function DetectPage() {
  redirect("/workspace/scan");
}
