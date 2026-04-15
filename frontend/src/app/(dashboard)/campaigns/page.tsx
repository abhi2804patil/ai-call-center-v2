"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { campaignsApi } from "@/lib/api";
import { Plus, Play, Pause, Square, BarChart3 } from "lucide-react";

const STATUS_TABS = ["all", "active", "paused", "draft", "completed"];

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [tab, setTab] = useState("all");
  const [loading, setLoading] = useState(true);

  const loadCampaigns = async () => {
    try {
      const statusFilter = tab === "all" ? undefined : tab;
      const { data } = await campaignsApi.list(1, 50, statusFilter);
      setCampaigns(data.campaigns);
      setTotal(data.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCampaigns();
  }, [tab]);

  const handleAction = async (id: string, action: string) => {
    try {
      if (action === "start") await campaignsApi.start(id);
      else if (action === "pause") await campaignsApi.pause(id);
      else if (action === "resume") await campaignsApi.resume(id);
      else if (action === "stop") await campaignsApi.stop(id);
      loadCampaigns();
    } catch (err) {
      console.error(err);
    }
  };

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      active: "bg-green-100 text-green-700",
      paused: "bg-yellow-100 text-yellow-700",
      draft: "bg-slate-100 text-slate-600",
      completed: "bg-blue-100 text-blue-700",
      cancelled: "bg-red-100 text-red-700",
    };
    return colors[status] || colors.draft;
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Campaigns</h1>
        <Link
          href="/campaigns/new"
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
        >
          <Plus size={16} />
          Create Campaign
        </Link>
      </div>

      <div className="flex gap-1 mb-6 bg-slate-100 p-1 rounded-lg w-fit">
        {STATUS_TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium capitalize transition-colors ${
              tab === t ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
        </div>
      ) : campaigns.length === 0 ? (
        <div className="bg-white rounded-xl p-12 text-center border border-slate-200">
          <BarChart3 size={48} className="mx-auto mb-4 text-slate-300" />
          <h3 className="text-lg font-medium text-slate-900 mb-2">No campaigns</h3>
          <p className="text-slate-500 mb-4">Create a campaign to start making calls.</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {campaigns.map((c) => {
            const progress = c.total_numbers > 0 ? (c.called_count / c.total_numbers) * 100 : 0;
            return (
              <div key={c.id} className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <Link href={`/campaigns/${c.id}`} className="text-lg font-semibold text-slate-900 hover:text-blue-600">
                        {c.name}
                      </Link>
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${statusBadge(c.status)}`}>
                        {c.status}
                      </span>
                    </div>
                    <div className="flex gap-6 text-sm text-slate-500 mb-3">
                      <span>Total: {c.total_numbers}</span>
                      <span>Called: {c.called_count}</span>
                      <span>Success: {c.success_count}</span>
                      <span>Failed: {c.failed_count}</span>
                    </div>
                    <div className="w-full max-w-sm">
                      <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-600 rounded-full" style={{ width: `${progress}%` }} />
                      </div>
                      <span className="text-xs text-slate-400 mt-1">{progress.toFixed(0)}%</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    {c.status === "draft" && (
                      <button onClick={() => handleAction(c.id, "start")} className="p-2 text-green-600 hover:bg-green-50 rounded-lg" title="Start">
                        <Play size={16} />
                      </button>
                    )}
                    {c.status === "active" && (
                      <button onClick={() => handleAction(c.id, "pause")} className="p-2 text-yellow-600 hover:bg-yellow-50 rounded-lg" title="Pause">
                        <Pause size={16} />
                      </button>
                    )}
                    {c.status === "paused" && (
                      <button onClick={() => handleAction(c.id, "resume")} className="p-2 text-green-600 hover:bg-green-50 rounded-lg" title="Resume">
                        <Play size={16} />
                      </button>
                    )}
                    {["active", "paused"].includes(c.status) && (
                      <button onClick={() => handleAction(c.id, "stop")} className="p-2 text-red-600 hover:bg-red-50 rounded-lg" title="Stop">
                        <Square size={16} />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
