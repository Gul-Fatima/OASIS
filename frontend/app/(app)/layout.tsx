import { AppShell } from "../../components/AppShell";
import { WorkspaceProvider } from "../../components/workspace/WorkspaceContext";

export default function AppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <WorkspaceProvider>
      <AppShell>{children}</AppShell>
    </WorkspaceProvider>
  );
}
