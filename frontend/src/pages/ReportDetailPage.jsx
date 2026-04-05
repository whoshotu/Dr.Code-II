import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { AlertCircle, Wrench } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/services/api";

const severityStyle = {
  critical: "destructive",
  high: "secondary",
  medium: "outline",
  low: "outline",
};

export default function ReportDetailPage() {
  const { reportId } = useParams();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadReport = async () => {
      try {
        const data = await api.getReportById(reportId);
        setReport(data);
      } finally {
        setLoading(false);
      }
    };
    loadReport();
  }, [reportId]);

  if (loading) {
    return <div className="rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground" data-testid="report-detail-loading">Loading report details...</div>;
  }

  if (!report) {
    return <div className="rounded-xl border border-border bg-card p-6 text-sm text-destructive" data-testid="report-detail-missing">Report not found.</div>;
  }

  return (
    <section className="space-y-6" data-testid="report-detail-page">
      <Card data-testid="report-meta-card">
        <CardHeader>
          <CardTitle className="text-3xl" data-testid="report-detail-title">{report.filename}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p data-testid="report-detail-summary">{report.summary}</p>
          <div className="flex flex-wrap gap-2">
            <Badge data-testid="report-detail-mode" variant="secondary">{report.mode}</Badge>
            <Badge data-testid="report-detail-language" variant="outline">{report.language}</Badge>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="issues" data-testid="report-tabs">
        <TabsList className="h-10" data-testid="report-tabs-list">
          <TabsTrigger value="issues" data-testid="tab-issues">Issues</TabsTrigger>
          <TabsTrigger value="fixes" data-testid="tab-fixes">Fixes</TabsTrigger>
          <TabsTrigger value="docs" data-testid="tab-docs">Documentation</TabsTrigger>
        </TabsList>

        <TabsContent value="issues" className="space-y-3" data-testid="issues-tab-content">
          {report.issues.map((issue) => (
            <Card key={issue.issue_id} data-testid={`issue-card-${issue.issue_id}`}>
              <CardContent className="space-y-2 p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-primary" />
                  <p className="font-semibold" data-testid={`issue-title-${issue.issue_id}`}>{issue.title}</p>
                  <Badge variant={severityStyle[issue.severity] || "outline"} data-testid={`issue-severity-${issue.issue_id}`}>{issue.severity}</Badge>
                </div>
                <p className="text-sm text-muted-foreground" data-testid={`issue-detail-${issue.issue_id}`}>{issue.detail}</p>
                {issue.code_snippet ? <pre className="overflow-auto rounded-md border border-border bg-black/30 p-3 text-xs" data-testid={`issue-snippet-${issue.issue_id}`}>{issue.code_snippet}</pre> : null}
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="fixes" className="space-y-3" data-testid="fixes-tab-content">
          {report.issues.map((issue) => (
            <Card key={`${issue.issue_id}-fix`} data-testid={`fix-card-${issue.issue_id}`}>
              <CardContent className="space-y-2 p-5">
                <p className="inline-flex items-center gap-2 font-semibold" data-testid={`fix-title-${issue.issue_id}`}><Wrench className="h-4 w-4 text-accent" /> {issue.title}</p>
                <p className="text-sm text-muted-foreground" data-testid={`fix-description-${issue.issue_id}`}>{issue.fix_suggestion}</p>
              </CardContent>
            </Card>
          ))}
          {report.ai_notes ? <Card data-testid="ai-notes-card"><CardContent className="p-5 text-sm" data-testid="ai-notes-content">{report.ai_notes}</CardContent></Card> : null}
        </TabsContent>

        <TabsContent value="docs" data-testid="docs-tab-content">
          <Card data-testid="generated-documentation-card">
            <CardContent className="p-5">
              <pre className="max-h-[560px] overflow-auto whitespace-pre-wrap rounded-md border border-border bg-black/30 p-4 text-xs font-mono" data-testid="generated-documentation-text">
                {report.documentation}
              </pre>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </section>
  );
}