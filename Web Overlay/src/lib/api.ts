import { invoke } from '@tauri-apps/api/core';

export interface BackendConnectionInfo {
  baseUrl: string;
  token: string;
  ready: boolean;
  appdataDir: string;
}
export interface AugmentItem {
  id: string | number;
  name: string;
  image: string;
  tier?: number;
  is_destiny?: boolean;
}
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));
const errorText = (error: unknown) => error instanceof Error ? error.message : String(error);

export class StudioApiService {
  private connection: BackendConnectionInfo | null = null;
  private initializing: Promise<BackendConnectionInfo> | null = null;
  private preview: Window | null = null;
  public isTauri(): boolean { return '__TAURI_INTERNALS__' in window; }
  public invalidateConnection(): void { this.connection = null; this.initializing = null; }
  public pair(token: string): void {
    sessionStorage.setItem('studio-token', token.trim());
    this.invalidateConnection();
  }
  public async getConnectionInfo(): Promise<BackendConnectionInfo> {
    if (this.connection) return this.connection;
    if (this.initializing) return this.initializing;
    this.initializing = this.connect();
    try { return await this.initializing; }
    finally { this.initializing = null; }
  }
  private async connect(): Promise<BackendConnectionInfo> {
    // URL fragments are not sent in HTTP requests or referrer headers.
    const fragment = new URLSearchParams(location.hash.slice(1));
    if (fragment.has('token')) {
      sessionStorage.setItem('studio-token', fragment.get('token') || '');
      history.replaceState(null, '', location.pathname + location.search);
    }
    const deadline = Date.now() + 15000;
    let lastError = 'Backend chưa sẵn sàng';
    while (Date.now() < deadline) {
      try {
        let conn: BackendConnectionInfo;
        const legacyDesktop = new URLSearchParams(location.search).get('desktop') === 'pywebview';
        if (legacyDesktop && !window.pywebview?.api?.get_backend_connection_info) {
          await delay(200);
          continue;
        }
        if (this.isTauri() || window.pywebview?.api?.get_backend_connection_info) {
          const info = this.isTauri()
            ? await invoke<any>('get_backend_connection_info')
            : await window.pywebview!.api!.get_backend_connection_info!();
          if (info.error) throw new Error(info.error);
          if (!info.ready) { await delay(200); continue; }
          conn = {baseUrl: info.base_url, token: info.token, ready: true, appdataDir: info.appdata_dir || ''};
        } else {
          if (location.protocol === 'file:') { await delay(200); continue; }
          const hosted = location.pathname.startsWith('/app');
          const baseUrl = import.meta.env.VITE_BACKEND_URL || (hosted ? location.origin : 'http://127.0.0.1:8080');
          conn = {baseUrl, token: sessionStorage.getItem('studio-token') || '', ready: true, appdataDir: ''};
        }
        const health = await fetch(`${conn.baseUrl}/api/status`, {signal: AbortSignal.timeout(1500)});
        if (!health.ok || !(await health.json()).ready) throw new Error('Backend đang khởi động');
        this.connection = conn;
        return conn;
      } catch (error) { lastError = errorText(error); }
      await delay(300);
    }
    throw new Error(`Không kết nối được backend: ${lastError}. Kiểm tra cổng hoặc khởi động lại ứng dụng.`);
  }
  private async request(endpoint: string, body?: unknown): Promise<any> {
    const conn = await this.getConnectionInfo();
    if (body !== undefined && !conn.token) throw new Error('Mở Browser Panel từ ứng dụng desktop để ghép cặp phiên.');
    const response = await fetch(`${conn.baseUrl}${endpoint}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: {'Content-Type': 'application/json', ...(conn.token ? {'X-Studio-Token': conn.token} : {})},
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(45000),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : data.error || `HTTP ${response.status}`);
    return data;
  }
  public async getAugmentsList(): Promise<AugmentItem[]> { return (await this.request('/api/augments')).augments; }
  public getConfig(): Promise<any> { return this.request('/api/config'); }
  public getAppState(): Promise<any> { return this.request('/api/state'); }
  public saveConfig(data: unknown): Promise<any> { return this.request('/api/config', data); }
  public saveCustomAugments(augments: (string | null)[]): Promise<any> { return this.request('/api/augments', {custom_augments: augments}); }
  public renderOverlay(): Promise<any> { return this.request('/api/render', {}); }
  public fetchLatestMatch(): Promise<any> { return this.request('/api/riot/fetch', {}); }
  public saveRiotSettings(settings: {riot_id: string; region: string; api_key?: string}): Promise<any> { return this.request('/api/riot/settings', settings); }
  public async exportOverlayImage(): Promise<{success: boolean; filePath?: string; error?: string}> {
    try {
      const result = await this.request('/api/export', {});
      return {success: result.success, filePath: result.file_path, error: result.error};
    } catch (error) { return {success: false, error: errorText(error)}; }
  }
  public async openOutputFolder(): Promise<void> { if (this.isTauri()) await invoke('open_app_folder', {folderType: 'output'}); }
  public async openLogsFolder(): Promise<void> { if (this.isTauri()) await invoke('open_app_folder', {folderType: 'logs'}); }
  public async openBrowserPanel(): Promise<void> {
    if (this.isTauri()) await invoke('open_browser_panel');
    else {
      const conn = await this.getConnectionInfo();
      window.open(`${conn.baseUrl}/app/#token=${encodeURIComponent(conn.token)}`, '_blank', 'noopener');
    }
  }
  public async openObsOverlayWindow(): Promise<void> { await this.toggleOverlayVisibility(true); }
  public async closePanel(): Promise<void> { /* Panel state is independent of backend lifetime. */ }
  public async toggleOverlayVisibility(visible: boolean): Promise<boolean> {
    if (this.isTauri()) return invoke<boolean>('set_preview_visibility', {visible});
    if (window.pywebview?.api?.toggle_overlay_visibility) return window.pywebview.api.toggle_overlay_visibility(visible);
    if (!visible) { this.preview?.close(); this.preview = null; return false; }
    this.preview = window.open('', 'tft-overlay-preview', 'width=960,height=540');
    if (!this.preview) throw new Error('Trình duyệt đang chặn cửa sổ preview. Hãy cho phép popup.');
    const conn = await this.getConnectionInfo();
    this.preview.location.href = `${conn.baseUrl}/overlay`;
    return true;
  }
}
export const StudioApi = new StudioApiService();
