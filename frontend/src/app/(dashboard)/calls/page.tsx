"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { callsApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { Phone, Radio, User, Bot } from "lucide-react";

export default function CallsPage() {
  const [tab, setTab] = useState<"live" | "history">("live");
  const [liveCalls, setLiveCalls] = useState<any[]>([]);
  const [historyCalls, setHistoryCalls] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [expandedCall, setExpandedCall] = useState<string | null>(null);
  const { company } = useAuthStore();
  const wsRef = useRef<WebSocket | null>(null);

  // Load history
  const loadHistory = async () => {
    try {
      const { data } = await callsApi.list({ page, page_size: 20 });
      setHistoryCalls(data.calls || []);
      setTotal(data.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Load live calls
  const loadLive = async () => {
    try {
      const { data } = await callsApi.getLive();
      setLiveCalls(data.live_calls || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (tab === "live") {
      loadLive();
      const interval = setInterval(loadLive, 5000);

      // WebSocket
      const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";
      const token = localStorage.getItem("access_token");
      if (company?.id && token) {
        try {
          wsRef.current = new WebSocket(`${wsUrl}/ws/calls/${company.id}?token=${token}`);
          wsRef.current.onmessage = (event) => {
            const data = JSON.parse(event.data);
            setLiveCalls((prev) => {
              const idx = prev.findIndex((c) => c.id === data.call_id);
              if (idx >= 0) {
                const updated = [...prev];
                updated[idx] = { ...updated[idx], ...data };
                return updated;
              }
              return prev;
            });
          };
        } catch {}
      }

      return () => {
        clearInterval(interval);
        wsRef.current?.close();
      };
    } else {
      loadHistory();
    }
  }, [tab, page]);

  const handleTakeover = async (callId: string) => {
    try {
      await callsApi.takeover(callId);
      loadLive();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Calls</h1>

      <div className="flex gap-1 mb-6 bg-slate-100 p-1 rounded-lg w-fit">
        <button onClick={() => setTab("live")} className={`px-4 py-1.5 rounded-md text-sm font-medium ${tab === "live" ? "bg-white shadow-sm text-slate-900" : "text-slate-500"}`}>
          <span className="flex items-center gap-2"><Radio size={14} className={tab === "live" ? "text-red-500" : ""} /> Live Calls</span>
        </button>
        <button onClick={() => setTab("history")} className={`px-4 py-1.5 rounded-md text-sm font-medium ${tab === "history" ? "bg-white shadow-sm text-slate-900" : "text-slate-500"}`}>
          Call History
        </button>
      </div>

      {tab === "live" ? (
        <div>
          {liveCalls.length === 0 ? (
            <div className="bg-white rounded-xl p-12 text-center border border-slate-200">
              <Phone size={48} className="mx-auto mb-4 text-slate-300" />
              <h3 className="text-lg font-medium text-slate-900 mb-2">No active calls</h3>
              <p className="text-slate-500">Active calls will appear here in real-time.</p>
            </div>
          ) : (
            <div className="grid gap-4">
              {liveCalls.map((call) => (
                <div key={call.id} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  <div
                    className="p-4 cursor-pointer hover:bg-slate-50"
                    onClick={() => setExpandedCall(expandedCall === call.id ? null : call.id)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse" />
                        <span className="font-mono text-sm">{call.phone_number}</span>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700`}>{call.status}</span>
                        <span className="text-sm text-slate-500">{call.duration}s</span>
                        <span className="text-xs text-slate-400">{call.language_used || "auto"}</span>
                        <span className="text-xs text-blue-600">{call.current_node || "-"}</span>
                      </div>
                      <button onClick={(e) => { e.stopPropagation(); handleTakeover(call.id); }} className="px-3 py-1 bg-red-600 text-white rounded text-xs hover:bg-red-700">
                        Take Over
                      </button>
                    </div>
                  </div>
                  {expandedCall === call.id && (
                    <div className="px-4 pb-4 border-t border-slate-100">
                      <div className="mt-3 space-y-2 max-h-60 overflow-y-auto">
                        {(call.transcript || []).map((entry: any, i: number) => (
                          <div key={i} className={`flex ${entry.role === "customer" ? "justify-start" : "justify-end"}`}>
                            <div className={`max-w-[70%] px-3 py-2 rounded-lg text-sm ${
                              entry.role === "customer" ? "bg-slate-100 text-slate-800" : "bg-blue-600 text-white"
                            }`}>
                              <div className="flex items-center gap-1 mb-1 opacity-75">
                                {entry.role === "customer" ? <User size={12} /> : <Bot size={12} />}
                                <span className="text-xs">{entry.role}</span>
                                {entry.node_key && <span className="text-xs ml-1">({entry.node_key})</span>}
                              </div>
                              {entry.text}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-slate-500 border-b border-slate-100">
                  <th className="px-5 py-3 font-medium">Phone</th>
                  <th className="px-5 py-3 font-medium">Direction</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Duration</th>
                  <th className="px-5 py-3 font-medium">Language</th>
                  <th className="px-5 py-3 font-medium">Sentiment</th>
                  <th className="px-5 py-3 font-medium">Date</th>
                </tr>
              </thead>
              <tbody>
                {historyCalls.map((call) => (
                  <tr key={call.id} className="border-b border-slate-50 hover:bg-slate-50">
                    <td className="px-5 py-3">
                      <Link href={`/calls/${call.id}`} className="text-sm font-mono text-blue-600 hover:underline">{call.phone_number}</Link>
                    </td>
                    <td className="px-5 py-3 text-sm text-slate-600">{call.direction}</td>
                    <td className="px-5 py-3">
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                        call.status === "completed" ? "bg-green-100 text-green-700" : call.status === "failed" ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"
                      }`}>{call.status}</span>
                    </td>
                    <td className="px-5 py-3 text-sm text-slate-600">{call.duration_seconds}s</td>
                    <td className="px-5 py-3 text-sm text-slate-600">{call.language_detected || "-"}</td>
                    <td className="px-5 py-3 text-sm text-slate-600">{call.sentiment_score?.toFixed(1) || "-"}</td>
                    <td className="px-5 py-3 text-sm text-slate-500">{new Date(call.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {total > 20 && (
            <div className="flex justify-center gap-2 p-4 border-t border-slate-100">
              <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1} className="px-3 py-1 border border-slate-300 rounded text-sm disabled:opacity-50">Previous</button>
              <span className="px-3 py-1 text-sm text-slate-600">Page {page}</span>
              <button onClick={() => setPage(page + 1)} disabled={page >= Math.ceil(total / 20)} className="px-3 py-1 border border-slate-300 rounded text-sm disabled:opacity-50">Next</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
