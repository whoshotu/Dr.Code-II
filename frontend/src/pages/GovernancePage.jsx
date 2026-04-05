import { useEffect, useMemo, useState } from "react";
import { toast } from "@/components/ui/sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/services/api";

const providerOptions = ["ollama", "openai_compatible", "gemini", "anthropic"];

export default function GovernancePage() {
  const [actor, setActor] = useState({ actorId: "owner-admin", role: "admin" });
  const [policy, setPolicy] = useState({
    version: 1,
    allowed_providers: providerOptions,
    blocked_patterns: ["rm -rf", "drop database", "private_key"],
    max_code_length: 70000,
    require_reviewer_for_high_risk: true,
    min_transparency_confidence: 0.45,
    updated_by: "system",
    updated_at: "",
  });
  const [blockedPatternText, setBlockedPatternText] = useState("rm -rf, drop database, private_key");
  const [auditLogs, setAuditLogs] = useState([]);
  const [securityEvents, setSecurityEvents] = useState([]);
  const [qualityMetrics, setQualityMetrics] = useState([]);

  const policySummary = useMemo(
    () => `${policy.allowed_providers.length} providers allowed · max ${policy.max_code_length} chars`,
    [policy.allowed_providers.length, policy.max_code_length],
  );

  const refreshAll = async () => {
    const [policyData, auditData, securityData, metricsData] = await Promise.all([
      api.getGovernancePolicy(),
      api.getGovernanceAuditLogs(),
      api.getSecurityEvents(),
      api.getQualityMetrics(),
    ]);
    setPolicy(policyData);
    setBlockedPatternText((policyData.blocked_patterns || []).join(", "));
    setAuditLogs(auditData);
    setSecurityEvents(securityData);
    setQualityMetrics(metricsData);
  };

  useEffect(() => {
    refreshAll();
  }, []);

  const toggleProvider = (provider) => {
    setPolicy((prev) => {
      const exists = prev.allowed_providers.includes(provider);
      return {
        ...prev,
        allowed_providers: exists
          ? prev.allowed_providers.filter((item) => item !== provider)
          : [...prev.allowed_providers, provider],
      };
    });
  };

  const savePolicy = async () => {
    const patterns = blockedPatternText
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    if (policy.allowed_providers.length === 0) {
      toast.error("Select at least one allowed provider.");
      return;
    }
    try {
      const updated = await api.updateGovernancePolicy(
        {
          allowed_providers: policy.allowed_providers,
          blocked_patterns: patterns,
          max_code_length: Number(policy.max_code_length),
          require_reviewer_for_high_risk: !!policy.require_reviewer_for_high_risk,
          min_transparency_confidence: Number(policy.min_transparency_confidence),
        },
        actor,
      );
      setPolicy(updated);
      setBlockedPatternText((updated.blocked_patterns || []).join(", "));
      toast.success("Governance policy updated");
      refreshAll();
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Unable to update policy");
    }
  };

  return (
    <section className="space-y-6" data-testid="governance-page">
      <div className="rounded-xl border border-border bg-card/70 p-6" data-testid="governance-header-card">
        <h2 className="text-4xl font-bold tracking-tight" data-testid="governance-heading">Governance & Security Console</h2>
        <p className="mt-2 text-base text-muted-foreground" data-testid="governance-subheading">
          Production-ready controls for validation quality, model governance, and security monitoring.
        </p>
      </div>

      <Card data-testid="governance-actor-card">
        <CardHeader>
          <CardTitle data-testid="governance-actor-title">Governance Actor Context</CardTitle>
          <CardDescription data-testid="governance-actor-description">Use admin/reviewer role simulation for protected policy actions.</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <Input
            data-testid="governance-actor-id-input"
            className="h-10"
            value={actor.actorId}
            onChange={(event) => setActor((prev) => ({ ...prev, actorId: event.target.value }))}
            placeholder="actor id"
          />
          <select
            data-testid="governance-role-select"
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
            value={actor.role}
            onChange={(event) => setActor((prev) => ({ ...prev, role: event.target.value }))}
          >
            <option value="admin">admin</option>
            <option value="reviewer">reviewer</option>
          </select>
        </CardContent>
      </Card>

      <Card data-testid="governance-policy-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2" data-testid="governance-policy-title">
            Active Policy
            <Badge variant="secondary" data-testid="governance-policy-version">v{policy.version}</Badge>
          </CardTitle>
          <CardDescription data-testid="governance-policy-summary">{policySummary}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2" data-testid="governance-provider-checkbox-group">
            <p className="text-sm font-medium" data-testid="governance-provider-label">Allowed Providers</p>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              {providerOptions.map((provider) => (
                <label key={provider} className="inline-flex items-center gap-2 rounded-md border border-border p-2 text-sm" data-testid={`governance-provider-option-${provider}`}>
                  <input
                    data-testid={`governance-provider-checkbox-${provider}`}
                    type="checkbox"
                    checked={policy.allowed_providers.includes(provider)}
                    onChange={() => toggleProvider(provider)}
                  />
                  {provider}
                </label>
              ))}
            </div>
          </div>

          <Input
            data-testid="governance-max-code-length-input"
            className="h-10"
            type="number"
            value={policy.max_code_length}
            onChange={(event) => setPolicy((prev) => ({ ...prev, max_code_length: Number(event.target.value) }))}
            placeholder="max code length"
          />

          <Input
            data-testid="governance-min-confidence-input"
            className="h-10"
            type="number"
            step="0.01"
            min="0"
            max="1"
            value={policy.min_transparency_confidence}
            onChange={(event) => setPolicy((prev) => ({ ...prev, min_transparency_confidence: Number(event.target.value) }))}
            placeholder="minimum confidence"
          />

          <Input
            data-testid="governance-blocked-patterns-input"
            className="h-10"
            value={blockedPatternText}
            onChange={(event) => setBlockedPatternText(event.target.value)}
            placeholder="comma-separated blocked patterns"
          />

          <label className="inline-flex items-center gap-2 rounded-md border border-border p-3 text-sm" data-testid="governance-reviewer-gate-toggle-label">
            <input
              data-testid="governance-reviewer-gate-checkbox"
              type="checkbox"
              checked={policy.require_reviewer_for_high_risk}
              onChange={(event) => setPolicy((prev) => ({ ...prev, require_reviewer_for_high_risk: event.target.checked }))}
            />
            Require reviewer approval for high-risk outputs
          </label>

          <Button data-testid="governance-save-policy-button" className="h-10" onClick={savePolicy}>Save Policy</Button>
          <p className="text-xs text-muted-foreground" data-testid="governance-policy-updated-meta">
            Last updated by {policy.updated_by || "system"} at {policy.updated_at ? new Date(policy.updated_at).toLocaleString() : "-"}
          </p>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Card data-testid="governance-audit-card">
          <CardHeader><CardTitle data-testid="governance-audit-title">Governance Audit Logs</CardTitle></CardHeader>
          <CardContent className="space-y-2" data-testid="governance-audit-list">
            {auditLogs.length === 0 ? <p className="text-sm text-muted-foreground" data-testid="governance-audit-empty">No audit events yet.</p> : auditLogs.map((event) => (
              <details key={event.event_id} className="rounded-md border border-border bg-background p-2" data-testid={`governance-audit-item-${event.event_id}`}>
                <summary className="cursor-pointer text-sm" data-testid={`governance-audit-summary-${event.event_id}`}>{event.action} · {event.status}</summary>
                <pre className="mt-2 overflow-auto text-xs" data-testid={`governance-audit-detail-${event.event_id}`}>{JSON.stringify(event.details, null, 2)}</pre>
              </details>
            ))}
          </CardContent>
        </Card>

        <Card data-testid="governance-security-card">
          <CardHeader><CardTitle data-testid="governance-security-title">Security Events</CardTitle></CardHeader>
          <CardContent className="space-y-2" data-testid="governance-security-list">
            {securityEvents.length === 0 ? <p className="text-sm text-muted-foreground" data-testid="governance-security-empty">No security events yet.</p> : securityEvents.map((event) => (
              <details key={event.event_id} className="rounded-md border border-border bg-background p-2" data-testid={`governance-security-item-${event.event_id}`}>
                <summary className="cursor-pointer text-sm" data-testid={`governance-security-summary-${event.event_id}`}>{event.event_type} · {event.severity}</summary>
                <pre className="mt-2 overflow-auto text-xs" data-testid={`governance-security-detail-${event.event_id}`}>{JSON.stringify(event.details, null, 2)}</pre>
              </details>
            ))}
          </CardContent>
        </Card>

        <Card data-testid="governance-metrics-card">
          <CardHeader><CardTitle data-testid="governance-metrics-title">Quality Monitoring</CardTitle></CardHeader>
          <CardContent className="space-y-2" data-testid="governance-metrics-list">
            {qualityMetrics.length === 0 ? <p className="text-sm text-muted-foreground" data-testid="governance-metrics-empty">No quality metrics yet.</p> : qualityMetrics.map((metric) => (
              <div key={metric.metric_id} className="rounded-md border border-border bg-background p-2 text-xs" data-testid={`governance-metric-item-${metric.metric_id}`}>
                <p data-testid={`governance-metric-id-${metric.metric_id}`}>report: {metric.report_id}</p>
                <p data-testid={`governance-metric-performance-${metric.metric_id}`}>analysis: {metric.analysis_ms} ms · issues: {metric.issue_count}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </section>
  );
}