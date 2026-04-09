import { useEffect, useState } from "react";
import { Clock3, Inbox, RotatingCcw } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/services/api";
import { toast } from "sonner";

export default function TrashPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadTrash = async () => {
    setLoading(true);
    try {
      const data = await api.getTrashContents();
      setItems(data);
    } catch (err) {
      toast.error("Failed to load trash contents");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTrash();
  }, []);

  return (
    <section className="space-y-6" data-testid="trash-page">
      <div className="rounded-xl border border-border bg-card/70 p-6" data-testid="trash-header-card">
        <h2 className="text-4xl font-bold tracking-tight" data-testid="trash-heading">Trash / Archive</h2>
        <p className="mt-2 text-base text-muted-foreground" data-testid="trash-subheading">View inactive analysis reports and sessions that have been archived.</p>
      </div>

      <div className="space-y-4" data-testid="trash-list">
        {loading ? (
          <Card data-testid="trash-loading-state"><CardContent className="p-6 text-sm text-muted-foreground">Loading archive...</CardContent></Card>
        ) : items.length === 0 ? (
          <Card data-testid="trash-empty-state">
            <CardContent className="flex flex-col items-center justify-center p-12 text-sm text-muted-foreground">
              <Inbox className="mb-4 h-12 w-12 opacity-20" />
              <p>Your trash is empty.</p>
            </CardContent>
          </Card>
        ) : (
          items.map((item, idx) => (
            <Card key={item.id || idx} data-testid={`trash-item-${item.id}`}>
              <CardHeader>
                <CardTitle className="flex flex-wrap items-center justify-between gap-2">
                  <span>{item.filename || item.repository_name || "Unknown Item"}</span>
                  <Badge variant="outline" data-testid="item-type">{item.type || "unknown"}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground">{item.summary || "No summary available."}</p>
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1"><Clock3 className="h-3.5 w-3.5" />Trashed: {new Date(item.trashed_at).toLocaleString()}</span>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </section>
  );
}
