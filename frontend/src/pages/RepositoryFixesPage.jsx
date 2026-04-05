import { useMemo, useState } from "react";
import { CheckCircle2, Download, FolderUp, ShieldCheck } from "lucide-react";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/services/api";

const SUPPORTED_REPO_FILE_REGEX = /\.(py|js|jsx|ts|tsx|json|md|txt|yml|yaml|css|html)$/i;

export default function RepositoryFixesPage() {
  const [repositoryName, setRepositoryName] = useState("workspace-repository");
  const [repositoryFiles, setRepositoryFiles] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [selectedFixIds, setSelectedFixIds] = useState([]);
  const [loadingAnalyze, setLoadingAnalyze] = useState(false);
  const [loadingApply, setLoadingApply] = useState(false);

  const analyzedFixes = analysis?.fixes || [];
  const selectedSet = useMemo(() => new Set(selectedFixIds), [selectedFixIds]);

  const onRepositoryUpload = async (event) => {
    const inputFiles = Array.from(event.target.files || []);
    if (inputFiles.length === 0) {
      return;
    }

    const rootName = inputFiles[0]?.webkitRelativePath?.split("/")[0];
    if (rootName) {
      setRepositoryName(rootName);
    }

    const supported = inputFiles.filter(
      (file) => SUPPORTED_REPO_FILE_REGEX.test(file.name) && file.size <= 250_000,
    );

    const readFiles = await Promise.all(
      supported.map(async (file) => ({
        path: file.webkitRelativePath || file.name,
        content: await file.text(),
      })),
    );

    setRepositoryFiles(readFiles);
    setAnalysis(null);
    setSelectedFixIds([]);

    if (readFiles.length === 0) {
      toast.error("No supported repository files were found.");
      return;
    }

    toast.success(`Loaded ${readFiles.length} files for repository analysis.`);
  };

  const runRepositoryAnalysis = async () => {
    if (repositoryFiles.length === 0) {
      toast.error("Upload a repository folder first.");
      return;
    }

    setLoadingAnalyze(true);
    try {
      const response = await api.analyzeRepository({
        repository_name: repositoryName,
        files: repositoryFiles,
      });
      setAnalysis(response);
      setSelectedFixIds([]);
      toast.success("Repository scan complete.");
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Repository analysis failed.");
    } finally {
      setLoadingAnalyze(false);
    }
  };

  const refreshAnalysis = async (sessionId) => {
    const latest = await api.getRepositorySession(sessionId);
    setAnalysis(latest);
  };

  const toggleFixSelection = (fixId) => {
    setSelectedFixIds((current) =>
      current.includes(fixId)
        ? current.filter((id) => id !== fixId)
        : [...current, fixId],
    );
  };

  const selectAllVisibleFixes = () => {
    if (!analysis) return;
    if (selectedFixIds.length === analyzedFixes.length) {
      setSelectedFixIds([]);
      return;
    }
    setSelectedFixIds(analyzedFixes.map((fix) => fix.fix_id));
  };

  const applyFixes = async (approveAll) => {
    if (!analysis) {
      toast.error("Run repository analysis before applying fixes.");
      return;
    }

    if (!approveAll && selectedFixIds.length === 0) {
      toast.error("Select one or more fixes to apply.");
      return;
    }

    setLoadingApply(true);
    try {
      const response = await api.applyRepositoryFixes({
        session_id: analysis.session_id,
        approve_all: approveAll,
        approved_fix_ids: approveAll ? [] : selectedFixIds,
      });
      await refreshAnalysis(analysis.session_id);
      toast.success(
        `${response.applied_fix_count} fixes applied across ${response.updated_file_count} files after validation.`,
      );
    } catch (error) {
      toast.error(
        error?.response?.data?.detail ||
          "Fix application was blocked because validation failed.",
      );
    } finally {
      setLoadingApply(false);
    }
  };

  const downloadPatchedRepository = () => {
    if (!analysis) {
      toast.error("No repository session is available.");
      return;
    }
    window.open(api.getRepositoryDownloadUrl(analysis.session_id), "_blank", "noopener,noreferrer");
  };

  return (
    <section className="space-y-6" data-testid="repository-fixes-page">
      <div className="rounded-xl border border-border bg-card/70 p-6" data-testid="repository-fixes-header-card">
        <h2 className="text-4xl font-bold tracking-tight" data-testid="repository-fixes-heading">
          Repository Fix Approval Center
        </h2>
        <p className="mt-2 text-base text-muted-foreground" data-testid="repository-fixes-subheading">
          Upload a full codebase, approve suggested fixes per issue or all at once, and apply only after syntax validation.
        </p>
      </div>

      <Card data-testid="repository-upload-card">
        <CardHeader>
          <CardTitle className="text-xl" data-testid="repository-upload-title">Repository Input</CardTitle>
          <CardDescription data-testid="repository-upload-description">
            Folder upload supports Python and JavaScript/TypeScript focused fix generation.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            data-testid="repository-name-input"
            className="h-10"
            value={repositoryName}
            onChange={(event) => setRepositoryName(event.target.value)}
            placeholder="Repository name"
          />

          <label
            className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border bg-background px-4 py-2 text-sm hover:border-primary/40"
            data-testid="repository-upload-label"
          >
            <FolderUp className="h-4 w-4" /> Upload Repository Folder
            <input
              data-testid="repository-upload-input"
              type="file"
              className="hidden"
              multiple
              webkitdirectory="true"
              directory=""
              onChange={onRepositoryUpload}
            />
          </label>

          <div className="flex flex-wrap items-center gap-2 text-sm" data-testid="repository-upload-stats">
            <Badge variant="outline" data-testid="repository-file-count-badge">
              {repositoryFiles.length} files loaded
            </Badge>
            {analysis ? (
              <Badge variant="secondary" data-testid="repository-session-badge">
                Session: {analysis.session_id.slice(0, 8)}
              </Badge>
            ) : null}
          </div>

          <Button
            data-testid="run-repository-analysis-button"
            className="h-10"
            onClick={runRepositoryAnalysis}
            disabled={loadingAnalyze}
          >
            {loadingAnalyze ? "Analyzing Repository..." : "Analyze Repository"}
          </Button>
        </CardContent>
      </Card>

      <Card data-testid="repository-analysis-summary-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-xl" data-testid="repository-analysis-summary-title">
            <ShieldCheck className="h-5 w-5 text-primary" /> Approval & Apply
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {analysis ? (
            <>
              <p className="text-sm text-muted-foreground" data-testid="repository-analysis-summary-text">
                {analysis.summary}
              </p>
              <div className="flex flex-wrap items-center gap-2" data-testid="repository-analysis-meta">
                <Badge variant="outline" data-testid="repository-analysis-status-badge">status: {analysis.status}</Badge>
                <Badge variant="outline" data-testid="repository-analysis-fix-count-badge">{analysis.fixes.length} fix suggestions</Badge>
                <Badge variant="secondary" data-testid="repository-analysis-applied-count-badge">{analysis.applied_fix_count} applied</Badge>
              </div>

              <div className="flex flex-wrap gap-2">
                <Button
                  data-testid="select-all-fixes-button"
                  className="h-10"
                  variant="outline"
                  onClick={selectAllVisibleFixes}
                >
                  {selectedFixIds.length === analyzedFixes.length && analyzedFixes.length > 0
                    ? "Clear Selection"
                    : "Select All Suggestions"}
                </Button>
                <Button
                  data-testid="apply-selected-fixes-button"
                  className="h-10"
                  onClick={() => applyFixes(false)}
                  disabled={loadingApply}
                >
                  {loadingApply ? "Applying..." : "Approve & Apply Selected"}
                </Button>
                <Button
                  data-testid="apply-all-fixes-button"
                  className="h-10"
                  variant="secondary"
                  onClick={() => applyFixes(true)}
                  disabled={loadingApply}
                >
                  {loadingApply ? "Applying..." : "Approve & Apply All"}
                </Button>
                <Button
                  data-testid="download-patched-repository-button"
                  className="h-10"
                  variant="outline"
                  onClick={downloadPatchedRepository}
                  disabled={analysis.status !== "applied"}
                >
                  <Download className="h-4 w-4" /> Download Patched Repository
                </Button>
              </div>
            </>
          ) : (
            <p className="text-sm text-muted-foreground" data-testid="repository-analysis-empty-text">
              No repository scan yet.
            </p>
          )}
        </CardContent>
      </Card>

      <Card data-testid="repository-fix-list-card">
        <CardHeader>
          <CardTitle className="text-xl" data-testid="repository-fix-list-title">Suggested Fixes</CardTitle>
          <CardDescription data-testid="repository-fix-list-description">
            Each fix can be individually approved. The system blocks application if syntax validation fails.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3" data-testid="repository-fix-list">
          {analyzedFixes.length === 0 ? (
            <p className="text-sm text-muted-foreground" data-testid="repository-fix-list-empty">No fix suggestions available yet.</p>
          ) : (
            analyzedFixes.map((fix) => (
              <div key={fix.fix_id} className="rounded-lg border border-border bg-background p-4" data-testid={`repository-fix-item-${fix.fix_id}`}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <label className="inline-flex cursor-pointer items-center gap-2 text-sm font-medium" data-testid={`repository-fix-checkbox-label-${fix.fix_id}`}>
                    <input
                      data-testid={`repository-fix-checkbox-${fix.fix_id}`}
                      type="checkbox"
                      checked={selectedSet.has(fix.fix_id) || !!fix.approved}
                      onChange={() => toggleFixSelection(fix.fix_id)}
                      disabled={fix.approved}
                    />
                    {fix.title}
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="outline" data-testid={`repository-fix-file-${fix.fix_id}`}>{fix.file_path}</Badge>
                    <Badge variant="secondary" data-testid={`repository-fix-severity-${fix.fix_id}`}>{fix.severity}</Badge>
                    {fix.approved ? (
                      <Badge data-testid={`repository-fix-approved-${fix.fix_id}`}>
                        <CheckCircle2 className="mr-1 h-3.5 w-3.5" /> approved
                      </Badge>
                    ) : null}
                  </div>
                </div>
                <p className="mt-2 text-sm text-muted-foreground" data-testid={`repository-fix-detail-${fix.fix_id}`}>{fix.detail}</p>
                <div className="mt-3 grid gap-2 text-xs md:grid-cols-2">
                  <pre className="overflow-auto rounded-md border border-border bg-black/30 p-3" data-testid={`repository-fix-original-${fix.fix_id}`}>{fix.original_line}</pre>
                  <pre className="overflow-auto rounded-md border border-border bg-black/30 p-3 text-primary" data-testid={`repository-fix-replacement-${fix.fix_id}`}>{fix.replacement_line}</pre>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </section>
  );
}