import { redirect } from "next/navigation";

/** The standalone measurement page became stage 2 of the workspace. */
export default function EnergyPage() {
  redirect("/workspace/measure");
}
