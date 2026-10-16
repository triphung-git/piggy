/**
 * Web Overlay/src/lib/api.ts
 * --------------------------
 * API Facade thống nhất cho TFT Post-Match Studio.
 * Tự động phát hiện môi trường chạy (Tauri v2 IPC hoặc Browser thông thường),
 * thay thế 1-1 cho `window.pywebview.api`.
 */

import { invoke } from '@tauri-apps/api/core';
import { toPng } from 'html-to-image';

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

class StudioApiService {
  private _cachedConnection: BackendConnectionInfo | null = null;
  private _initPromise: Promise<BackendConnectionInfo> | null = null;

  public isTauri(): boolean {
    return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
  }

  public async getConnectionInfo(): Promise<BackendConnectionInfo> {
    if (this._cachedConnection) {
      return this._cachedConnection;
    }

    if (this._initPromise) {
      return this._initPromise;
    }

    this._initPromise = (async () => {
      if (this.isTauri()) {
        try {
          const info = await invoke<any>('get_backend_connection_info');
          this._cachedConnection = {
            baseUrl: info.base_url || 'http://127.0.0.1:8080',
            token: info.token || '',
            ready: Boolean(info.ready),
            appdataDir: info.appdata_dir || '',
          };
          return this._cachedConnection;
        } catch (err) {
          console.warn('[StudioApi] Failed to invoke get_backend_connection_info:', err);
        }
      }

      // Fallback khi chạy dev trên trình duyệt thông thường
      this._cachedConnection = {
        baseUrl: 'http://127.0.0.1:8080',
        token: '',
        ready: true,
        appdataDir: '',
      };
      return this._cachedConnection;
    })();

    return this._initPromise;
  }

  private async _fetchWithToken(endpoint: string, options: RequestInit = {}): Promise<Response> {
    const conn = await this.getConnectionInfo();
    const headers = new Headers(options.headers || {});

    if (conn.token && !headers.has('x-studio-token')) {
      headers.set('x-studio-token', conn.token);
    }
    if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
      headers.set('Content-Type', 'application/json');
    }

    const url = endpoint.startsWith('http') ? endpoint : `${conn.baseUrl}${endpoint}`;
    return fetch(url, { ...options, headers });
  }

  // --- API Methods ---

  public async getAugmentsList(): Promise<AugmentItem[]> {
    try {
      const res = await this._fetchWithToken('/api/augments');
      if (!res.ok) return [];
      const data = await res.json();
      return data.augments || [];
    } catch (e) {
      console.error('[StudioApi] getAugmentsList error:', e);
      return [];
    }
  }

  public async saveCustomAugments(augments: (string | null)[]): Promise<{ success: boolean; error?: string }> {
    try {
      const res = await this._fetchWithToken('/api/augments', {
        method: 'POST',
        body: JSON.stringify({ custom_augments: augments }),
      });
      return await res.json();
    } catch (e: any) {
      return { success: false, error: e?.message || String(e) };
    }
  }

  public async renderOverlay(): Promise<{
    success: boolean;
    match_id?: string;
    mode?: string;
    png_path?: string;
    error?: string;
  }> {
    try {
      const res = await this._fetchWithToken('/api/render', {
        method: 'POST',
      });
      return await res.json();
    } catch (e: any) {
      return { success: false, error: e?.message || String(e) };
    }
  }

  public async getConfig(): Promise<any> {
    try {
      const res = await this._fetchWithToken('/api/config');
      return await res.json();
    } catch (e) {
      console.error('[StudioApi] getConfig error:', e);
      return {};
    }
  }

  public async saveConfig(data: any): Promise<{ success: boolean; error?: string; overlay_config?: any }> {
    try {
      const res = await this._fetchWithToken('/api/config', {
        method: 'POST',
        body: JSON.stringify(data),
      });
      return await res.json();
    } catch (e: any) {
      return { success: false, error: e?.message || String(e) };
    }
  }

  public async fetchLatestMatch(): Promise<{ success: boolean; error?: string; message?: string }> {
    try {
      const res = await this._fetchWithToken('/api/riot/fetch', {
        method: 'POST',
      });
      return await res.json();
    } catch (e: any) {
      return { success: false, error: e?.message || String(e) };
    }
  }

  public async getAppState(): Promise<any> {
    try {
      const res = await this._fetchWithToken('/api/state');
      return await res.json();
    } catch (e) {
      return null;
    }
  }

  /**
   * Kết xuất ảnh PNG 1080p chuẩn xác:
   * 1. Thử dùng html-to-image render phần tử overlay ở độ phân giải 1920x1080.
   * 2. Gửi Base64 xuống endpoint /api/export/base64.
   * 3. Nếu thất bại, fallback sang /api/export (Headless Chromium).
   */
  public async exportOverlayImage(elementId?: string): Promise<{ success: boolean; filePath?: string; error?: string }> {
    try {
      let targetEl: HTMLElement | null = null;
      if (elementId) {
        targetEl = document.getElementById(elementId);
      }
      if (!targetEl) {
        targetEl = document.getElementById('overlay-root') || document.querySelector('.overlay-container') || document.body;
      }

      if (targetEl) {
        const dataUrl = await toPng(targetEl, {
          width: 1920,
          height: 1080,
          pixelRatio: 1,
          cacheBust: true,
        });

        const res = await this._fetchWithToken('/api/export/base64', {
          method: 'POST',
          body: JSON.stringify({ image_base64: dataUrl }),
        });

        if (res.ok) {
          const result = await res.json();
          if (result.success) {
            return { success: true, filePath: result.file_path };
          }
        }
      }
    } catch (err) {
      console.warn('[StudioApi] html-to-image export failed, falling back to backend Chromium:', err);
    }

    // Fallback sang endpoint /api/export của backend
    try {
      const fallbackRes = await this._fetchWithToken('/api/export', { method: 'POST' });
      const data = await fallbackRes.json();
      return { success: data.success, filePath: data.file_path, error: data.error };
    } catch (fallbackErr: any) {
      return { success: false, error: fallbackErr?.message || String(fallbackErr) };
    }
  }

  public async openOutputFolder(): Promise<void> {
    if (this.isTauri()) {
      try {
        await invoke('open_app_folder', { folderType: 'output' });
        return;
      } catch (err) {
        console.warn('[StudioApi] open_app_folder error:', err);
      }
    }
    const conn = await this.getConnectionInfo();
    window.open(`${conn.baseUrl}/output`, '_blank');
  }

  public async openLogsFolder(): Promise<void> {
    if (this.isTauri()) {
      try {
        await invoke('open_app_folder', { folderType: 'logs' });
        return;
      } catch (err) {
        console.warn('[StudioApi] openLogsFolder error:', err);
      }
    }
  }

  public async openObsOverlayWindow(): Promise<void> {
    const conn = await this.getConnectionInfo();
    const url = `${conn.baseUrl}/overlay`;
    window.open(url, '_blank');
  }

  public async closePanel(): Promise<void> {
    if (this.isTauri()) {
      try {
        await invoke('stop_backend_sidecar');
      } catch (e) {
        console.warn('[StudioApi] stop_backend_sidecar error:', e);
      }
    }
  }

  public async toggleOverlayVisibility(visible: boolean): Promise<boolean> {
    return visible;
  }
}

export const StudioApi = new StudioApiService();
