"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { scriptsApi, audioApi } from "@/lib/api";
import { Plus, Search, FileText, Copy, Trash2, Volume2, Edit } from "lucide-react";

export default function ScriptsPage() {
  const [scripts, setScripts] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  const loadScripts = async () => {
    try {
      const { data } = await scriptsApi.list(page, 20, search || undefined);
      setScripts(data.scripts);
      setTotal(data.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadScripts();
  }, [page, search]);

  const handleDuplicate = async (id: string) => {
    await scriptsApi.duplicate(id);
    loadScripts();
  };

  const handleDelete = async (id: string) => {
    if (confirm("Delete this script?")) {
      await scriptsApi.delete(id);
      loadScripts();
    }
  };

  const handleGenerateAudio = async (id: string) => {
    await audioApi.generate(id);
    loadScripts();
  };

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      ready: "bg-green-100 text-green-700",
      generating: "bg-yellow-100 text-yellow-700",
      pending: "bg-slate-100 text-slate-600",
      failed: "bg-red-100 text-red-700",
    };
    return colors[status] || colors.pending;
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Scripts</h1>
        <Link
          href="/scripts/new"
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
        >
          <Plus size={16} />
          Create Script
        </Link>
      </div>

      <div className="mb-4">
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search scripts..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="w-full max-w-md pl-9 pr-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
          />
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      ) : scripts.length === 0 ? (
        <div className="bg-white rounded-xl p-12 text-center border border-slate-200">
          <FileText size={48} className="mx-auto mb-4 text-slate-300" />
          <h3 className="text-lg font-medium text-slate-900 mb-2">No scripts yet</h3>
          <p className="text-slate-500 mb-4">Create your first call script to get started.</p>
          <Link
            href="/scripts/new"
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
          >
            <Plus size={16} />
            Create Script
          </Link>
        </div>
      ) : (
        <div className="grid gap-4">
          {scripts.map((script) => (
            <div key={script.id} className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="text-lg font-semibold text-slate-900">{script.name}</h3>
                    <span className="text-xs text-slate-400">v{script.version}</span>
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${statusBadge(script.audio_status)}`}>
                      {script.audio_status}
                    </span>
                  </div>
                  {script.description && (
                    <p className="text-sm text-slate-500 mb-2">{script.description}</p>
                  )}
                  <div className="flex gap-4 text-sm text-slate-500">
                    <span>{Object.keys(script.content?.nodes || {}).length} nodes</span>
                    <span>{script.content?.supported_languages?.length || 0} languages</span>
                    <span>{script.audio_file_count} audio files</span>
                    <span>Created {new Date(script.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2 ml-4">
                  {script.audio_status !== "generating" && (
                    <button
                      onClick={() => handleGenerateAudio(script.id)}
                      className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                      title="Generate Audio"
                    >
                      <Volume2 size={16} />
                    </button>
                  )}
                  <Link
                    href={`/scripts/${script.id}/edit`}
                    className="p-2 text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                    title="Edit"
                  >
                    <Edit size={16} />
                  </Link>
                  <Link
                    href={`/scripts/${script.id}/audio`}
                    className="p-2 text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                    title="Audio Files"
                  >
                    <Volume2 size={16} />
                  </Link>
                  <button
                    onClick={() => handleDuplicate(script.id)}
                    className="p-2 text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                    title="Duplicate"
                  >
                    <Copy size={16} />
                  </button>
                  <button
                    onClick={() => handleDelete(script.id)}
                    className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="Delete"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {total > 20 && (
        <div className="flex justify-center gap-2 mt-6">
          <button
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page === 1}
            className="px-3 py-1 border border-slate-300 rounded-lg text-sm disabled:opacity-50"
          >
            Previous
          </button>
          <span className="px-3 py-1 text-sm text-slate-600">
            Page {page} of {Math.ceil(total / 20)}
          </span>
          <button
            onClick={() => setPage(page + 1)}
            disabled={page >= Math.ceil(total / 20)}
            className="px-3 py-1 border border-slate-300 rounded-lg text-sm disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
