import { useState, useEffect, useRef } from "react";
import usePersistedState from "../hooks/usePersistedState";
import { Copy, Check, GitBranch, Loader2 } from "lucide-react";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/services/api";
import mermaid from "mermaid";

mermaid.initialize({
  startOnLoad: false,
  theme: "dark",
  securityLevel: "loose",
});

export default function GenerateDiagramPanel({ initialCode = "", initialLanguage = "python", sanitizerEnabled = true }) {
  const [code, setCode] = usePersistedState("drcode_generate_diagram_code", initialCode);
  const [language, setLanguage] = useState(initialLanguage);
  const [diagramType, setDiagramType] = useState("sequence");
  const [loading, setLoading] = useState(false);
  const [diagramSyntax, setDiagramSyntax] = useState("");
  const [copied, setCopied] = useState(false);
  const [showSyntax, setShowSyntax] = useState(false);
  const diagramRef = useRef(null);
  const [diagramId] = useState(() => `mermaid-${Math.random().toString(36).substr(2, 9)}`);

  useEffect(() => {
    if (diagramSyntax && diagramRef.current) {
      mermaid.render(diagramId, diagramSyntax)
        .then(({ svg }) => {
          if (diagramRef.current) {
            diagramRef.current.innerHTML = svg;
          }
        })
        .catch((err) => {
          console.error("Mermaid render error:", err);
          if (diagramRef.current) {
            diagramRef.current.innerHTML = `<p class="text-red-500 text-sm">Failed to render diagram: ${err.message}</p>`;
          }
        });
    }
  }, [diagramSyntax, diagramId]);

  const generateDiagram = async () => {
    if (!code.trim()) {
      toast.error("Add code before generating diagram.");
      return;
    }
    setLoading(true);
    setDiagramSyntax("");
    try {
      const result = await api.generateDiagram({
        code,
        language,
        diagram_type: diagramType,
        sanitizer: sanitizerEnabled,
      });
      if (result.success) {
        setDiagramSyntax(result.diagram_syntax);
        toast.success("Diagram generated successfully");
      } else {
        toast.error(result.error || "Failed to generate diagram");
      }
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Failed to generate diagram");
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(diagramSyntax);
      setCopied(true);
      toast.success("Copied to clipboard");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Failed to copy");
    }
  };

  return (
    <Card data-testid="generate-diagram-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xl" data-testid="generate-diagram-title">
          <GitBranch className="h-5 w-5 text-primary" /> DR.CODE Generate: Sequence Diagram
        </CardTitle>
        <CardDescription data-testid="generate-diagram-description">
          Generate Mermaid sequence diagrams from your code.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <select
            data-testid="diagram-language-select"
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
          >
            <option value="python">Python</option>
            <option value="javascript">JavaScript</option>
            <option value="typescript">TypeScript</option>
          </select>

          <select
            data-testid="diagram-type-select"
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
            value={diagramType}
            onChange={(e) => setDiagramType(e.target.value)}
          >
            <option value="sequence">Sequence</option>
            <option value="flow">Flow</option>
          </select>
        </div>

        <Textarea
          data-testid="diagram-source-code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          className="min-h-[200px] font-mono text-sm"
          placeholder="Paste your code here to generate a sequence diagram..."
        />

        <Button
          data-testid="generate-diagram-button"
          className="h-10"
          onClick={generateDiagram}
          disabled={loading}
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Generating...
            </>
          ) : (
            <>
              <GitBranch className="mr-2 h-4 w-4" /> Generate Diagram
            </>
          )}
        </Button>

        {diagramSyntax && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground" data-testid="diagram-results-info">
                Mermaid {diagramType} diagram
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowSyntax(!showSyntax)}
                  data-testid="toggle-syntax-button"
                >
                  {showSyntax ? "Hide Syntax" : "Show Syntax"}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={copyToClipboard}
                  data-testid="copy-diagram-button"
                >
                  {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  <span className="ml-2">{copied ? "Copied" : "Copy"}</span>
                </Button>
              </div>
            </div>
            
            <div 
              ref={diagramRef}
              className="min-h-[200px] rounded-md border border-border bg-background p-4 flex items-center justify-center overflow-auto"
              data-testid="diagram-rendered"
            />

            {showSyntax && (
              <Textarea
                data-testid="generated-diagram-syntax"
                value={diagramSyntax}
                readOnly
                className="min-h-[150px] font-mono text-sm bg-muted/50"
              />
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
