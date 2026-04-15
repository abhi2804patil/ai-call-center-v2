"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { campaignsApi } from "@/lib/api";
import { Play, Pause, Square, RefreshCw } from "lucide-react";

export default function CampaignDetailPage() {
  const params = useParams();
  const campaignId = params.id as string;
  const [campaign, setCampaign] = useState<any>(null);
  const [progress, setProgress] = useState<any>(null);
  const [phones, setPhones] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    try {
      const [campRes, progRes, phonesRes] = await Promise.all([
        campaignsApi.get(campaignId),
        campaignsApi.getProgress(campaignId),
        campaignsApi.getPhoneNumbers(campaignId),
      ]);
      setCampaign(campRes.data);
      setProgress(progRes.data);
      setPhones(phonesRes.data.phone_numbers || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [campaignId]);

  const handleAction = async (action: string) => {
    try {
      if (action === "start") await campaignsApi.start(campaignId);
      else if (action === "pause") await campaignsApi.pause(campaignId);
      else if (action === "resume") await campaignsApi.resume(campaignId);
      else if (action === "stop") await campaignsApi.stop(campaignId);
      loadData();
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) {
    return <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" /></div>;
  }

  if (!campaign) return <div>Campaign not found</div>;

  const statusColor: Record<string, string> = {
    active: "bg-green-100 text-green-700",
    paused: "bg-yellow-100 text-yellow-700",
    draft: "bg-slate-100 text-slate-600",
    completed: "bg-blue-100 text-blue-700",
    cancelled: "bg-red-100 text-red-700",
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{campaign.name}</h1>
          <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium mt-1 ${statusColor[campaign.status] || statusColor.draft}`}>
            {campaign.status}
          </span>
        </div>
        <div className="flex gap-2">
          {campaign.status === "draft" && <button onClick={() => handleAction("start")} className="flex items-center gap-1 px-3 py-1.5 bg-green-600 text-white rounded-lg text-sm"><Play size={14} /> Start</button>}
          {campaign.status === "active" && <button onClick={() => handleAction("pause")} className="flex items-center gap-1 px-3 py-1.5 bg-yellow-600 text-white rounded-lg text-sm"><Pause size={14} /> Pause</button>}
          {campaign.status === "paused" && <button onClick={() => handleAction("resume")} className="flex items-center gap-1 px-3 py-1.5 bg-green-600 text-white rounded-lg text-sm"><Play size={14} /> Resume</button>}
          {["active", "paused"].includes(campaign.status) && <button onClick={() => handleAction("stop")} className="flex items-center gap-1 px-3 py-1.5 bg-red-600 text-white rounded-lg text-sm"><Square size={14} /> Stop</button>}
          <button onClick={loadData} className="p-2 text-slate-600 hover:bg-slate-100 rounded-lg"><RefreshCw size={16} /></button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        {[
          { label: "Total", value: progress?.total || 0 },
          { label: "Called", value: progress?.called || 0 },
          { label: "Successful", value: progress?.succeeded || 0 },
          { label: "Failed", value: progress?.failed || 0 },
          { label: "Remaining", value: progress?.remaining || 0 },
        ].map((s) => (
          <div key={s.label} className="bg-white rounded-xl p-4 border border-slate-200 text-center">
            <p className="text-2xl font-bold text-slate-900">{s.value}</p>
            <p className="text-sm text-slate-500">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Progress bar */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 mb-6">
        <div className="flex justify-between text-sm mb-2">
          <span className="text-slate-700 font-medium">Progress</span>
          <span className="text-slate-500">{progress?.percent || 0}%</span>
        </div>
        <div className="h-3 bg-slate-200 rounded-full overflow-hidden">
          <div className="h-full bg-blue-600 rounded-full" style={{ width: `${progress?.percent || 0}%` }} />
        </div>
      </div>

      {/* Phone Numbers */}
      <div className="bg-white rounded-xl border border-slate-200">
        <div className="p-5 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900">Phone Numbers</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-sm text-slate-500 border-b border-slate-100">
                <th className="px-5 py-3 font-medium">Phone</th>
                <th className="px-5 py-3 font-medium">Customer Data</th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium">Attempts</th>
              </tr>
            </thead>
            <tbody>
              {phones.map((p) => (
                <tr key={p.id} className="border-b border-slate-50">
                  <td className="px-5 py-3 text-sm font-mono">{p.phone_number}</td>
                  <td className="px-5 py-3 text-sm text-slate-600">
                    {Object.entries(p.customer_data || {}).map(([k, v]) => `${k}: ${v}`).join(", ") || "-"}
                  </td>
                  <td className="px-5 py-3">
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                      p.status === "called" ? "bg-green-100 text-green-700" : p.status === "failed" ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-600"
                    }`}>{p.status}</span>
                  </td>
                  <td className="px-5 py-3 text-sm text-slate-600">{p.attempt_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
