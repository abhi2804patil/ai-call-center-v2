"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { analyticsApi, callsApi } from "@/lib/api";
import { Phone, Megaphone, TrendingUp, Clock, Plus, FileText } from "lucide-react";

export default function DashboardPage() {
  const [stats, setStats] = useState<any>(null);
  const [recentCalls, setRecentCalls] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [dashRes, callsRes] = await Promise.all([
          analyticsApi.dashboard(),
          callsApi.list({ page: 1, page_size: 10 }),
        ]);
        setStats(dashRes.data.overview);
        setRecentCalls(callsRes.data.calls || []);
      } catch (err) {
        console.error("Failed to load dashboard:", err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  const statCards = [
    { label: "Total Calls", value: stats?.total_calls || 0, icon: Phone, color: "bg-blue-500" },
    { label: "Success Rate", value: `${stats?.success_rate || 0}%`, icon: TrendingUp, color: "bg-green-500" },
    { label: "Avg Duration", value: `${Math.round(stats?.avg_duration || 0)}s`, icon: Clock, color: "bg-purple-500" },
    { label: "Active Campaigns", value: stats?.total_calls ? "Active" : "None", icon: Megaphone, color: "bg-orange-500" },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
        <div className="flex gap-3">
          <Link
            href="/scripts/new"
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium"
          >
            <FileText size={16} />
            Create Script
          </Link>
          <Link
            href="/campaigns/new"
            className="flex items-center gap-2 px-4 py-2 bg-slate-900 text-white rounded-lg hover:bg-slate-800 text-sm font-medium"
          >
            <Plus size={16} />
            New Campaign
          </Link>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {statCards.map((card) => {
          const Icon = card.icon;
          return (
            <div key={card.label} className="bg-white rounded-xl p-5 shadow-sm border border-slate-200">
              <div className="flex items-center gap-3">
                <div className={`${card.color} p-2.5 rounded-lg`}>
                  <Icon size={20} className="text-white" />
                </div>
                <div>
                  <p className="text-sm text-slate-500">{card.label}</p>
                  <p className="text-2xl font-bold text-slate-900">{card.value}</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Recent Calls */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200">
        <div className="p-5 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900">Recent Calls</h2>
        </div>
        {recentCalls.length === 0 ? (
          <div className="p-8 text-center text-slate-500">
            <Phone size={40} className="mx-auto mb-3 text-slate-300" />
            <p>No calls yet. Create a script and start a campaign!</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-slate-500 border-b border-slate-100">
                  <th className="px-5 py-3 font-medium">Phone</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Duration</th>
                  <th className="px-5 py-3 font-medium">Language</th>
                  <th className="px-5 py-3 font-medium">Date</th>
                </tr>
              </thead>
              <tbody>
                {recentCalls.map((call) => (
                  <tr key={call.id} className="border-b border-slate-50 hover:bg-slate-50">
                    <td className="px-5 py-3 text-sm font-mono">{call.phone_number}</td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                          call.status === "completed"
                            ? "bg-green-100 text-green-700"
                            : call.status === "failed"
                            ? "bg-red-100 text-red-700"
                            : "bg-yellow-100 text-yellow-700"
                        }`}
                      >
                        {call.status}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-sm text-slate-600">{call.duration_seconds}s</td>
                    <td className="px-5 py-3 text-sm text-slate-600">{call.language_detected || "-"}</td>
                    <td className="px-5 py-3 text-sm text-slate-500">
                      {new Date(call.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
