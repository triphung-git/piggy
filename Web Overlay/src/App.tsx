import { useEffect, useState } from 'react';
import SourceTransformPanel from './components/SourceTransformPanel';
import { UpdateModal } from './components/UpdateModal';
import { checkForAppUpdateDetailed, type UpdateInfo } from './lib/updater';
import { Sparkles, ArrowUpCircle } from 'lucide-react';

export default function App() {
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [showUpdateModal, setShowUpdateModal] = useState(false);

  useEffect(() => {
    // Tự động kiểm tra bản cập nhật mới khi khởi chạy Desktop app
    const checkUpdates = async () => {
      try {
        const result = await checkForAppUpdateDetailed();
        if (result.status === 'update_available' && result.update) {
          setUpdateInfo(result.update);
          setShowUpdateModal(true);
        } else if (result.status === 'error') {
          console.warn('[App] Update check failed (network or signature error):', result.error);
        }
      } catch (err) {
        console.warn('[App] Update check skipped:', err);
      }
    };

    checkUpdates();
  }, []);


  return (
    <div className="relative size-full min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center p-4 overflow-hidden select-none">
      {/* Subtle Studio Grid Background */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.15]"
        style={{
          backgroundImage: `
            radial-gradient(circle at 50% 50%, rgba(59, 130, 246, 0.15) 0%, transparent 60%),
            linear-gradient(to right, #27272a 1px, transparent 1px),
            linear-gradient(to bottom, #27272a 1px, transparent 1px)
          `,
          backgroundSize: '100% 100%, 32px 32px, 32px 32px',
        }}
      />

      {/* Update Pill if modal was closed */}
      {updateInfo && !showUpdateModal && (
        <button
          onClick={() => setShowUpdateModal(true)}
          className="absolute top-4 right-4 z-20 flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-semibold hover:bg-amber-500/20 transition-all shadow-lg shadow-amber-500/5 cursor-pointer"
        >
          <ArrowUpCircle className="w-3.5 h-3.5" />
          <span>Có bản cập nhật v{updateInfo.version}</span>
        </button>
      )}

      {/* Control Panel */}
      <main className="relative z-10 my-auto">
        <SourceTransformPanel />
      </main>

      {/* Modal cập nhật */}
      {showUpdateModal && updateInfo && (
        <UpdateModal
          updateInfo={updateInfo}
          onClose={() => setShowUpdateModal(false)}
        />
      )}

      {/* Footer */}
      <footer className="absolute bottom-3 right-4 z-0 text-[10px] font-mono text-zinc-600 flex items-center gap-3 pointer-events-none">
        <span className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Desktop Studio
        </span>
        <span>TFT Post-Match Studio — Open Source (MIT)</span>
      </footer>
    </div>
  );
}
