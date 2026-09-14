import axios from "axios";
import { useAuth } from "./auth";

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL ?? "/api/v1", timeout: 15000 });

type RefreshResponse = { access: string; refresh?: string };
let activeRefresh: Promise<RefreshResponse> | null = null;

export function isAccessTokenFailure(error: unknown) {
  const response = (error as {
    response?: {
      status?: number;
      data?: { error?: { details?: { code?: string; detail?: { code?: string } } } };
      headers?: { get?: (name: string) => string | null; [key: string]: unknown };
    };
  })?.response;
  if (response?.status !== 401) return false;

  const details = response.data?.error?.details;
  const code = details?.code ?? details?.detail?.code;
  const headers = response.headers;
  const authenticate = typeof headers?.get === "function"
    ? headers.get("www-authenticate")
    : String(headers?.["www-authenticate"] ?? "");

  return code === "token_not_valid" || Boolean(authenticate?.toLowerCase().startsWith("bearer"));
}

function refreshAccessToken(refresh: string) {
  if (!activeRefresh) {
    activeRefresh = axios.post<RefreshResponse>(
      `${api.defaults.baseURL}/auth/token/refresh/`,
      { refresh },
    ).then((response) => response.data).finally(() => { activeRefresh = null; });
  }
  return activeRefresh;
}

api.interceptors.request.use((config) => {
  const token = useAuth.getState().accessToken;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  config.headers["X-Correlation-ID"] = crypto.randomUUID();
  return config;
});

api.interceptors.response.use(undefined, async (error) => {
  const request = error.config as (typeof error.config & { _chainControlRetry?: boolean }) | undefined;
  const auth = useAuth.getState();
  const accessTokenFailed = isAccessTokenFailure(error);
  if (accessTokenFailed && request && !request._chainControlRetry && auth.refreshToken) {
    request._chainControlRetry = true;
    try {
      const data = await refreshAccessToken(auth.refreshToken);
      auth.updateTokens(data.access, data.refresh);
      request.headers.Authorization = `Bearer ${data.access}`;
      return api(request);
    } catch {
      useAuth.getState().clear();
    }
  } else if (accessTokenFailed) {
    useAuth.getState().clear();
  }
  return Promise.reject(error);
});

export default api;
