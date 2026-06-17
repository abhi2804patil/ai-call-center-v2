"use client";

import { useState, useEffect } from "react";
import { useAuthStore } from "@/lib/store";
import { authApi } from "@/lib/api";
import { Copy, Eye, EyeOff, RefreshCw } from "lucide-react";

export default function SettingsPage() {
  const { company, user } = useAuthStore();
  const [showApiKey, setShowApiKey] = useState(false);
  const [copied, setCopied] = useState(false);

  const copyApiKey = () => {
    if (company?.api_key) {
      navigator.clipboard.writeText(company.api_key);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const maskedKey = company?.api_key
    ? company.api_key.substring(0, 6) + "..." + company.api_key.substring(company.api_key.length - 4)
    : "";

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Settings</h1>

      {/* Company Settings */}
      <div className="bg-white rounded-xl p-6 border border-slate-200 mb-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Company</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Company Name</label>
            <input value={company?.name || ""} readOnly className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
            <input value={company?.email || ""} readOnly className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Plan</label>
            <span className="inline-flex px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm font-medium capitalize">
              {company?.plan || "free"}
            </span>
          </div>
        </div>
      </div>

      {/* API Key */}
      <div className="bg-white rounded-xl p-6 border border-slate-200 mb-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">API Key</h2>
        <div className="flex items-center gap-2">
          <code className="flex-1 px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm font-mono">
            {showApiKey ? company?.api_key : maskedKey}
          </code>
          <button onClick={() => setShowApiKey(!showApiKey)} className="p-2 text-slate-600 hover:bg-slate-100 rounded-lg">
            {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
          <button onClick={copyApiKey} className="p-2 text-slate-600 hover:bg-slate-100 rounded-lg">
            <Copy size={16} />
          </button>
        </div>
        {copied && <p className="text-xs text-green-600 mt-1">Copied!</p>}
      </div>

      {/* User Info */}
      <div className="bg-white rounded-xl p-6 border border-slate-200 mb-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">User Profile</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Name</label>
            <input value={user?.full_name || ""} readOnly className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
            <input value={user?.email || ""} readOnly className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Role</label>
            <span className="inline-flex px-3 py-1 bg-slate-100 text-slate-700 rounded-full text-sm font-medium capitalize">
              {user?.role || "admin"}
            </span>
          </div>
        </div>
      </div>

      {/* Plan & Billing */}
      <div className="bg-white rounded-xl p-6 border border-slate-200">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Plan & Billing</h2>
        <div className="p-4 bg-slate-50 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-slate-700">Current Plan</span>
            <span className="text-sm font-bold text-blue-600 capitalize">{company?.plan || "Free"}</span>
          </div>
          <p className="text-xs text-slate-500">Contact support to upgrade your plan.</p>
        </div>
      </div>
    </div>
  );
}
