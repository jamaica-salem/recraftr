import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const AuthContext = createContext(null);
const STORAGE_KEY = "rm_auth";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [ready, setReady] = useState(false);

  const persist = useCallback((tok, usr) => {
    if (tok && usr) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ token: tok, user: usr }));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
    setToken(tok);
    setUser(usr);
  }, []);

  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        if (parsed?.token) {
          setToken(parsed.token);
          setUser(parsed.user);
          // Validate token with backend
          axios
            .get(`${API}/auth/me`, {
              headers: { Authorization: `Bearer ${parsed.token}` },
            })
            .then((res) => {
              setUser(res.data);
            })
            .catch((err) => {
              if (err?.response?.status === 401) {
                console.warn("Stored auth token is invalid/expired. Clearing session.");
                persist(null, null);
              }
            })
            .finally(() => {
              setReady(true);
            });
          return;
        }
      } catch {
        localStorage.removeItem(STORAGE_KEY);
      }
    }
    setReady(true);
  }, [persist]);

  useEffect(() => {
    const interceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error?.response?.status === 401) {
          const detail = error?.response?.data?.detail;
          if (detail === "Invalid token" || detail === "Not authenticated") {
            persist(null, null);
          }
        }
        return Promise.reject(error);
      }
    );
    return () => axios.interceptors.response.eject(interceptor);
  }, [persist]);

  const login = async (email, password) => {
    const res = await axios.post(`${API}/auth/login`, { email, password });
    persist(res.data.token, res.data.user);
    return res.data.user;
  };

  const signup = async (name, email, password) => {
    const res = await axios.post(`${API}/auth/register`, { name, email, password });
    persist(res.data.token, res.data.user);
    return res.data.user;
  };

  const logout = () => persist(null, null);

  const authHeaders = token ? { Authorization: `Bearer ${token}` } : {};

  return (
    <AuthContext.Provider value={{ user, token, ready, login, signup, logout, authHeaders }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
