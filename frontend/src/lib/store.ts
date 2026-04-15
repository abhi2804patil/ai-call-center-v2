import { create } from "zustand";

interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  company_id: string;
  is_active: boolean;
}

interface Company {
  id: string;
  name: string;
  email: string;
  plan: string;
  api_key: string;
  settings: Record<string, any>;
}

interface AuthState {
  user: User | null;
  company: Company | null;
  isAuthenticated: boolean;
  setAuth: (user: User, company: Company, tokens: { access_token: string; refresh_token: string }) => void;
  setUser: (user: User) => void;
  setCompany: (company: Company) => void;
  logout: () => void;
  loadFromStorage: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  company: null,
  isAuthenticated: false,

  setAuth: (user, company, tokens) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("access_token", tokens.access_token);
      localStorage.setItem("refresh_token", tokens.refresh_token);
      localStorage.setItem("user", JSON.stringify(user));
      localStorage.setItem("company", JSON.stringify(company));
    }
    set({ user, company, isAuthenticated: true });
  },

  setUser: (user) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("user", JSON.stringify(user));
    }
    set({ user });
  },

  setCompany: (company) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("company", JSON.stringify(company));
    }
    set({ company });
  },

  logout: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("user");
      localStorage.removeItem("company");
    }
    set({ user: null, company: null, isAuthenticated: false });
  },

  loadFromStorage: () => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token");
      const userStr = localStorage.getItem("user");
      const companyStr = localStorage.getItem("company");

      if (token && userStr) {
        try {
          const user = JSON.parse(userStr);
          const company = companyStr ? JSON.parse(companyStr) : null;
          set({ user, company, isAuthenticated: true });
        } catch {
          set({ user: null, company: null, isAuthenticated: false });
        }
      }
    }
  },
}));
