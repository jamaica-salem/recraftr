import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import axios from "axios";
import { supabase } from "@/lib/supabaseClient";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [ready, setReady] = useState(false);

  // Sync profile details with backend
  const syncProfile = useCallback(async (jwtToken, fallbackUser) => {
    if (!jwtToken) return;
    try {
      const res = await axios.get(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${jwtToken}` },
      });
      if (res?.data) {
        setUser(res.data);
      }
    } catch (err) {
      console.warn("Could not sync backend profile with token:", err?.message);
      if (fallbackUser) {
        setUser(fallbackUser);
      }
    }
  }, []);

  useEffect(() => {
    // 1. Check existing session on mount
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session?.access_token) {
        setToken(session.access_token);
        const initialUser = {
          id: session.user.id,
          email: session.user.email,
          name: session.user.user_metadata?.name || session.user.email?.split("@")[0] || "User",
        };
        setUser(initialUser);
        syncProfile(session.access_token, initialUser).finally(() => setReady(true));
      } else {
        setToken(null);
        setUser(null);
        setReady(true);
      }
    });

    // 2. Listen for auth changes (sign in, sign out, token refresh)
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (event, session) => {
      if (session?.access_token) {
        setToken(session.access_token);
        const currentUser = {
          id: session.user.id,
          email: session.user.email,
          name: session.user.user_metadata?.name || session.user.email?.split("@")[0] || "User",
        };
        setUser(currentUser);
        syncProfile(session.access_token, currentUser);
      } else {
        setToken(null);
        setUser(null);
      }
      setReady(true);
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [syncProfile]);

  // Global Axios 401 interceptor
  useEffect(() => {
    const interceptor = axios.interceptors.response.use(
      (response) => response,
      async (error) => {
        if (error?.response?.status === 401) {
          const detail = error?.response?.data?.detail;
          if (detail === "Invalid token" || detail === "Not authenticated") {
            try {
              const { data, error: refreshError } = await supabase.auth.refreshSession();
              if (refreshError || !data?.session) {
                await supabase.auth.signOut();
                setUser(null);
                setToken(null);
              }
            } catch {
              setUser(null);
              setToken(null);
            }
          }
        }
        return Promise.reject(error);
      }
    );
    return () => axios.interceptors.response.eject(interceptor);
  }, []);

  const login = async (email, password) => {
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      throw error;
    }
    const session = data.session;
    const initialUser = {
      id: session.user.id,
      email: session.user.email,
      name: session.user.user_metadata?.name || session.user.email?.split("@")[0] || "User",
    };
    setToken(session.access_token);
    setUser(initialUser);
    syncProfile(session.access_token, initialUser);
    return initialUser;
  };

  const signup = async (name, email, password) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: { name },
      },
    });
    if (error) {
      throw error;
    }
    const session = data.session;
    if (session) {
      const initialUser = {
        id: session.user.id,
        email: session.user.email,
        name: name || session.user.email?.split("@")[0] || "User",
      };
      setToken(session.access_token);
      setUser(initialUser);
      syncProfile(session.access_token, initialUser);
      return initialUser;
    }
    // If Supabase has email confirmation enabled and session is not immediately returned
    return data.user;
  };

  const logout = async () => {
    try {
      await supabase.auth.signOut();
    } finally {
      setUser(null);
      setToken(null);
    }
  };

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
