/**
 * Web Overlay/src/lib/updater.ts
 * ------------------------------
 * State machine và logic kiểm tra & cài đặt cập nhật cho Desktop app.
 * Tuân thủ quy tắc:
 *   1. Không tự ý cập nhật mà không có sự xác nhận của người dùng.
 *   2. Tải/xác minh trước, dừng Python sidecar ngay trước install() để giải phóng file .exe.
 */

import { check, type Update } from '@tauri-apps/plugin-updater';
import { relaunch } from '@tauri-apps/plugin-process';
import { invoke } from '@tauri-apps/api/core';
import { StudioApi } from './api';

export type UpdateState =
  | 'idle'
  | 'checking'
  | 'up_to_date'
  | 'update_available'
  | 'waiting_for_consent'
  | 'downloading'
  | 'installing'
  | 'restarting'
  | 'failed';

export interface UpdateInfo {
  version: string;
  currentVersion: string;
  date?: string;
  body?: string;
  rawUpdate: Update;
}

export interface CheckUpdateResult {
  status: 'update_available' | 'up_to_date' | 'error' | 'unsupported';
  update?: UpdateInfo;
  error?: string;
}

export async function checkForAppUpdateDetailed(): Promise<CheckUpdateResult> {
  if (typeof window === 'undefined' || !('__TAURI_INTERNALS__' in window)) {
    return { status: 'unsupported' };
  }

  try {
    const update = await check();
    if (!update) {
      return { status: 'up_to_date' };
    }

    return {
      status: 'update_available',
      update: {
        version: update.version,
        currentVersion: update.currentVersion,
        date: update.date,
        body: update.body,
        rawUpdate: update,
      },
    };
  } catch (err: any) {
    const errorStr = err?.message || String(err);
    console.error('[Updater] check() error:', errorStr);
    return { status: 'error', error: errorStr };
  }
}

export async function checkForAppUpdate(): Promise<UpdateInfo | null> {
  const result = await checkForAppUpdateDetailed();
  if (result.status === 'update_available' && result.update) {
    return result.update;
  }
  return null;
}


export async function installConfirmedUpdate(
  updateInfo: UpdateInfo,
  onProgress?: (downloadedBytes: number, totalBytes?: number) => void
): Promise<void> {
  // Download and verify while the existing backend remains available.
  let downloaded = 0;
  let contentLength: number | undefined;

  await updateInfo.rawUpdate.download((event) => {
    switch (event.event) {
      case 'Started':
        contentLength = event.data.contentLength;
        break;
      case 'Progress':
        downloaded += event.data.chunkLength;
        onProgress?.(downloaded, contentLength);
        break;
      case 'Finished':
        break;
    }
  });

  let stopAttempted = false;
  try {
    stopAttempted = true;
    await invoke('stop_backend_sidecar');
    StudioApi.invalidateConnection();
    await updateInfo.rawUpdate.install();
    await relaunch();
  } catch (error) {
    if (stopAttempted) {
      try {
        const connection = await invoke<{ready: boolean}>('get_backend_connection_info');
        if (!connection.ready) await invoke('start_backend_sidecar');
        StudioApi.invalidateConnection();
        await StudioApi.getConnectionInfo();
      } catch (recoveryError) {
        throw new Error(`Cập nhật thất bại: ${String(error)}. Không thể phục hồi backend: ${String(recoveryError)}. Hãy khởi động lại ứng dụng.`);
      }
    }
    throw error;
  }
}
