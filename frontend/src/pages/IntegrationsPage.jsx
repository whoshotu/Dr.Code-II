import { useEffect, useState } from "react";
import { Copy, Github, CheckCircle2, XCircle } from "lucide-react";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { api } from "@/services/api";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
const WEBHOOK_URL = `${BACKEND_URL}/api/integrations/git/webhook`;

export default function IntegrationsPage() {
  const [events, setEvents] = useState([]);
  const [githubStatus, setGithubStatus] = useState(null);
  const [gitPayload, setGitPayload] = useState({ repository: "", event_type: "", branch: "", commit_sha: "" });
  const [ciPayload, setCiPayload] = useState({ pipeline: "", status: "", branch: "", commit_sha: "" });

  const loadAll = async () => {
    const [eventsData, statusData] = await Promise.all([
      api.getIntegrationEvents(),
      api.getGithubStatus(),
    ]);
    setEvents(eventsData);
    setGithubStatus(statusData);
  };

  useEffect(() => { loadAll(); }, []);

  const sendGitEvent = async () => {
    await api.sendGitWebhook(gitPayload);
    toast.success("Git webhook event accepted");
    loadAll();
  };

  const sendCiEvent = async () => {
    await api.sendCiEvent(ciPayload);
    toast.success("CI pipeline event accepted");
    loadAll();
  };

  const copyWebhookUrl = () => {
    navigator.clipboard.writeText(WEBHOOK_URL);
    toast.success("Webhook URL copied to clipboard");
  };

  const statusIcon = (ok) => ok
    ? <CheckCircle2 className="h-4 w-4 text-teal-400" />
    : <XCircle className="h-4 w-4 text-rose-500" />;

  const eventStatusColor = (status) => {
    if (status === "analyzed") return "text-teal-400";
    if (status === "error") return "text-rose-500";
    if (status?.startsWith("skipped")) return "text-amber-400";
    return "text-muted-foreground";
  };

  return (
    <section className="space-y-6" data-testid="integrations-page">
      <div className="rounded-xl border border-border bg-card/70 p-6" data-testid="integrations-header-card">
        <h2 className="text-4xl font-bold tracking-tight" data-testid="integrations-heading">Integrations</h2>
        <p className="mt-2 text-base text-muted-foreground" data-testid="integrations-subheading">
          Connect DR.CODE to GitHub for automatic PR analysis. Test stubs available below.
        </p>
      </div>

      {/* GitHub Live Status */}
      <Card data-testid="github-status-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2" data-testid="github-status-title">
            <Github className="h-5 w-5" /> GitHub Connection
          </CardTitle>
          <CardDescription data-testid="github-status-description">
            Configure your GitHub token in Settings → GitHub Integration.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {githubStatus ? (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2" data-testid="github-status-grid">
              <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-3 text-sm" data-testid="github-token-status">
                {statusIcon(githubStatus.token_configured)}
                <span>PAT Token</span>
                {githubStatus.token_configured && (
                  <code className="ml-auto font-mono text-xs text-muted-foreground" data-testid="github-token-masked">{githubStatus.token_masked}</code>
                )}
              </div>
              <div className="flex items-center gap-2 rounded-lg border border-border bg-background p-3 text-sm" data-testid="github-secret-status">
                {statusIcon(githubStatus.webhook_secret_configured)}
                <span>Webhook Secret</span>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground" data-testid="github-status-loading">Loading…</p>
          )}

          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground" data-testid="webhook-url-label">Your Webhook URL (paste into GitHub repo settings)</p>
            <div className="flex items-center gap-2">
              <code className="flex-1 truncate rounded-md border border-border bg-background px-3 py-2 font-mono text-xs" data-testid="webhook-url-display">
                {WEBHOOK_URL}
              </code>
              <Button data-testid="copy-webhook-url-button" className="h-9 shrink-0" variant="outline" onClick={copyWebhookUrl}>
                <Copy className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <details className="rounded-lg border border-border" data-testid="github-setup-guide">
            <summary className="cursor-pointer px-4 py-3 text-sm font-medium" data-testid="github-setup-guide-summary">
              📋 Setup Guide
            </summary>
            <ol className="space-y-2 px-4 pb-4 pt-2 text-sm text-muted-foreground">
              <li data-testid="setup-step-1">1. Go to <strong>Settings → GitHub Integration</strong> and paste a PAT with <code>pull_requests: write</code> scope.</li>
              <li data-testid="setup-step-2">2. Optionally set a Webhook Secret (recommended for production).</li>
              <li data-testid="setup-step-3">3. In your GitHub repo → <strong>Settings → Webhooks → Add webhook</strong>.</li>
              <li data-testid="setup-step-4">4. Paste the URL above. Set Content-Type to <code>application/json</code>. Select <strong>Pull requests</strong> events.</li>
              <li data-testid="setup-step-5">5. Open a PR — DR.CODE will auto-analyze and post inline comments.</li>
            </ol>
          </details>
        </CardContent>
      </Card>

      {/* Test stubs */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card data-testid="git-webhook-card">
          <CardHeader><CardTitle data-testid="git-webhook-title">Git Webhook Stub</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Input data-testid="git-repository-input" className="h-10" value={gitPayload.repository} onChange={(e) => setGitPayload({ ...gitPayload, repository: e.target.value })} placeholder="Repository" />
            <Input data-testid="git-event-type-input" className="h-10" value={gitPayload.event_type} onChange={(e) => setGitPayload({ ...gitPayload, event_type: e.target.value })} placeholder="Event type" />
            <Input data-testid="git-branch-input" className="h-10" value={gitPayload.branch} onChange={(e) => setGitPayload({ ...gitPayload, branch: e.target.value })} placeholder="Branch" />
            <Input data-testid="git-commit-input" className="h-10" value={gitPayload.commit_sha} onChange={(e) => setGitPayload({ ...gitPayload, commit_sha: e.target.value })} placeholder="Commit SHA" />
            <Button data-testid="send-git-event-button" className="h-10" onClick={sendGitEvent}>Send Git Event</Button>
          </CardContent>
        </Card>

        <Card data-testid="ci-event-card">
          <CardHeader><CardTitle data-testid="ci-event-title">CI Event Stub</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <Input data-testid="ci-pipeline-input" className="h-10" value={ciPayload.pipeline} onChange={(e) => setCiPayload({ ...ciPayload, pipeline: e.target.value })} placeholder="Pipeline" />
            <Input data-testid="ci-status-input" className="h-10" value={ciPayload.status} onChange={(e) => setCiPayload({ ...ciPayload, status: e.target.value })} placeholder="Status" />
            <Input data-testid="ci-branch-input" className="h-10" value={ciPayload.branch} onChange={(e) => setCiPayload({ ...ciPayload, branch: e.target.value })} placeholder="Branch" />
            <Input data-testid="ci-commit-input" className="h-10" value={ciPayload.commit_sha} onChange={(e) => setCiPayload({ ...ciPayload, commit_sha: e.target.value })} placeholder="Commit SHA" />
            <Button data-testid="send-ci-event-button" className="h-10" variant="secondary" onClick={sendCiEvent}>Send CI Event</Button>
          </CardContent>
        </Card>
      </div>

      {/* Events log */}
      <Card data-testid="integration-events-card">
        <CardHeader><CardTitle data-testid="integration-events-title">Recent Integration Events</CardTitle></CardHeader>
        <CardContent className="space-y-3" data-testid="integration-events-list">
          {events.length === 0 ? (
            <p className="text-sm text-muted-foreground" data-testid="integration-events-empty">No events received yet.</p>
          ) : (
            events.map((event) => (
              <div key={event.event_id} className="rounded-lg border border-border bg-background p-3 text-sm" data-testid={`integration-event-${event.event_id}`}>
                <div className="flex items-center gap-2">
                  <p className="font-medium" data-testid={`integration-event-source-${event.event_id}`}>{event.source} · {event.event_type}</p>
                  <Badge variant="outline" className="ml-auto" data-testid={`integration-event-badge-${event.event_id}`}>{event.source}</Badge>
                </div>
                <p className={`text-xs mt-1 ${eventStatusColor(event.status)}`} data-testid={`integration-event-status-${event.event_id}`}>
                  {event.status}
                </p>
                {event.details?.fix_count !== undefined && (
                  <p className="mt-1 text-xs text-muted-foreground" data-testid={`integration-event-fixes-${event.event_id}`}>
                    {event.details.fix_count} fixes · {event.details.comment_count} comments posted · {event.details.file_count} files scanned
                  </p>
                )}
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </section>
  );
}