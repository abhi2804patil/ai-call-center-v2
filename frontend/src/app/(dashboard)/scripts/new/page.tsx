"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { scriptsApi, audioApi } from "@/lib/api";
import { Plus, Trash2, X } from "lucide-react";

const LANGUAGES = [
  { code: "hi", name: "Hindi" }, { code: "en", name: "English" },
  { code: "ta", name: "Tamil" }, { code: "te", name: "Telugu" },
  { code: "bn", name: "Bengali" }, { code: "mr", name: "Marathi" },
  { code: "gu", name: "Gujarati" }, { code: "kn", name: "Kannada" },
  { code: "ml", name: "Malayalam" }, { code: "od", name: "Odia" },
  { code: "pa", name: "Punjabi" },
];

const DYNAMIC_SLOTS = ["customer_name", "amount", "date", "policy_number"];

const DEFAULT_NODES = [
  { key: "greeting", text: {}, dynamic_slots: [] as string[], next_action: "listen", fixed: true },
  { key: "interested", text: {}, dynamic_slots: [] as string[], next_action: "listen", fixed: false },
  { key: "not_interested", text: {}, dynamic_slots: [] as string[], next_action: "listen", fixed: false },
  { key: "callback", text: {}, dynamic_slots: [] as string[], next_action: "listen", fixed: false },
  { key: "closing", text: {}, dynamic_slots: [] as string[], next_action: "end", fixed: true },
  { key: "fallback", text: {}, dynamic_slots: [] as string[], next_action: "listen", fixed: true },
  { key: "transfer", text: {}, dynamic_slots: [] as string[], next_action: "transfer", fixed: true },
];

export default function NewScriptPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Step 1
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  // Step 2
  const [voiceId, setVoiceId] = useState("meera");
  const [selectedLangs, setSelectedLangs] = useState<string[]>(["hi", "en"]);

  // Step 3
  const [nodes, setNodes] = useState(DEFAULT_NODES.map((n) => ({ ...n, text: {} as Record<string, string> })));

  // Step 4
  const [intentMap, setIntentMap] = useState<Record<string, string[]>>({
    interested: ["haan", "yes", "proceed", "okay"],
    not_interested: ["nahi", "no", "cancel"],
    callback: ["baad mein", "later", "kal"],
    transfer: ["agent", "human", "manager"],
  });

  // Step 5
  const [guardrails, setGuardrails] = useState<string[]>(["Never discuss competitors"]);
  const [newGuardrail, setNewGuardrail] = useState("");

  const toggleLang = (code: string) => {
    setSelectedLangs((prev) =>
      prev.includes(code) ? prev.filter((l) => l !== code) : [...prev, code]
    );
  };

  const updateNodeText = (idx: number, lang: string, text: string) => {
    const updated = [...nodes];
    updated[idx] = { ...updated[idx], text: { ...updated[idx].text, [lang]: text } };
    setNodes(updated);
  };

  const toggleNodeSlot = (idx: number, slot: string) => {
    const updated = [...nodes];
    const slots = updated[idx].dynamic_slots;
    updated[idx] = {
      ...updated[idx],
      dynamic_slots: slots.includes(slot) ? slots.filter((s) => s !== slot) : [...slots, slot],
    };
    setNodes(updated);
  };

  const addNode = () => {
    const key = `custom_${nodes.length}`;
    setNodes([...nodes, { key, text: {}, dynamic_slots: [], next_action: "listen", fixed: false }]);
  };

  const removeNode = (idx: number) => {
    if (!nodes[idx].fixed) {
      setNodes(nodes.filter((_, i) => i !== idx));
    }
  };

  const updateIntentKeywords = (intent: string, keywords: string) => {
    setIntentMap({ ...intentMap, [intent]: keywords.split(",").map((k) => k.trim()).filter(Boolean) });
  };

  const handleSave = async (generateAudio: boolean) => {
    setError("");
    setLoading(true);

    const nodesObj: Record<string, any> = {};
    nodes.forEach((n) => {
      nodesObj[n.key] = {
        text: n.text,
        dynamic_slots: n.dynamic_slots,
        next_action: n.next_action,
      };
    });

    const content = {
      persona: "AI Call Agent",
      default_language: selectedLangs[0] || "hi",
      supported_languages: selectedLangs,
      voice_id: voiceId,
      nodes: nodesObj,
      intent_map: intentMap,
      escalation: { trigger: "customer asks for human agent", fallback_number: "+919999999999" },
      guardrails,
    };

    try {
      const { data } = await scriptsApi.create({ name, description, content });
      if (generateAudio) {
        await audioApi.generate(data.id);
      }
      router.push("/scripts");
    } catch (err: any) {
      setError(err.response?.data?.detail?.validation_errors?.join(", ") || err.response?.data?.detail || "Failed to create script");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Create Script</h1>

      {/* Step indicator */}
      <div className="flex gap-2 mb-8">
        {[1, 2, 3, 4, 5, 6].map((s) => (
          <button
            key={s}
            onClick={() => setStep(s)}
            className={`flex-1 h-2 rounded-full transition-colors ${
              s <= step ? "bg-blue-600" : "bg-slate-200"
            }`}
          />
        ))}
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 p-3 rounded-lg mb-4 text-sm">{error}</div>
      )}

      {/* Step 1: Basics */}
      {step === 1 && (
        <div className="bg-white rounded-xl p-6 border border-slate-200">
          <h2 className="text-lg font-semibold mb-4">Basics</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Script Name</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Insurance Renewal Campaign"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows={3}
                placeholder="Describe the purpose of this script..."
              />
            </div>
          </div>
          <div className="mt-6 flex justify-end">
            <button onClick={() => setStep(2)} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium">
              Next
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Voice & Language */}
      {step === 2 && (
        <div className="bg-white rounded-xl p-6 border border-slate-200">
          <h2 className="text-lg font-semibold mb-4">Voice & Language</h2>
          <div className="mb-6">
            <label className="block text-sm font-medium text-slate-700 mb-3">Voice</label>
            <div className="flex gap-4">
              {[
                { id: "meera", label: "Meera (Female)" },
                { id: "arvind", label: "Arvind (Male)" },
              ].map((v) => (
                <label
                  key={v.id}
                  className={`flex items-center gap-2 px-4 py-3 border rounded-lg cursor-pointer transition-colors ${
                    voiceId === v.id ? "border-blue-600 bg-blue-50" : "border-slate-300"
                  }`}
                >
                  <input
                    type="radio"
                    name="voice"
                    value={v.id}
                    checked={voiceId === v.id}
                    onChange={(e) => setVoiceId(e.target.value)}
                    className="text-blue-600"
                  />
                  {v.label}
                </label>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-3">Languages</label>
            <div className="grid grid-cols-3 gap-2">
              {LANGUAGES.map((l) => (
                <label
                  key={l.code}
                  className={`flex items-center gap-2 px-3 py-2 border rounded-lg cursor-pointer text-sm ${
                    selectedLangs.includes(l.code) ? "border-blue-600 bg-blue-50" : "border-slate-300"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedLangs.includes(l.code)}
                    onChange={() => toggleLang(l.code)}
                    className="text-blue-600 rounded"
                  />
                  {l.name}
                </label>
              ))}
            </div>
          </div>
          <div className="mt-6 flex justify-between">
            <button onClick={() => setStep(1)} className="px-4 py-2 border border-slate-300 rounded-lg text-sm">Back</button>
            <button onClick={() => setStep(3)} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium">Next</button>
          </div>
        </div>
      )}

      {/* Step 3: Script Nodes */}
      {step === 3 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Script Nodes</h2>
            <button onClick={addNode} className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm">
              <Plus size={14} /> Add Node
            </button>
          </div>
          {nodes.map((node, idx) => (
            <div key={idx} className="bg-white rounded-xl p-5 border border-slate-200">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <input
                    value={node.key}
                    onChange={(e) => {
                      if (!node.fixed) {
                        const updated = [...nodes];
                        updated[idx] = { ...updated[idx], key: e.target.value };
                        setNodes(updated);
                      }
                    }}
                    disabled={node.fixed}
                    className="font-medium text-slate-900 bg-transparent border-b border-dashed border-slate-300 focus:outline-none focus:border-blue-500 px-0"
                  />
                  {node.fixed && <span className="text-xs text-slate-400">Required</span>}
                </div>
                <div className="flex items-center gap-2">
                  <select
                    value={node.next_action}
                    onChange={(e) => {
                      const updated = [...nodes];
                      updated[idx] = { ...updated[idx], next_action: e.target.value };
                      setNodes(updated);
                    }}
                    className="text-sm border border-slate-300 rounded px-2 py-1"
                  >
                    <option value="listen">Listen</option>
                    <option value="end">End</option>
                    <option value="transfer">Transfer</option>
                  </select>
                  {!node.fixed && (
                    <button onClick={() => removeNode(idx)} className="p-1 text-red-500 hover:bg-red-50 rounded">
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              </div>

              {selectedLangs.map((lang) => (
                <div key={lang} className="mb-2">
                  <label className="block text-xs text-slate-500 mb-1">
                    {LANGUAGES.find((l) => l.code === lang)?.name || lang}
                  </label>
                  <textarea
                    value={node.text[lang] || ""}
                    onChange={(e) => updateNodeText(idx, lang, e.target.value)}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                    rows={2}
                    placeholder={`Text in ${lang}... Use {slot_name} for dynamic data`}
                  />
                </div>
              ))}

              <div className="mt-2">
                <span className="text-xs text-slate-500 mr-2">Dynamic slots:</span>
                {DYNAMIC_SLOTS.map((slot) => (
                  <label key={slot} className="inline-flex items-center gap-1 mr-3 text-xs">
                    <input
                      type="checkbox"
                      checked={node.dynamic_slots.includes(slot)}
                      onChange={() => toggleNodeSlot(idx, slot)}
                      className="rounded text-blue-600"
                    />
                    {`{${slot}}`}
                  </label>
                ))}
              </div>
            </div>
          ))}
          <div className="flex justify-between">
            <button onClick={() => setStep(2)} className="px-4 py-2 border border-slate-300 rounded-lg text-sm">Back</button>
            <button onClick={() => setStep(4)} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium">Next</button>
          </div>
        </div>
      )}

      {/* Step 4: Intent Map */}
      {step === 4 && (
        <div className="bg-white rounded-xl p-6 border border-slate-200">
          <h2 className="text-lg font-semibold mb-4">Intent Mapping</h2>
          <p className="text-sm text-slate-500 mb-4">Define keywords for each intent. Separate with commas.</p>
          {nodes.filter((n) => !["greeting", "closing", "fallback", "transfer"].includes(n.key)).map((node) => (
            <div key={node.key} className="mb-4">
              <label className="block text-sm font-medium text-slate-700 mb-1">{node.key}</label>
              <input
                value={(intentMap[node.key] || []).join(", ")}
                onChange={(e) => updateIntentKeywords(node.key, e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="keyword1, keyword2, keyword3..."
              />
            </div>
          ))}
          <div className="mt-6 flex justify-between">
            <button onClick={() => setStep(3)} className="px-4 py-2 border border-slate-300 rounded-lg text-sm">Back</button>
            <button onClick={() => setStep(5)} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium">Next</button>
          </div>
        </div>
      )}

      {/* Step 5: Guardrails */}
      {step === 5 && (
        <div className="bg-white rounded-xl p-6 border border-slate-200">
          <h2 className="text-lg font-semibold mb-4">Guardrails</h2>
          <div className="space-y-2 mb-4">
            {guardrails.map((g, i) => (
              <div key={i} className="flex items-center gap-2 bg-slate-50 px-3 py-2 rounded-lg">
                <span className="flex-1 text-sm">{g}</span>
                <button onClick={() => setGuardrails(guardrails.filter((_, j) => j !== i))} className="text-red-500">
                  <X size={14} />
                </button>
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              value={newGuardrail}
              onChange={(e) => setNewGuardrail(e.target.value)}
              className="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm"
              placeholder="Add a guardrail..."
              onKeyDown={(e) => {
                if (e.key === "Enter" && newGuardrail.trim()) {
                  setGuardrails([...guardrails, newGuardrail.trim()]);
                  setNewGuardrail("");
                }
              }}
            />
            <button
              onClick={() => { if (newGuardrail.trim()) { setGuardrails([...guardrails, newGuardrail.trim()]); setNewGuardrail(""); } }}
              className="px-3 py-2 bg-slate-900 text-white rounded-lg text-sm"
            >
              Add
            </button>
          </div>
          <div className="mt-6 flex justify-between">
            <button onClick={() => setStep(4)} className="px-4 py-2 border border-slate-300 rounded-lg text-sm">Back</button>
            <button onClick={() => setStep(6)} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium">Review</button>
          </div>
        </div>
      )}

      {/* Step 6: Review & Save */}
      {step === 6 && (
        <div className="bg-white rounded-xl p-6 border border-slate-200">
          <h2 className="text-lg font-semibold mb-4">Review & Save</h2>
          <div className="space-y-3 mb-6 text-sm">
            <p><strong>Name:</strong> {name}</p>
            <p><strong>Voice:</strong> {voiceId}</p>
            <p><strong>Languages:</strong> {selectedLangs.join(", ")}</p>
            <p><strong>Nodes:</strong> {nodes.length}</p>
            <p><strong>Total audio files needed:</strong> {nodes.length * selectedLangs.length}</p>
            <p><strong>Guardrails:</strong> {guardrails.length}</p>
          </div>
          <div className="flex justify-between">
            <button onClick={() => setStep(5)} className="px-4 py-2 border border-slate-300 rounded-lg text-sm">Back</button>
            <div className="flex gap-3">
              <button
                onClick={() => handleSave(false)}
                disabled={loading}
                className="px-4 py-2 border border-slate-300 rounded-lg text-sm hover:bg-slate-50 disabled:opacity-50"
              >
                Save as Draft
              </button>
              <button
                onClick={() => handleSave(true)}
                disabled={loading}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium disabled:opacity-50"
              >
                {loading ? "Saving..." : "Save & Generate Audio"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
