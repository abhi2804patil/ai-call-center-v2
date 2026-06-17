"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { scriptsApi, audioApi } from "@/lib/api";

const LANGUAGES = [
  { code: "hi", name: "Hindi" }, { code: "en", name: "English" },
  { code: "ta", name: "Tamil" }, { code: "te", name: "Telugu" },
  { code: "bn", name: "Bengali" }, { code: "mr", name: "Marathi" },
  { code: "gu", name: "Gujarati" }, { code: "kn", name: "Kannada" },
  { code: "ml", name: "Malayalam" }, { code: "od", name: "Odia" },
  { code: "pa", name: "Punjabi" },
];

export default function EditScriptPage() {
  const router = useRouter();
  const params = useParams();
  const scriptId = params.id as string;

  const [script, setScript] = useState<any>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [content, setContent] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await scriptsApi.get(scriptId);
        setScript(data);
        setName(data.name);
        setDescription(data.description || "");
        setContent(data.content);
      } catch (err) {
        setError("Failed to load script");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [scriptId]);

  const updateNodeText = (nodeKey: string, lang: string, text: string) => {
    setContent({
      ...content,
      nodes: {
        ...content.nodes,
        [nodeKey]: {
          ...content.nodes[nodeKey],
          text: { ...content.nodes[nodeKey].text, [lang]: text },
        },
      },
    });
  };

  const handleSave = async (regenerate: boolean) => {
    setSaving(true);
    setError("");
    try {
      await scriptsApi.update(scriptId, { name, description, content });
      if (regenerate) {
        await audioApi.generate(scriptId);
      }
      router.push("/scripts");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to update script");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" /></div>;
  }

  if (!content) return <div>Script not found</div>;

  const languages = content.supported_languages || [];
  const nodes = content.nodes || {};

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Edit Script</h1>
          <span className="text-sm text-slate-500">Version {script?.version}</span>
        </div>
      </div>

      {error && <div className="bg-red-50 text-red-600 p-3 rounded-lg mb-4 text-sm">{error}</div>}

      <div className="space-y-4">
        <div className="bg-white rounded-xl p-5 border border-slate-200">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
              <input value={description} onChange={(e) => setDescription(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
          </div>
        </div>

        {Object.entries(nodes).map(([nodeKey, nodeConfig]: [string, any]) => (
          <div key={nodeKey} className="bg-white rounded-xl p-5 border border-slate-200">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-medium text-slate-900">{nodeKey}</h3>
              <span className="text-xs text-slate-400">{nodeConfig.next_action}</span>
            </div>
            {languages.map((lang: string) => (
              <div key={lang} className="mb-2">
                <label className="block text-xs text-slate-500 mb-1">{LANGUAGES.find((l) => l.code === lang)?.name || lang}</label>
                <textarea
                  value={nodeConfig.text?.[lang] || ""}
                  onChange={(e) => updateNodeText(nodeKey, lang, e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                  rows={2}
                />
              </div>
            ))}
          </div>
        ))}

        <div className="flex justify-end gap-3">
          <button onClick={() => router.push("/scripts")} className="px-4 py-2 border border-slate-300 rounded-lg text-sm">Cancel</button>
          <button onClick={() => handleSave(false)} disabled={saving} className="px-4 py-2 border border-blue-600 text-blue-600 rounded-lg text-sm hover:bg-blue-50 disabled:opacity-50">
            Save
          </button>
          <button onClick={() => handleSave(true)} disabled={saving} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
            {saving ? "Saving..." : "Save & Regenerate Audio"}
          </button>
        </div>
      </div>
    </div>
  );
}
