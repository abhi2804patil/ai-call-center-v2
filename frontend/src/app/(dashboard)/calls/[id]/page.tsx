"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { callsApi } from "@/lib/api";
import { User, Bot, Clock, Globe, TrendingUp } from "lucide-react";

export default function CallDetailPage() {
  const params = useParams();
  const callId = params.id as string;
  const [call, setCall] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await callsApi.get(callId);
        setCall(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [callId]);

  if (loading) return <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" /></div>;
  if (!call) return <div>Call not found</div>;

  const sentimentLabel = (score: number | null) => {
    if (score === null) return "N/A";
    if (score > 0.3) return "Positive";
    if (score < -0.3) return "Negative";
    return "Neutral";
  };

  const sentimentColor = (score: number | null) => {
    if (score === null) return "text-slate-500";
    if (score > 0.3) return "text-green-600";
    if (score < -0.3) return "text-red-600";
    return "text-yellow-600";
  };

  return (
    <div>
      <div className="flex items-center gap-4 mb-6">
        <h1 className="text-2xl font-bold text-slate-900">{call.phone_number}</h1>
        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
          call.status === "completed" ? "bg-green-100 text-green-700" : call.status === "failed" ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"
        }`}>{call.status}</span>
      </div>

      <div className="flex gap-4 mb-6 text-sm text-slate-500">
        <span className="flex items-center gap-1"><Clock size={14} /> {call.duration_seconds}s</span>
        <span className="flex items-center gap-1"><Globe size={14} /> {call.language_detected || "Unknown"}</span>
        <span>{call.direction}</span>
        <span>{new Date(call.created_at).toLocaleString()}</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Transcript */}
        <div className="lg:col-span-3 bg-white rounded-xl border border-slate-200 p-5">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Transcript</h2>
          <div className="space-y-3">
            {(call.transcript || []).map((entry: any, i: number) => (
              <div key={i} className={`flex ${entry.role === "customer" ? "justify-start" : entry.role === "system" ? "justify-center" : "justify-end"}`}>
                {entry.role === "system" ? (
                  <span className="text-xs text-slate-400 italic">{entry.text}</span>
                ) : (
                  <div className={`max-w-[75%] px-4 py-2.5 rounded-xl text-sm ${
                    entry.role === "customer" ? "bg-slate-100 text-slate-800 rounded-bl-none" : "bg-blue-600 text-white rounded-br-none"
                  }`}>
                    <div className="flex items-center gap-1.5 mb-1 opacity-75 text-xs">
                      {entry.role === "customer" ? <User size={12} /> : <Bot size={12} />}
                      <span className="font-medium">{entry.role === "customer" ? "Customer" : "AI"}</span>
                      {entry.node_key && <span className="ml-1">Node: {entry.node_key}</span>}
                    </div>
                    <p>{entry.text}</p>
                    {entry.intent && (
                      <p className="mt-1 text-xs opacity-75">Intent: {entry.intent} ({(entry.confidence * 100).toFixed(0)}%)</p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Details sidebar */}
        <div className="lg:col-span-2 space-y-4">
          {/* Summary */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h3 className="text-sm font-semibold text-slate-900 mb-2">AI Summary</h3>
            <p className="text-sm text-slate-600">{call.ai_summary || "Summary not yet generated."}</p>
          </div>

          {/* Sentiment */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h3 className="text-sm font-semibold text-slate-900 mb-2">Sentiment</h3>
            <div className="flex items-center gap-3">
              <TrendingUp size={20} className={sentimentColor(call.sentiment_score)} />
              <span className={`text-lg font-bold ${sentimentColor(call.sentiment_score)}`}>
                {sentimentLabel(call.sentiment_score)}
              </span>
              {call.sentiment_score !== null && (
                <span className="text-sm text-slate-500">({call.sentiment_score.toFixed(2)})</span>
              )}
            </div>
          </div>

          {/* Outcome Tags */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h3 className="text-sm font-semibold text-slate-900 mb-2">Outcome Tags</h3>
            <div className="flex flex-wrap gap-1">
              {(call.outcome_tags || []).length > 0 ? (
                call.outcome_tags.map((tag: string, i: number) => (
                  <span key={i} className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs">{tag}</span>
                ))
              ) : (
                <span className="text-sm text-slate-400">No tags</span>
              )}
            </div>
          </div>

          {/* Cost */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h3 className="text-sm font-semibold text-slate-900 mb-2">Cost Breakdown</h3>
            {Object.keys(call.cost_breakdown || {}).length > 0 ? (
              <div className="space-y-1 text-sm">
                {Object.entries(call.cost_breakdown).map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span className="text-slate-600 capitalize">{k}</span>
                    <span className="font-medium">&#8377;{String(v)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <span className="text-sm text-slate-400">Not available</span>
            )}
          </div>

          {/* Customer Data */}
          {call.metadata_ && Object.keys(call.metadata_).length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="text-sm font-semibold text-slate-900 mb-2">Customer Data</h3>
              <div className="space-y-1 text-sm">
                {Object.entries(call.metadata_).map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span className="text-slate-600">{k}</span>
                    <span className="font-medium">{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
