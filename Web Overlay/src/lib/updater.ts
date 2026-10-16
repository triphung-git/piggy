/**
 * Web Overlay/src/lib/updater.ts
 * ------------------------------
 * State machine và logic kiểm tra & cài đặt cập nhật cho Desktop app.
 * Tuân thủ quy tắc:
 *   1. Không tự ý cập nhật mà không có sự xác nhận của người dùng.
 *   2. Bắt buộc dừng Python sidecar trước khi downloadAndInstall() để tránh khóa file .exe.
 */

import { check, type Update } from '@tauri-apps/plugin-updater';
import { relaunch } from '@tauri-apps/plugin-process';
import { invoke } from '@tauri-apps/api/core';

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

export async function checkForAppUpdate(): Promise<UpdateInfo | null> {
  if (typeof window === 'undefined' || !('__TAURI_INTERNALS__' in window)) {
    return null;
  }

  try {
    const update = await check();
    if (!update) {
      return null;
    }

    return {
      version: update.version,
      currentVersion: update.currentVersion,
      date: update.date,
      body: update.body,
      rawUpdate: update,
    };
  } catch (err) {
    console.warn('[Updater] check() error:', err);
    return null;
  }
}

export async function installConfirmedUpdate(
  updateInfo: UpdateInfo,
  onProgress?: (downloadedBytes: number, totalBytes?: number) => void
): Promise<void> {
  // 1. Dừng tiến trình Python FastAPI sidecar trước để giải phóng file lock & cổng 8080
  try {
    await invoke('stop_backend_sidecar');
  } catch (e) {
    console.warn('[Updater] stop_backend_sidecar warning:', e);
  }

  // 2. Tải và cài đặt gói cập nhật đã xác minh chữ ký
  let downloaded = 0;
  let contentLength: number | undefined;

  await updateInfo.rawUpdate.downloadAndInstall((event) => {
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

  // 3. Khởi động lại ứng dụng vào phiên bản mới
  await relaunch();
}
