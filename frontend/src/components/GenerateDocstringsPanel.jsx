import { useState } from "react";
import usePersistedState from "../hooks/usePersistedState";
import { Copy, Check, FileText, Loader2 } from "lucide-react";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/services/api";

export default function GenerateDocstringsPanel({ initialCode = "", initialLanguage = "python", sanitizerEnabled = true }) {
  const [code, setCode] = usePersistedState("drcode_generate_docstrings_code", initialCode);
  const [language, setLanguage] = useState(initialLanguage);
  const [style, setStyle] = useState("google");
  const [loading, setLoading] = useState(false);
  const [documentedCode, setDocumentedCode] = useState("");
  const [functionsDocumented, setFunctionsDocumented] = useState([]);
  const [copied, setCopied] = useState(false);

  const generateDocstrings = async () => {
    if (!code.trim()) {
      toast.error("Add code before generating docstrings.");
      return;
    }
    setLoading(true);
    setDocumentedCode("");
    setFunctionsDocumented([]);
    try {
      const result = await api.generateDocstrings({
        code,
        language,
        style,
        sanitizer: sanitizerEnabled,
      });
      if (result.success) {
        setDocumentedCode(result.documented_code);
        setFunctionsDocumented(result.functions_documented);
        toast.success(`Generated docstrings for ${result.functions_documented.length} function(s)`);
      } else {
        toast.error(result.error || "Failed to generate docstrings");
      }
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Failed to generate docstrings");
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(documentedCode);
      setCopied(true);
      toast.success("Copied to clipboard");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Failed to copy");
    }
  };

  return (
    <Card data-testid="generate-docstrings-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xl" data-testid="generate-docstrings-title">
          <FileText className="h-5 w-5 text-primary" /> DR.CODE Generate: Docstrings
        </CardTitle>
        <CardDescription data-testid="generate-docstrings-description">
          Generate documentation for your code using AI.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <select
            data-testid="docstring-language-select"
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
          >
            <option value="python">Python</option>
            <option value="javascript">JavaScript</option>
            <option value="typescript">TypeScript</option>
          </select>

          <select
            data-testid="docstring-style-select"
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
            value={style}
            onChange={(e) => setStyle(e.target.value)}
          >
            <option value="google">Google</option>
            <option value="numpy">NumPy</option>
            <option value="sphinx">Sphinx</option>
          </select>
        </div>

        <Textarea
          data-testid="docstring-source-code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          className="min-h-[200px] font-mono text-sm"
          placeholder="Paste your code here to generate docstrings..."
        />

        <Button
          data-testid="generate-docstrings-button"
          className="h-10"
          onClick={generateDocstrings}
          disabled={loading}
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Generating...
            </>
          ) : (
            <>
              <FileText className="mr-2 h-4 w-4" /> Generate Docstrings
            </>
          )}
        </Button>

        {documentedCode && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground" data-testid="docstring-results-info">
                Docstrings for: {functionsDocumented.join(", ")}
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={copyToClipboard}
                data-testid="copy-docstrings-button"
              >
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                <span className="ml-2">{copied ? "Copied" : "Copy"}</span>
              </Button>
            </div>
            <Textarea
              data-testid="generated-docstring-code"
              value={documentedCode}
              readOnly
              className="min-h-[200px] font-mono text-sm bg-muted/50"
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
