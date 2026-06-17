"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import { audioApi, scriptsApi } from "@/lib/api";
import { Play, Pause, RefreshCw, Volume2 } from "lucide-react";

export default function AudioManagementPage() {
  const params = useParams();
  const scriptId = params.id as string;

  const [script, setScript] = useState<any>(null);
  const [audioFiles, setAudioFiles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Preview
  const [previewText, setPreviewText] = useState("");
  const [previewLang, setPreviewLang] = useState("hi");
  const [previewVoice, setPreviewVoice] = useState("meera");
  const [previewing, setPreviewing] = useState(false);

  const loadData = async () => {
    try {
      const [scriptRes, audioRes] = await Promise.all([
        scriptsApi.get(scriptId),
        audioApi.list(scriptId),
      ]);
      setScript(scriptRes.data);
      setAudioFiles(audioRes.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [scriptId]);

  const handleGenerateAll = async () => {
    setGenerating(true);
    try {
      await audioApi.generate(scriptId);
      setTimeout(loadData, 3000);
    } catch (err) {
      console.error(err);
    } finally {
      setGenerating(false);
    }
  };

  const handleRegenerate = async (nodeKey: string, langCode: string) => {
    try {
      await audioApi.generateSingle(scriptId, { node_key: nodeKey, language_code: langCode });
      loadData();
    } catch (err) {
      console.error(err);
    }
  };

  const handlePreview = async () => {
    if (!previewText.trim()) return;
    setPreviewing(true);
    try {
      const response = await audioApi.preview({
        text: previewText,
        language_code: previewLang,
        voice_id: previewVoice,
      });
      const blob = new Blob([response.data], { type: "audio/wav" });
      const url = URL.createObjectURL(blob);
      if (audioRef.current) {
        audioRef.current.src = url;
        audioRef.current.play();
      }
    } catch (err) {
      console.error(err);
    } finally {
      setPreviewing(false);
    }
  };

  if (loading) {
    return <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" /></div>;
  }

  const nodes = script?.content?.nodes || {};
  const languages = script?.content?.supported_languages || [];
  const totalNeeded = Object.keys(nodes).length * languages.length;
  const readyCount = audioFiles.filter((f) => f.status === "ready").length;

  const getAudioForNodeLang = (nodeKey: string, lang: string) =>
    audioFiles.find((f) => f.node_key === nodeKey && f.language_code === lang);

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Audio Management</h1>
          <p className="text-slate-500">{script?.name}</p>
        </div>
        <button
          onClick={handleGenerateAll}
          disabled={generating}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50"
        >
          <RefreshCw size={16} className={generating ? "animate-spin" : ""} />
          {generating ? "Generating..." : "Regenerate All"}
        </button>
      </div>

      {/* Progress bar */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-slate-700">Audio Generation Progress</span>
          <span className="text-sm text-slate-500">{readyCount}/{totalNeeded} files</span>
        </div>
        <div className="h-3 bg-slate-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-600 rounded-full transition-all duration-500"
            style={{ width: `${totalNeeded > 0 ? (readyCount / totalNeeded) * 100 : 0}%` }}
          />
        </div>
        <div className="flex gap-4 mt-3 text-xs text-slate-500">
          <span className="flex items-center gap-1"><span className="w-2 h-2 bg-green-500 rounded-full" /> Ready: {audioFiles.filter((f) => f.status === "ready").length}</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 bg-yellow-500 rounded-full" /> Generating: {audioFiles.filter((f) => f.status === "generating").length}</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 bg-red-500 rounded-full" /> Failed: {audioFiles.filter((f) => f.status === "failed").length}</span>
        </div>
      </div>

      {/* Audio files grid */}
      <div className="space-y-4 mb-8">
        {Object.entries(nodes).map(([nodeKey, nodeConfig]: [string, any]) => (
          <div key={nodeKey} className="bg-white rounded-xl p-5 border border-slate-200">
            <h3 className="text-base font-semibold text-slate-900 mb-3 capitalize">{nodeKey.replace(/_/g, " ")}</h3>
            <div className="grid gap-3">
              {languages.map((lang: string) => {
                const audio = getAudioForNodeLang(nodeKey, lang);
                const statusColor = audio?.status === "ready" ? "bg-green-100 text-green-700" : audio?.status === "generating" ? "bg-yellow-100 text-yellow-700" : audio?.status === "failed" ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-500";
                return (
                  <div key={lang} className="flex items-center gap-4 p-3 bg-slate-50 rounded-lg">
                    <span className="text-sm font-medium text-slate-700 w-16 uppercase">{lang}</span>
                    <span className="flex-1 text-sm text-slate-600 truncate">{nodeConfig.text?.[lang] || "-"}</span>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor}`}>
                      {audio?.status || "pending"}
                    </span>
                    {audio?.audio_duration_ms && (
                      <span className="text-xs text-slate-400">{(audio.audio_duration_ms / 1000).toFixed(1)}s</span>
                    )}
                    {audio?.status === "ready" && (
                      <button className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-lg">
                        <Play size={14} />
                      </button>
                    )}
                    <button
                      onClick={() => handleRegenerate(nodeKey, lang)}
                      className="p-1.5 text-slate-500 hover:bg-slate-200 rounded-lg"
                      title="Regenerate"
                    >
                      <RefreshCw size={14} />
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Preview section */}
      <div className="bg-white rounded-xl p-5 border border-slate-200">
        <h3 className="text-base font-semibold text-slate-900 mb-3">Preview Audio</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
          <textarea
            value={previewText}
            onChange={(e) => setPreviewText(e.target.value)}
            className="md:col-span-1 px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={2}
            placeholder="Type any text to preview..."
          />
          <select value={previewLang} onChange={(e) => setPreviewLang(e.target.value)} className="px-3 py-2 border border-slate-300 rounded-lg text-sm">
            {languages.map((l: string) => <option key={l} value={l}>{l.toUpperCase()}</option>)}
          </select>
          <select value={previewVoice} onChange={(e) => setPreviewVoice(e.target.value)} className="px-3 py-2 border border-slate-300 rounded-lg text-sm">
            <option value="meera">Meera (Female)</option>
            <option value="arvind">Arvind (Male)</option>
          </select>
        </div>
        <button
          onClick={handlePreview}
          disabled={previewing || !previewText.trim()}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm font-medium disabled:opacity-50"
        >
          <Volume2 size={16} />
          {previewing ? "Generating..." : "Preview"}
        </button>
        <audio ref={audioRef} className="hidden" />
      </div>
    </div>
  );
}
