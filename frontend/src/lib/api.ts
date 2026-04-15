import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// Auth
export const authApi = {
  register: (data: { name: string; email: string; password: string; full_name: string }) =>
    api.post("/auth/register", data),
  login: (data: { email: string; password: string }) =>
    api.post("/auth/login", data),
  refresh: (refresh_token: string) =>
    api.post("/auth/refresh", { refresh_token }),
  getMe: () => api.get("/auth/me"),
  getCompany: () => api.get("/auth/company"),
};

// Scripts
export const scriptsApi = {
  list: (page = 1, pageSize = 20, search?: string) =>
    api.get("/scripts", { params: { page, page_size: pageSize, search } }),
  get: (id: string) => api.get(`/scripts/${id}`),
  create: (data: any) => api.post("/scripts", data),
  update: (id: string, data: any) => api.put(`/scripts/${id}`, data),
  delete: (id: string) => api.delete(`/scripts/${id}`),
  duplicate: (id: string) => api.post(`/scripts/${id}/duplicate`),
  getNodes: (id: string) => api.get(`/scripts/${id}/nodes`),
  testIntent: (id: string, data: { text: string; language: string }) =>
    api.post(`/scripts/${id}/test-intent`, data),
};

// Audio
export const audioApi = {
  generate: (scriptId: string) => api.post(`/audio/generate/${scriptId}`),
  generateSingle: (scriptId: string, data: { node_key: string; language_code: string }) =>
    api.post(`/audio/generate-single/${scriptId}`, data),
  preview: (data: { text: string; language_code: string; voice_id: string }) =>
    api.post("/audio/preview", data, { responseType: "blob" }),
  list: (scriptId: string) => api.get(`/audio/${scriptId}`),
  get: (scriptId: string, nodeKey: string, langCode: string) =>
    api.get(`/audio/${scriptId}/${nodeKey}/${langCode}`),
  deleteAll: (scriptId: string) => api.delete(`/audio/${scriptId}`),
};

// Campaigns
export const campaignsApi = {
  list: (page = 1, pageSize = 20, status?: string) =>
    api.get("/campaigns", { params: { page, page_size: pageSize, status } }),
  get: (id: string) => api.get(`/campaigns/${id}`),
  create: (data: any) => api.post("/campaigns", data),
  update: (id: string, data: any) => api.put(`/campaigns/${id}`, data),
  delete: (id: string) => api.delete(`/campaigns/${id}`),
  uploadPhones: (id: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post(`/campaigns/${id}/upload-phones`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  start: (id: string) => api.post(`/campaigns/${id}/start`),
  pause: (id: string) => api.post(`/campaigns/${id}/pause`),
  resume: (id: string) => api.post(`/campaigns/${id}/resume`),
  stop: (id: string) => api.post(`/campaigns/${id}/stop`),
  getProgress: (id: string) => api.get(`/campaigns/${id}/progress`),
  getPhoneNumbers: (id: string, page = 1, status?: string) =>
    api.get(`/campaigns/${id}/phone-numbers`, { params: { page, status } }),
};

// Calls
export const callsApi = {
  list: (params: any) => api.get("/calls", { params }),
  get: (id: string) => api.get(`/calls/${id}`),
  getLive: () => api.get("/calls/live"),
  takeover: (id: string) => api.post(`/calls/${id}/takeover`),
};

// Analytics
export const analyticsApi = {
  dashboard: (params?: { start_date?: string; end_date?: string; campaign_id?: string }) =>
    api.get("/analytics/dashboard", { params }),
  campaignAnalytics: (id: string, params?: any) =>
    api.get(`/analytics/campaigns/${id}`, { params }),
  export: (params?: { start_date?: string; end_date?: string }) =>
    api.get("/analytics/export", { params, responseType: "blob" }),
};

export default api;
