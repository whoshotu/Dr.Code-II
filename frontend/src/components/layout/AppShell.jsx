import { NavLink, Outlet } from "react-router-dom";
import { Activity, Bug, FileCode2, FolderGit2, PlugZap, Settings, ShieldCheck } from "lucide-react";

const navItems = [
  { label: "Dashboard", to: "/", icon: Activity, testId: "nav-dashboard-link" },
  { label: "Repo Fixes", to: "/repository-fixes", icon: FolderGit2, testId: "nav-repository-fixes-link" },
  { label: "Reports", to: "/reports", icon: FileCode2, testId: "nav-reports-link" },
  { label: "Governance", to: "/governance", icon: ShieldCheck, testId: "nav-governance-link" },
  { label: "Integrations", to: "/integrations", icon: PlugZap, testId: "nav-integrations-link" },
  { label: "Settings", to: "/settings", icon: Settings, testId: "nav-settings-link" },
  { label: "Archive", to: "/trash", icon: Bug, testId: "nav-trash-link" },
];

export const AppShell = () => {
  return (
    <div className="grid-atmosphere min-h-screen bg-background text-foreground">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 md:px-6 lg:flex-row lg:gap-8 lg:py-8">
        <aside className="pulse-border rounded-xl border border-border bg-card/70 p-4 backdrop-blur-xl lg:w-72 lg:sticky lg:top-6 lg:h-[calc(100vh-3rem)]">
          <div className="mb-8 space-y-2">
            <div className="inline-flex items-center gap-2 rounded-full border border-primary/40 bg-primary/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-primary" data-testid="brand-badge">
              <Bug className="h-3.5 w-3.5" />
              Code Surgeon
            </div>
            <h1 className="text-3xl font-bold tracking-tight" data-testid="app-title">Dr.Code-II</h1>
            <p className="text-sm text-muted-foreground" data-testid="app-subtitle">
              AI-powered code diagnostics with tactical fixes.
            </p>
          </div>

          <nav className="flex flex-wrap gap-2 lg:flex-col" data-testid="main-navigation">
            {navItems.map(({ label, to, icon: Icon, testId }) => (
              <NavLink
                key={to}
                to={to}
                data-testid={testId}
                className={({ isActive }) =>
                  `slide-up flex h-10 items-center gap-2 rounded-lg border px-3 text-sm font-medium transition-all duration-200 ${
                    isActive
                      ? "border-primary/50 bg-primary/15 text-foreground shadow-[0_0_12px_rgba(0,229,255,0.25)]"
                      : "border-border bg-background/60 text-muted-foreground hover:border-primary/30 hover:text-foreground"
                  }`
                }
              >
                <Icon className="h-4 w-4" />
                {label}
              </NavLink>
            ))}
          </nav>
        </aside>

        <main className="w-full" data-testid="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
};