// components/LLMSection.tsx
import React, { useState, useImperativeHandle, forwardRef } from "react";

const LLMSection = forwardRef(function LLMSection(
  { lastUpdated, embeddingModel }: { lastUpdated?: string, embeddingModel?: string },
  ref
) {
  const [prompt, setPrompt] = useState("");
  const [response, setResponse] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSend = async (customPrompt?: string) => {
    const toSend = customPrompt !== undefined ? customPrompt : prompt;
    if (!toSend.trim()) return;
    setLoading(true);
    setError(null);
    setResponse(null);
    try {
      const res = await fetch("http://localhost:8000/llm-context", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: toSend }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (data.matches && data.matches.length > 0) {
        setResponse(
          data.matches.map((m: any) => m.review_text).join("\n\n---\n\n")
        );
      } else {
        setResponse("No relevant context found.");
      }
    } catch (e: any) {
      setError(e.message || "Error fetching context");
    } finally {
      setLoading(false);
    }
  };

  useImperativeHandle(ref, () => ({
    submitPrompt: (newPrompt: string) => {
      setPrompt(newPrompt);
      handleSend(newPrompt);
    }
  }));

  return (
    <section className="mt-12 bg-black/80 rounded-xl p-4 w-full">
      <div className="flex justify-between items-center mb-4">
        <span className="text-[#FAFAFA] font-mono text-xs font-light">
          SentenceTransformer: {embeddingModel || 'Unknown'}
        </span>
        <span className="text-[#FAFAFA] font-mono text-xs font-light">
          Last updated: {lastUpdated || 'N/A'}
        </span>
      </div>

      <div className="bg-[#2F2F2F]/50 rounded-lg p-4 w-full min-h-[200px] flex flex-col justify-end">
        {error && <div className="text-red-400 mb-4 font-mono text-xs">{error}</div>}
        {response && (
          <div className="mb-6 bg-black/30 rounded p-4 text-[#FAFAFA] font-mono text-xs whitespace-pre-line max-h-60 overflow-y-auto">
            {response}
          </div>
        )}
        <div className="flex items-end gap-4">
          <textarea
            placeholder="Type your question here..."
            className="flex-grow h-10 resize-none rounded-md bg-black/30 text-[#FAFAFA] font-sans text-sm p-2 focus:outline-none"
            rows={1}
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            disabled={loading}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
          />
          <button
            className="h-10 text-[#FAFAFA] text-lg px-4 rounded-md bg-white/20 hover:bg-white/20 transition-colors"
            onClick={() => handleSend()}
            disabled={loading || !prompt.trim()}
          >
            {loading ? "…" : "✈"}
          </button>
        </div>
      </div>
    </section>
  );
});

export default LLMSection;
