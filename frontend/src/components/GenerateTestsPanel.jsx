import { useState } from "react";
import usePersistedState from "../hooks/usePersistedState";
import { Copy, Check, FlaskConical, Loader2 } from "lucide-react";
import { toast } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { api } from "@/services/api";

export default function GenerateTestsPanel({ initialCode = "", initialLanguage = "python", sanitizerEnabled = true }) {
  const [code, setCode] = usePersistedState("drcode_generate_tests_code", initialCode);
  const [language, setLanguage] = useState(initialLanguage);
  const [framework, setFramework] = useState("pytest");
  const [includeEdgeCases, setIncludeEdgeCases] = useState(true);
  const [loading, setLoading] = useState(false);
  const [testCode, setTestCode] = useState("");
  const [testCount, setTestCount] = useState(0);
  const [functionsTested, setFunctionsTested] = useState([]);
  const [copied, setCopied] = useState(false);

  const generateTests = async () => {
    if (!code.trim()) {
      toast.error("Add code before generating tests.");
      return;
    }
    setLoading(true);
    setTestCode("");
    setTestCount(0);
    setFunctionsTested([]);
    try {
      const result = await api.generateTests({
        code,
        language,
        framework,
        include_edge_cases: includeEdgeCases,
        sanitizer: sanitizerEnabled,
      });
      if (result.success) {
        setTestCode(result.test_code);
        setTestCount(result.test_count);
        setFunctionsTested(result.functions_tested);
        toast.success(`Generated ${result.test_count} test(s)`);
      } else {
        toast.error(result.error || "Failed to generate tests");
      }
    } catch (error) {
      toast.error(error?.response?.data?.detail || "Failed to generate tests");
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(testCode);
      setCopied(true);
      toast.success("Copied to clipboard");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Failed to copy");
    }
  };

  const frameworkOptions = {
    python: [
      { value: "pytest", label: "pytest" },
      { value: "unittest", label: "unittest" },
    ],
    javascript: [
      { value: "vitest", label: "vitest" },
      { value: "jest", label: "jest" },
    ],
    typescript: [
      { value: "vitest", label: "vitest" },
      { value: "jest", label: "jest" },
    ],
  };

  return (
    <Card data-testid="generate-tests-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xl" data-testid="generate-tests-title">
          <FlaskConical className="h-5 w-5 text-primary" /> DR.CODE Generate: Tests
        </CardTitle>
        <CardDescription data-testid="generate-tests-description">
          Generate unit tests for your code using AI.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <select
            data-testid="test-language-select"
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
          >
            <option value="python">Python</option>
            <option value="javascript">JavaScript</option>
            <option value="typescript">TypeScript</option>
          </select>

          <select
            data-testid="test-framework-select"
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
            value={framework}
            onChange={(e) => setFramework(e.target.value)}
          >
            {frameworkOptions[language]?.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm">
            <input
              type="checkbox"
              checked={includeEdgeCases}
              onChange={(e) => setIncludeEdgeCases(e.target.checked)}
              className="h-4 w-4"
            />
            Edge cases
          </label>
        </div>

        <Textarea
          data-testid="test-source-code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          className="min-h-[200px] font-mono text-sm"
          placeholder="Paste your code here to generate tests..."
        />

        <Button
          data-testid="generate-tests-button"
          className="h-10"
          onClick={generateTests}
          disabled={loading}
        >
          {loading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Generating...
            </>
          ) : (
            <>
              <FlaskConical className="mr-2 h-4 w-4" /> Generate Tests
            </>
          )}
        </Button>

        {testCode && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground" data-testid="test-results-info">
                {testCount} test(s) for {functionsTested.join(", ")}
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={copyToClipboard}
                data-testid="copy-tests-button"
              >
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                <span className="ml-2">{copied ? "Copied" : "Copy"}</span>
              </Button>
            </div>
            <Textarea
              data-testid="generated-test-code"
              value={testCode}
              readOnly
              className="min-h-[200px] font-mono text-sm bg-muted/50"
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
