import axios from "axios";

const API_BASE = process.env.REACT_APP_BACKEND_URL 
  ? `${process.env.REACT_APP_BACKEND_URL}/api` 
  : "/api";

const client = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

export const api = {
  analyzeCode: async (payload) => {
    const { data } = await client.post("/analyze", payload);
    return data;
  },
  analyzeRepository: async (payload) => {
    const { data } = await client.post("/repository/analyze", payload);
    return data;
  },
  getRepositorySession: async (sessionId) => {
    const { data } = await client.get(`/repository/sessions/${sessionId}`);
    return data;
  },
  applyRepositoryFixes: async (payload) => {
    const { data } = await client.post("/repository/apply-fixes", payload);
    return data;
  },
  getRepositoryDownloadUrl: (sessionId) => `${API_BASE}/repository/sessions/${sessionId}/download`,
  getReports: async () => {
    const { data } = await client.get("/reports");
    return data;
  },
  getReportById: async (reportId) => {
    const { data } = await client.get(`/reports/${reportId}`);
    return data;
  },
  getSettings: async () => {
    const { data } = await client.get("/settings");
    return data;
  },
  updateSettings: async (payload) => {
    const { data } = await client.put("/settings", payload);
    return data;
  },
  getGovernancePolicy: async () => {
    const { data } = await client.get("/governance/policy");
    return data;
  },
  updateGovernancePolicy: async (payload, actor) => {
    const { data } = await client.put("/governance/policy", payload, {
      headers: {
        "x-actor-id": actor.actorId,
        "x-user-role": actor.role,
      },
    });
    return data;
  },
  getGovernanceAuditLogs: async () => {
    const { data } = await client.get("/governance/audit-logs");
    return data;
  },
  getSecurityEvents: async () => {
    const { data } = await client.get("/security/events");
    return data;
  },
  getQualityMetrics: async () => {
    const { data } = await client.get("/quality/metrics");
    return data;
  },
  sendGitWebhook: async (payload) => {
    const { data } = await client.post("/integrations/git/webhook", payload);
    return data;
  },
  sendCiEvent: async (payload) => {
    const { data } = await client.post("/integrations/ci/event", payload);
    return data;
  },
  getIntegrationEvents: async () => {
    const { data } = await client.get("/integrations/events");
    return data;
  },
  // v2: GitHub integration
  saveGithubSettings: async (payload) => {
    const { data } = await client.put("/settings/github", payload);
    return data;
  },
  getGithubStatus: async () => {
    const { data } = await client.get("/integrations/github/status");
    return data;
  },

  generateTests: async (payload) => {
    const { data } = await client.post("/generate/tests", payload);
    return data;
  },

  generateDocstrings: async (payload) => {
    const { data } = await client.post("/generate/docstrings", payload);
    return data;
  },

  generateDiagram: async (payload) => {
    const { data } = await client.post("/generate/diagram", payload);
    return data;
  },
  analyzeLocalFolder: async (path) => {
    const { data } = await client.post("/repository/analyze-local", { path });
    return data;
  },
  resetAnalysis: async () => {
    const { data } = await client.post("/reset-analysis");
    return data;
  },
  trashFile: async (fileId) => {
    const { data } = await client.delete(`/trash-file/${fileId}`);
    return data;
  },
  getTrashContents: async () => {
    const { data } = await client.get("/trash");
    return data;
  },
};