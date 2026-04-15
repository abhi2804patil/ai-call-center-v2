"use client";

import { useEffect, useState } from "react";
import { analyticsApi } from "@/lib/api";
import { Phone, TrendingUp, Clock, DollarSign, Download } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from "recharts";

export default function AnalyticsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [dateRange, setDateRange] = useState("30");

  useEffect(() => {
    const load = async () => {
      try {
        const endDate = new Date().toISOString().split("T")[0];
        const startDate = new Date(Date.now() - parseInt(dateRange) * 24 * 60 * 60 * 1000).toISOString().split("T")[0];
        const { data: res } = await analyticsApi.dashboard({ start_date: startDate, end_date: endDate });
        setData(res);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [dateRange]);

  const handleExport = async () => {
    try {
      const response = await analyticsApi.export();
      const blob = new Blob([response.data], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "analytics_export.csv";
      a.click();
    } catch (err) {
      console.error(err);
    }
  };

  if (loading) return <div className="flex justify-center py-12"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" /></div>;

  const overview = data?.overview || {};
  const trends = data?.trends || [];
  const topCampaigns = data?.top_campaigns || [];
  const langBreakdown = Object.entries(overview.language_breakdown || {}).map(([lang, count]) => ({ lang: lang.toUpperCase(), count }));

  const kpiCards = [
    { label: "Total Calls", value: overview.total_calls || 0, icon: Phone, color: "bg-blue-500" },
    { label: "Success Rate", value: `${overview.success_rate || 0}%`, icon: TrendingUp, color: "bg-green-500" },
    { label: "Avg Duration", value: `${Math.round(overview.avg_duration || 0)}s`, icon: Clock, color: "bg-purple-500" },
    { label: "Total Cost", value: `₹${(overview.total_cost || 0).toFixed(0)}`, icon: DollarSign, color: "bg-orange-500" },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Analytics</h1>
        <div className="flex items-center gap-3">
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm"
          >
            <option value="7">Last 7 days</option>
            <option value="14">Last 14 days</option>
            <option value="30">Last 30 days</option>
            <option value="90">Last 90 days</option>
          </select>
          <button onClick={handleExport} className="flex items-center gap-2 px-4 py-2 bg-slate-900 text-white rounded-lg text-sm hover:bg-slate-800">
            <Download size={16} />
            Export CSV
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {kpiCards.map((card) => {
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

      {/* Call Volume Chart */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 mb-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Call Volume</h2>
        {trends.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trends}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} stroke="#94a3b8" />
              <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
              <Tooltip />
              <Line type="monotone" dataKey="total_calls" stroke="#3b82f6" strokeWidth={2} name="Total" />
              <Line type="monotone" dataKey="successful_calls" stroke="#22c55e" strokeWidth={2} name="Successful" />
              <Line type="monotone" dataKey="failed_calls" stroke="#ef4444" strokeWidth={2} name="Failed" />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-center py-12 text-slate-400">No data for this period</p>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Language Distribution */}
        <div className="bg-white rounded-xl p-5 border border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Language Distribution</h2>
          {langBreakdown.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={langBreakdown}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="lang" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-center py-12 text-slate-400">No language data</p>
          )}
        </div>

        {/* Top Campaigns */}
        <div className="bg-white rounded-xl p-5 border border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Top Campaigns</h2>
          {topCampaigns.length > 0 ? (
            <div className="space-y-3">
              {topCampaigns.map((c: any) => (
                <div key={c.campaign_id} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                  <div>
                    <p className="text-sm font-medium text-slate-900">{c.name}</p>
                    <p className="text-xs text-slate-500">{c.total_calls} calls</p>
                  </div>
                  <span className={`text-sm font-bold ${c.success_rate >= 70 ? "text-green-600" : c.success_rate >= 40 ? "text-yellow-600" : "text-red-600"}`}>
                    {c.success_rate}%
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center py-12 text-slate-400">No campaign data</p>
          )}
        </div>
      </div>
    </div>
  );
}
