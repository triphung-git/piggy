import React, { useState } from 'react';
import { ArrowUpCircle, CheckCircle2, AlertCircle, RefreshCw, X, Download } from 'lucide-react';
import { UpdateInfo, UpdateState, installConfirmedUpdate } from '../lib/updater';

interface UpdateModalProps {
  updateInfo: UpdateInfo | null;
  onClose: () => void;
}

export const UpdateModal: React.FC<UpdateModalProps> = ({ updateInfo, onClose }) => {
  const [state, setState] = useState<UpdateState>('waiting_for_consent');
  const [downloaded, setDownloaded] = useState(0);
  const [total, setTotal] = useState<number | undefined>(undefined);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!updateInfo) return null;

  const handleStartUpdate = async () => {
    setState('downloading');
    setErrorMessage(null);

    try {
      await installConfirmedUpdate(updateInfo, (downloadedBytes, totalBytes) => {
        setDownloaded(downloadedBytes);
        setTotal(totalBytes);
        if (totalBytes && downloadedBytes >= totalBytes) {
          setState('installing');
        }
      });
      setState('restarting');
    } catch (err: any) {
      console.error('[UpdateModal] Update failed:', err);
      setState('failed');
      setErrorMessage(err?.message || 'Có lỗi xảy ra trong quá trình cài đặt.');
    }
  };

  const progressPercent = total && total > 0 ? Math.min(100, Math.round((downloaded / total) * 100)) : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-md bg-zinc-900 border border-zinc-700/80 rounded-xl shadow-2xl p-5 text-zinc-100 font-sans">
        {/* Header */}
        <div className="flex items-start justify-between pb-3 border-b border-zinc-800">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400">
              <ArrowUpCircle className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-zinc-100 tracking-wide">Cập nhật phiên bản mới</h2>
              <p className="text-[11px] text-zinc-400">
                v{updateInfo.currentVersion} → <span className="text-amber-400 font-semibold">v{updateInfo.version}</span>
              </p>
            </div>
          </div>
          {state === 'waiting_for_consent' && (
            <button
              onClick={onClose}
              className="text-zinc-500 hover:text-zinc-300 p-1 rounded transition-colors"
              title="Đóng"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Body / Release Notes */}
        <div className="py-4 space-y-3">
          {state === 'waiting_for_consent' && (
            <>
              {updateInfo.date && (
                <div className="text-[10px] text-zinc-500 font-mono">
                  Phát hành: {updateInfo.date}
                </div>
              )}
              <div className="bg-zinc-950/70 border border-zinc-800/80 rounded-lg p-3 max-h-48 overflow-y-auto text-xs text-zinc-300 space-y-1.5 font-mono">
                <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1 font-semibold">
                  Thông tin bản cập nhật:
                </div>
                {updateInfo.body ? (
                  <p className="whitespace-pre-wrap leading-relaxed">{updateInfo.body}</p>
                ) : (
                  <p className="text-zinc-500 italic">Bản cập nhật tối ưu hóa hiệu năng và sửa lỗi.</p>
                )}
              </div>
              <p className="text-[11px] text-zinc-400">
                Toàn bộ dữ liệu cấu hình (<code className="text-zinc-300">.env</code>, giải đấu, ảnh xuất) sẽ được bảo toàn nguyên vẹn sau khi cập nhật.
              </p>
            </>
          )}

          {/* Downloading / Installing State */}
          {(state === 'downloading' || state === 'installing' || state === 'restarting') && (
            <div className="py-4 space-y-3">
              <div className="flex items-center justify-between text-xs text-zinc-300">
                <span className="flex items-center gap-2">
                  <RefreshCw className="w-3.5 h-3.5 text-amber-400 animate-spin" />
                  {state === 'downloading' && 'Đang tải gói cập nhật...'}
                  {state === 'installing' && 'Đang xác minh chữ ký & cài đặt...'}
                  {state === 'restarting' && 'Đang khởi động lại ứng dụng...'}
                </span>
                {progressPercent !== null && (
                  <span className="font-mono text-amber-400 font-bold">{progressPercent}%</span>
                )}
              </div>

              {/* Progress Bar */}
              <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-amber-500 to-yellow-400 transition-all duration-200"
                  style={{ width: `${progressPercent ?? (state === 'downloading' ? 30 : 90)}%` }}
                />
              </div>

              {total && total > 0 && (
                <div className="text-right text-[10px] font-mono text-zinc-500">
                  {(downloaded / (1024 * 1024)).toFixed(1)} MB / {(total / (1024 * 1024)).toFixed(1)} MB
                </div>
              )}
            </div>
          )}

          {/* Failed State */}
          {state === 'failed' && (
            <div className="p-3 bg-red-950/40 border border-red-800/60 rounded-lg flex items-start gap-2.5 text-xs text-red-300">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-red-200">Cập nhật thất bại</p>
                <p className="text-[11px] text-red-400 mt-0.5">{errorMessage}</p>
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-zinc-800">
          {state === 'waiting_for_consent' && (
            <>
              <button
                type="button"
                onClick={onClose}
                className="px-3.5 py-1.5 rounded-lg text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 border border-transparent transition-all"
              >
                Để sau
              </button>
              <button
                type="button"
                onClick={handleStartUpdate}
                className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-amber-500 hover:bg-amber-400 text-zinc-950 flex items-center gap-1.5 transition-all shadow-md shadow-amber-500/10"
              >
                <Download className="w-3.5 h-3.5" />
                Cập nhật ngay
              </button>
            </>
          )}

          {state === 'failed' && (
            <>
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-1.5 rounded-lg text-xs text-zinc-400 hover:bg-zinc-800"
              >
                Đóng
              </button>
              <button
                type="button"
                onClick={handleStartUpdate}
                className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-amber-500 hover:bg-amber-400 text-zinc-950 flex items-center gap-1.5"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Thử lại
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
