"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { campaignsApi, scriptsApi } from "@/lib/api";
import { Upload, FileText, CheckCircle2 } from "lucide-react";

export default function NewCampaignPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Step 1
  const [name, setName] = useState("");
  const [direction, setDirection] = useState("outbound");
  const [scriptId, setScriptId] = useState("");
  const [scripts, setScripts] = useState<any[]>([]);

  // Step 2
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [campaignId, setCampaignId] = useState<string>("");

  // Step 3
  const [schedule, setSchedule] = useState({ start_time: "09:00", end_time: "18:00", timezone: "Asia/Kolkata" });
  const [settings, setSettings] = useState({ max_retries: 3, retry_interval_minutes: 30, concurrent_limit: 10 });

  useEffect(() => {
    const load = async () => {
      const { data } = await scriptsApi.list(1, 100);
      setScripts(data.scripts.filter((s: any) => s.audio_status === "ready"));
    };
    load();
  }, []);

  const handleCreateAndContinue = async () => {
    setError("");
    setLoading(true);
    try {
      const { data } = await campaignsApi.create({ name, script_id: scriptId, direction, settings });
      setCampaignId(data.id);
      setStep(2);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to create campaign");
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async () => {
    if (!csvFile || !campaignId) return;
    setLoading(true);
    setError("");
    try {
      const { data } = await campaignsApi.uploadPhones(campaignId, csvFile);
      setUploadResult(data);
      setStep(3);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Upload failed");
    } finally {
      setLoading(false);
    }
  };

  const handleStart = async () => {
    setLoading(true);
    try {
      await campaignsApi.start(campaignId);
      router.push(`/campaigns/${campaignId}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to start campaign");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold text-slate-900 mb-6">New Campaign</h1>

      {/* Steps */}
      <div className="flex gap-4 mb-8">
        {[
          { n: 1, label: "Details" },
          { n: 2, label: "Phone Numbers" },
          { n: 3, label: "Schedule" },
          { n: 4, label: "Review" },
        ].map((s) => (
          <div key={s.n} className={`flex items-center gap-2 ${step >= s.n ? "text-blue-600" : "text-slate-400"}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${step >= s.n ? "bg-blue-600 text-white" : "bg-slate-200"}`}>
              {step > s.n ? <CheckCircle2 size={16} /> : s.n}
            </div>
            <span className="text-sm font-medium hidden sm:inline">{s.label}</span>
          </div>
        ))}
      </div>

      {error && <div className="bg-red-50 text-red-600 p-3 rounded-lg mb-4 text-sm">{error}</div>}

      {/* Step 1: Details */}
      {step === 1 && (
        <div className="bg-white rounded-xl p-6 border border-slate-200">
          <h2 className="text-lg font-semibold mb-4">Campaign Details</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Campaign Name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" placeholder="Q4 Renewal Drive" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Direction</label>
              <select value={direction} onChange={(e) => setDirection(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm">
                <option value="outbound">Outbound</option>
                <option value="inbound">Inbound</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Select Script</label>
              {scripts.length === 0 ? (
                <p className="text-sm text-slate-500">No scripts with ready audio. <a href="/scripts/new" className="text-blue-600 hover:underline">Create one first</a>.</p>
              ) : (
                <select value={scriptId} onChange={(e) => setScriptId(e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm">
                  <option value="">Choose a script...</option>
                  {scripts.map((s) => (
                    <option key={s.id} value={s.id}>{s.name} (v{s.version})</option>
                  ))}
                </select>
              )}
            </div>
          </div>
          <div className="mt-6 flex justify-end">
            <button onClick={handleCreateAndContinue} disabled={!name || !scriptId || loading} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50">
              {loading ? "Creating..." : "Next"}
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Phone Numbers */}
      {step === 2 && (
        <div className="bg-white rounded-xl p-6 border border-slate-200">
          <h2 className="text-lg font-semibold mb-4">Upload Phone Numbers</h2>
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) setCsvFile(f); }}
            className="border-2 border-dashed border-slate-300 rounded-xl p-8 text-center hover:border-blue-400 transition-colors"
          >
            <Upload size={40} className="mx-auto mb-3 text-slate-400" />
            <p className="text-sm text-slate-600 mb-2">Drag & drop your CSV file here, or</p>
            <label className="inline-flex items-center gap-2 px-4 py-2 bg-slate-900 text-white rounded-lg text-sm cursor-pointer hover:bg-slate-800">
              <FileText size={16} />
              Browse Files
              <input type="file" accept=".csv" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) setCsvFile(f); }} />
            </label>
            <p className="text-xs text-slate-400 mt-3">CSV must have a &quot;phone_number&quot; column. Other columns become customer data.</p>
          </div>

          {csvFile && (
            <div className="mt-4 p-3 bg-slate-50 rounded-lg flex items-center justify-between">
              <span className="text-sm text-slate-700">{csvFile.name} ({(csvFile.size / 1024).toFixed(1)} KB)</span>
              <button onClick={() => setCsvFile(null)} className="text-sm text-red-600 hover:underline">Remove</button>
            </div>
          )}

          {uploadResult && (
            <div className="mt-4 p-4 bg-green-50 rounded-lg text-sm">
              <p className="font-medium text-green-700 mb-1">Upload Complete</p>
              <p>Valid: {uploadResult.valid} | Invalid: {uploadResult.invalid} | Duplicates removed: {uploadResult.duplicates_removed}</p>
            </div>
          )}

          <div className="mt-6 flex justify-between">
            <button onClick={() => setStep(1)} className="px-4 py-2 border border-slate-300 rounded-lg text-sm">Back</button>
            <button onClick={handleUpload} disabled={!csvFile || loading} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50">
              {loading ? "Uploading..." : "Upload & Continue"}
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Schedule */}
      {step === 3 && (
        <div className="bg-white rounded-xl p-6 border border-slate-200">
          <h2 className="text-lg font-semibold mb-4">Schedule & Settings</h2>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Start Time</label>
              <input type="time" value={schedule.start_time} onChange={(e) => setSchedule({ ...schedule, start_time: e.target.value })} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">End Time</label>
              <input type="time" value={schedule.end_time} onChange={(e) => setSchedule({ ...schedule, end_time: e.target.value })} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Concurrent Calls</label>
              <input type="number" value={settings.concurrent_limit} onChange={(e) => setSettings({ ...settings, concurrent_limit: +e.target.value })} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Max Retries</label>
              <input type="number" value={settings.max_retries} onChange={(e) => setSettings({ ...settings, max_retries: +e.target.value })} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Retry Interval (min)</label>
              <input type="number" value={settings.retry_interval_minutes} onChange={(e) => setSettings({ ...settings, retry_interval_minutes: +e.target.value })} className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm" />
            </div>
          </div>
          <div className="mt-6 flex justify-between">
            <button onClick={() => setStep(2)} className="px-4 py-2 border border-slate-300 rounded-lg text-sm">Back</button>
            <button onClick={() => setStep(4)} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium">Review</button>
          </div>
        </div>
      )}

      {/* Step 4: Review */}
      {step === 4 && (
        <div className="bg-white rounded-xl p-6 border border-slate-200">
          <h2 className="text-lg font-semibold mb-4">Review & Launch</h2>
          <div className="space-y-2 text-sm mb-6">
            <p><strong>Name:</strong> {name}</p>
            <p><strong>Direction:</strong> {direction}</p>
            <p><strong>Phone numbers:</strong> {uploadResult?.valid || 0}</p>
            <p><strong>Concurrent calls:</strong> {settings.concurrent_limit}</p>
            <p><strong>Schedule:</strong> {schedule.start_time} - {schedule.end_time}</p>
          </div>
          <div className="flex justify-between">
            <button onClick={() => setStep(3)} className="px-4 py-2 border border-slate-300 rounded-lg text-sm">Back</button>
            <div className="flex gap-3">
              <button onClick={() => router.push("/campaigns")} className="px-4 py-2 border border-slate-300 rounded-lg text-sm">Save Draft</button>
              <button onClick={handleStart} disabled={loading} className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm font-medium disabled:opacity-50">
                {loading ? "Starting..." : "Start Campaign"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
