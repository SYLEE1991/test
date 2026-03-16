import { createContext, useContext, useState, useCallback } from 'react';

const AuthContext = createContext(null);

const STORAGE_KEYS = {
  token: 'erp_token',
  email: 'erp_email',
  serverUrl: 'erp_serverUrl',
  storeCode: 'erp_storeCode',
};

function loadAuth() {
  const token = localStorage.getItem(STORAGE_KEYS.token);
  const email = localStorage.getItem(STORAGE_KEYS.email);
  const serverUrl = localStorage.getItem(STORAGE_KEYS.serverUrl);
  if (token && email && serverUrl) {
    return { token, email, serverUrl };
  }
  return null;
}

export function loadStoreCode() {
  return localStorage.getItem(STORAGE_KEYS.storeCode) || '';
}

export function saveStoreCode(code) {
  if (code) {
    localStorage.setItem(STORAGE_KEYS.storeCode, code);
  } else {
    localStorage.removeItem(STORAGE_KEYS.storeCode);
  }
}

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(loadAuth);

  const login = useCallback((token, email, serverUrl) => {
    localStorage.setItem(STORAGE_KEYS.token, token);
    localStorage.setItem(STORAGE_KEYS.email, email);
    localStorage.setItem(STORAGE_KEYS.serverUrl, serverUrl);
    setAuth({ token, email, serverUrl });
  }, []);

  const logout = useCallback(() => {
    Object.values(STORAGE_KEYS).forEach((key) => localStorage.removeItem(key));
    setAuth(null);
  }, []);

  return (
    <AuthContext.Provider value={{ auth, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
