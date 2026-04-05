import { useEffect, useMemo, useState } from "react";
import { Github } from "lucide-react";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { api } from "@/services/api";

const providerMeta = {
  ollama: { label: "Ollama (Local/Cloud)", needsKey: false },
  openai_compatible: { label: "OpenAI-Compatible", needsKey: true },
  gemini: { label: "Gemini Native", needsKey: true },
  anthropic: { label: "Anthropic Native", needsKey: true },
};

const defaultSettings = {
  severity: { critical: 85, high: 70, medium: 45, low: 0 },
  providers: {
    ollama: { enabled: true, base_url: "http://localhost:11434", model: "llama3.1:8b", key_configured: false, api_key_masked: null },
    openai_compatible: { enabled: false, base_url: "https://api.openai.com/v1", model: "gpt-5.2", key_configured: false, api_key_masked: null },
    gemini: { enabled: false, base_url: "https://generativelanguage.googleapis.com/v1beta", model: "gemini-2.5-pro", key_configured: false, api_key_masked: null },
    anthropic: { enabled: false, base_url: "https://api.anthropic.com/v1", model: "claude-sonnet-4-6", key_configured: false, api_key_masked: null },
  },
  routing: { primary_provider: "ollama", fallback_enabled: true, fallback_provider: "openai_compatible" },
};

export default function SettingsPage() {
  const [settings, setSettings] = useState(defaultSettings);
  const [apiKeys, setApiKeys] = useState({
    ollama: "",
    openai_compatible: "",
    gemini: "",
    anthropic: "",
  });
  const [clearKeys, setClearKeys] = useState({
    ollama: false,
    openai_compatible: false,
    gemini: false,
    anthropic: false,
  });

  // v2: GitHub integration state
  const [githubToken, setGithubToken] = useState("");
  const [githubSecret, setGithubSecret] = useState("");
  const [clearGithubToken, setClearGithubToken] = useState(false);
  const [githubStatus, setGithubStatus] = useState(null);

  const providerEntries = useMemo(() => Object.entries(providerMeta), []);

  useEffect(() => {
    const load = async () => {
      const data = await api.getSettings();
      setSettings({
        severity: data.severity || defaultSettings.severity,
        providers: { ...defaultSettings.providers, ...(data.providers || {}) },
        routing: data.routing || defaultSettings.routing,
      });
    };
    load();
    // v2: load GitHub status on mount
    api.getGithubStatus().then(setGithubStatus).catch(() => null);
  }, []);

  const updateSeverity = (key, value) => {
    setSettings((prev) => ({
      ...prev,
      severity: { ...prev.severity, [key]: Number(value) },
    }));
  };

  const updateProviderField = (provider, field, value) => {
    setSettings((prev) => ({
      ...prev,
      providers: {
        ...prev.providers,
        [provider]: { ...prev.providers[provider], [field]: value },
      },
    }));
  };

  const saveSettings = async () => {
    if (
      !(settings.severity.critical > settings.severity.high
        && settings.severity.high > settings.severity.medium
        && settings.severity.medium >= settings.severity.low)
    ) {
      toast.error("Use threshold order: critical > high > medium >= low");
      return;
    }

    const providerPayload = Object.fromEntries(
      providerEntries.map(([provider]) => {
        const payload = {
          enabled: !!settings.providers[provider]?.enabled,
          base_url: settings.providers[provider]?.base_url || "",
          model: settings.providers[provider]?.model || "",
        };
        if (apiKeys[provider]?.trim()) {
          payload.api_key = apiKeys[provider].trim();
        }
        if (clearKeys[provider]) {
          payload.clear_api_key = true;
        }
        return [provider, payload];
      }),
    );

    const payload = {
      severity: settings.severity,
      providers: providerPayload,
      routing: settings.routing,
    };

    const updated = await api.updateSettings(payload);
    setSettings({
      severity: updated.severity || defaultSettings.severity,
      providers: { ...defaultSettings.providers, ...(updated.providers || {}) },
      routing: updated.routing || defaultSettings.routing,
    });
    setApiKeys({ ollama: "", openai_compatible: "", gemini: "", anthropic: "" });
    setClearKeys({ ollama: false, openai_compatible: false, gemini: false, anthropic: false });
    toast.success("Provider settings updated");
  };

  // v2: Save GitHub PAT + webhook secret
  const saveGithubSettings = async () => {
    try {
      const updated = await api.saveGithubSettings({
        token: githubToken || undefined,
        webhook_secret: githubSecret || undefined,
        clear_token: clearGithubToken,
      });
      setGithubStatus(updated);
      setGithubToken("");
      setGithubSecret("");
      setClearGithubToken(false);
      toast.success("GitHub integration settings saved");
    } catch {
      toast.error("Failed to save GitHub settings");
    }
  };

  return (
    <section className="space-y-6" data-testid="settings-page">
      <div className="rounded-xl border border-border bg-card/70 p-6" data-testid="settings-header-card">
        <h2 className="text-4xl font-bold tracking-tight" data-testid="settings-heading">Model & Key Routing Settings</h2>
        <p className="mt-2 text-base text-muted-foreground" data-testid="settings-subheading">
          Configure local models and API-key providers with primary + fallback routing.
        </p>
      </div>

      <Card data-testid="provider-routing-card">
        <CardHeader>
          <CardTitle data-testid="provider-routing-title">Provider Routing</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div data-testid="primary-provider-container">
            <p className="mb-1 text-xs text-muted-foreground">Primary Provider</p>
            <select
              data-testid="primary-provider-select"
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={settings.routing.primary_provider}
              onChange={(event) => setSettings((prev) => ({ ...prev, routing: { ...prev.routing, primary_provider: event.target.value } }))}
            >
              {providerEntries.map(([provider, meta]) => <option key={provider} value={provider}>{meta.label}</option>)}
            </select>
          </div>
          <div className="rounded-lg border border-border p-3" data-testid="fallback-enabled-container">
            <p className="text-sm font-medium" data-testid="fallback-enabled-label">Enable fallback</p>
            <p className="text-xs text-muted-foreground" data-testid="fallback-enabled-help">Use second provider if primary fails.</p>
            <Switch
              data-testid="fallback-enabled-switch"
              checked={!!settings.routing.fallback_enabled}
              onCheckedChange={(checked) => setSettings((prev) => ({ ...prev, routing: { ...prev.routing, fallback_enabled: checked } }))}
            />
          </div>
          <div data-testid="fallback-provider-container">
            <p className="mb-1 text-xs text-muted-foreground">Fallback Provider</p>
            <select
              data-testid="fallback-provider-select"
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={settings.routing.fallback_provider}
              onChange={(event) => setSettings((prev) => ({ ...prev, routing: { ...prev.routing, fallback_provider: event.target.value } }))}
              disabled={!settings.routing.fallback_enabled}
            >
              {providerEntries.map(([provider, meta]) => <option key={provider} value={provider}>{meta.label}</option>)}
            </select>
          </div>
        </CardContent>
      </Card>

      {providerEntries.map(([provider, meta]) => (
        <Card key={provider} data-testid={`provider-card-${provider}`}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2" data-testid={`provider-title-${provider}`}>
              {meta.label}
              <Badge variant="outline" data-testid={`provider-key-status-${provider}`}>
                {settings.providers[provider]?.key_configured ? "key saved" : "no key"}
              </Badge>
            </CardTitle>
            <CardDescription data-testid={`provider-description-${provider}`}>
              {provider === "ollama"
                ? "Use local/server Ollama endpoint. No API key needed."
                : "Bring your own API key. Key is encrypted before saving."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between rounded-lg border border-border p-3" data-testid={`provider-enabled-container-${provider}`}>
              <p className="text-sm font-medium" data-testid={`provider-enabled-label-${provider}`}>Enable provider</p>
              <Switch
                data-testid={`provider-enabled-switch-${provider}`}
                checked={!!settings.providers[provider]?.enabled}
                onCheckedChange={(checked) => updateProviderField(provider, "enabled", checked)}
              />
            </div>

            <Input
              data-testid={`provider-base-url-input-${provider}`}
              className="h-10"
              value={settings.providers[provider]?.base_url || ""}
              onChange={(event) => updateProviderField(provider, "base_url", event.target.value)}
              placeholder="Base URL"
            />
            <Input
              data-testid={`provider-model-input-${provider}`}
              className="h-10"
              value={settings.providers[provider]?.model || ""}
              onChange={(event) => updateProviderField(provider, "model", event.target.value)}
              placeholder="Model name"
            />

            {meta.needsKey ? (
              <>
                <Input
                  data-testid={`provider-api-key-input-${provider}`}
                  className="h-10"
                  type="password"
                  value={apiKeys[provider]}
                  onChange={(event) => setApiKeys((prev) => ({ ...prev, [provider]: event.target.value }))}
                  placeholder="Enter API key"
                />
                <div className="flex items-center gap-3" data-testid={`provider-clear-key-container-${provider}`}>
                  <input
                    data-testid={`provider-clear-key-checkbox-${provider}`}
                    type="checkbox"
                    checked={!!clearKeys[provider]}
                    onChange={(event) => setClearKeys((prev) => ({ ...prev, [provider]: event.target.checked }))}
                  />
                  <p className="text-xs text-muted-foreground" data-testid={`provider-clear-key-label-${provider}`}>
                    Clear saved key for this provider
                  </p>
                </div>
                {settings.providers[provider]?.api_key_masked ? (
                  <p className="text-xs text-muted-foreground" data-testid={`provider-masked-key-${provider}`}>
                    Saved key: {settings.providers[provider].api_key_masked}
                  </p>
                ) : null}
              </>
            ) : null}
          </CardContent>
        </Card>
      ))}

      <Card data-testid="severity-settings-card">
        <CardHeader><CardTitle data-testid="severity-settings-title">Severity Thresholds</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <Input data-testid="threshold-critical-input" className="h-10" type="number" value={settings.severity.critical} onChange={(event) => updateSeverity("critical", event.target.value)} />
          <Input data-testid="threshold-high-input" className="h-10" type="number" value={settings.severity.high} onChange={(event) => updateSeverity("high", event.target.value)} />
          <Input data-testid="threshold-medium-input" className="h-10" type="number" value={settings.severity.medium} onChange={(event) => updateSeverity("medium", event.target.value)} />
          <Input data-testid="threshold-low-input" className="h-10" type="number" value={settings.severity.low} onChange={(event) => updateSeverity("low", event.target.value)} />
          <Button data-testid="save-settings-button" className="h-10 md:col-span-2" onClick={saveSettings}>Save Provider &amp; Severity Settings</Button>
        </CardContent>
      </Card>

      {/* v2: GitHub Integration Card */}
      <Card data-testid="github-settings-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2" data-testid="github-settings-title">
            <Github className="h-5 w-5" /> GitHub Integration
            {githubStatus?.token_configured && (
              <Badge variant="secondary" data-testid="github-settings-status-badge">connected</Badge>
            )}
          </CardTitle>
          <CardDescription data-testid="github-settings-description">
            Store your GitHub PAT to enable automatic PR analysis and inline comment-back.
            Token is encrypted at rest using Fernet (same as AI provider keys).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input
            data-testid="github-token-input"
            className="h-10"
            type="password"
            value={githubToken}
            onChange={(e) => setGithubToken(e.target.value)}
            placeholder="GitHub PAT (ghp_…)"
          />
          {githubStatus?.token_masked && (
            <p className="text-xs text-muted-foreground" data-testid="github-token-masked-display">
              Saved token: <code>{githubStatus.token_masked}</code>
            </p>
          )}
          <Input
            data-testid="github-webhook-secret-input"
            className="h-10"
            type="password"
            value={githubSecret}
            onChange={(e) => setGithubSecret(e.target.value)}
            placeholder="Webhook secret (optional but recommended)"
          />
          <label className="inline-flex items-center gap-2 text-sm" data-testid="github-clear-token-label">
            <input
              data-testid="github-clear-token-checkbox"
              type="checkbox"
              checked={clearGithubToken}
              onChange={(e) => setClearGithubToken(e.target.checked)}
            />
            Clear saved GitHub token
          </label>
          <Button data-testid="github-save-button" className="h-10" onClick={saveGithubSettings}>
            Save GitHub Settings
          </Button>
        </CardContent>
      </Card>
    </section>
  );
}