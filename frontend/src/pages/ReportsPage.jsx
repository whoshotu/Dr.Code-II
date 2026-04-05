import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, Clock3 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/services/api";

export default function ReportsPage() {
  const navigate = useNavigate();
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadReports = async () => {
      try {
        const data = await api.getReports();
        setReports(data);
      } finally {
        setLoading(false);
      }
    };
    loadReports();
  }, []);

  return (
    <section className="space-y-6" data-testid="reports-page">
      <div className="rounded-xl border border-border bg-card/70 p-6" data-testid="reports-header-card">
        <h2 className="text-4xl font-bold tracking-tight" data-testid="reports-heading">Analysis Reports</h2>
        <p className="mt-2 text-base text-muted-foreground" data-testid="reports-subheading">Review historical scans and drill down into suggested fixes.</p>
      </div>

      <div className="space-y-4" data-testid="reports-list">
        {loading ? (
          <Card data-testid="reports-loading-state"><CardContent className="p-6 text-sm text-muted-foreground">Loading reports...</CardContent></Card>
        ) : reports.length === 0 ? (
          <Card data-testid="reports-empty-state"><CardContent className="p-6 text-sm text-muted-foreground">No reports yet. Run an analysis from dashboard.</CardContent></Card>
        ) : (
          reports.map((report) => (
            <Card key={report.report_id} data-testid={`report-card-${report.report_id}`}>
              <CardHeader>
                <CardTitle className="flex flex-wrap items-center justify-between gap-2">
                  <span data-testid={`report-filename-${report.report_id}`}>{report.filename}</span>
                  <Badge variant="secondary" data-testid={`report-mode-${report.report_id}`}>{report.mode}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground" data-testid={`report-summary-${report.report_id}`}>{report.summary}</p>
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1" data-testid={`report-created-${report.report_id}`}><Clock3 className="h-3.5 w-3.5" />{new Date(report.created_at).toLocaleString()}</span>
                  <span className="inline-flex items-center gap-1 rounded-full border border-destructive/40 px-2 py-1 text-destructive" data-testid={`report-critical-count-${report.report_id}`}><AlertTriangle className="h-3.5 w-3.5" />{report.critical_count} critical</span>
                  <span className="rounded-full border border-border px-2 py-1" data-testid={`report-issue-count-${report.report_id}`}>{report.issue_count} total issues</span>
                </div>
                <Button data-testid={`view-report-button-${report.report_id}`} className="h-10" onClick={() => navigate(`/reports/${report.report_id}`)}>View report details</Button>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </section>
  );
}