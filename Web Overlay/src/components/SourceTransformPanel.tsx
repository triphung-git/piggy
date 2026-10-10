import React, { useState, useRef, useEffect, useMemo } from 'react';
import {
  X,
  Eye,
  EyeOff,
  Play,
  CheckCircle2,
  RefreshCw,
  Sparkles,
  Monitor,
  Search,
  ChevronDown,
  Save,
} from 'lucide-react';

// ---- Augment types ----
interface AugmentItem {
  id: string;
  name: string;   // English name from DDragon
  image: string;  // Filename, e.g. "BronzeForLife_II.png"
  tier?: number;  // 1, 2, or 3
  is_destiny?: boolean;
}

interface AugmentSlotState {
  main: string | null;   // image filename or null = Auto
  bonus: string | null;  // image filename or null = Auto
}

export function getDestinyTier(aug: AugmentItem | null | undefined): 1 | 2 | 3 | null {
  if (!aug) return null;
  const s = `${aug.name} ${aug.image} ${aug.id}`.toLowerCase();
  if (s.includes('silverdestiny') || s.includes('silver destiny') || s.includes('vận mệnh bạc')) return 1;
  if (s.includes('goldendestiny') || s.includes('gold destiny') || s.includes('vận mệnh vàng')) return 2;
  if (s.includes('prismaticdestiny') || s.includes('prismatic destiny') || s.includes('vận mệnh kim cương')) return 3;
  return null;
}

export function getAugmentTier(aug: AugmentItem | null | undefined): number {
  if (!aug) return 2;
  if (aug.tier) return aug.tier;
  const s = `${aug.name} ${aug.image} ${aug.id}`.toLowerCase();
  if (s.includes('_iii') || s.includes('-iii') || s.includes('3.png') || aug.id.endsWith('3') || s.includes('prismatic')) return 3;
  if (s.includes('_ii') || s.includes('-ii') || s.includes('2.png') || aug.id.endsWith('2') || s.includes('gold')) return 2;
  if (s.includes('_i') || s.includes('-i') || s.includes('1.png') || aug.id.endsWith('1') || s.includes('silver')) return 1;
  return 2;
}

function parseCustomAugmentsToSlots(
  ca: (string | null)[] | undefined,
  list: AugmentItem[]
): AugmentSlotState[] {
  if (!ca || !Array.isArray(ca) || ca.length === 0) {
    return [
      { main: null, bonus: null },
      { main: null, bonus: null },
      { main: null, bonus: null },
    ];
  }

  const result: AugmentSlotState[] = [];
  let idx = 0;
  for (let slot = 0; slot < 3; slot++) {
    if (idx >= ca.length) {
      result.push({ main: null, bonus: null });
      continue;
    }
    const val = ca[idx];
    idx++;
    const mainAug = val ? list.find(a => a.image === val) : null;
    const isDestiny = mainAug
      ? getDestinyTier(mainAug) !== null
      : (val ? val.toLowerCase().includes('destiny') : false);

    let bonusVal: string | null = null;
    if (isDestiny && idx < ca.length) {
      bonusVal = ca[idx] || null;
      idx++;
    }
    result.push({ main: val || null, bonus: bonusVal });
  }
  return result;
}

declare global {
  interface Window {
    pywebview?: {
      api?: {
        render_overlay?: () => Promise<{
          success: boolean;
          match_id?: string;
          mode?: string;
          png_path?: string;
          error?: string;
        }>;
        toggle_overlay_visibility?: (visible: boolean) => Promise<boolean>;
        close_panel?: () => Promise<void>;
        get_augments_list?: () => Promise<AugmentItem[]>;
        save_custom_augments?: (augments: (string | null)[]) => Promise<any>;
      };
    };
    // Callbacks từ Python backend
    onAppStateUpdate?: (data: any) => void;
    onProgressUpdate?: (data: { pct: number; status: string }) => void;
  }
}

export default function SourceTransformPanel() {
  const [isVisible, setIsVisible] = useState(false);
  const [isClosed, setIsClosed] = useState(false);

  // Render process state
  const [isRendering, setIsRendering] = useState(false);
  const [renderProgress, setRenderProgress] = useState(0);
  const [showSuccessToast, setShowSuccessToast] = useState(false);
  const [toastMessage, setToastMessage] = useState('Overlay rendered & synced');
  const [toastDuration, setToastDuration] = useState('1.2s');

  // OBS connection status
  const [obsConnected, setObsConnected] = useState(false);
  const obsUrl = 'http://localhost:8080/overlay';

  // Augments Selector State
  const [augmentsList, setAugmentsList] = useState<AugmentItem[]>([]);
  // 3 slots chính, mỗi slot có main và bonus (nếu là lõi Destiny)
  const [slotsState, setSlotsState] = useState<AugmentSlotState[]>([
    { main: null, bonus: null },
    { main: null, bonus: null },
    { main: null, bonus: null },
  ]);
  const [isSavingAugments, setIsSavingAugments] = useState(false);
  const [augmentsLoaded, setAugmentsLoaded] = useState(false);

  // Nạp danh sách augments khi mở app
  useEffect(() => {
    const initAugments = async () => {
      try {
        let list: AugmentItem[] = [];
        if (window.pywebview?.api?.get_augments_list) {
          list = await window.pywebview.api.get_augments_list();
        } else {
          const res = await fetch('/api/augments').then(r => r.json()).catch(() => null);
          list = res?.augments || [];
        }
        setAugmentsList(list);
        setAugmentsLoaded(true);

        // Load custom_augments hiện tại từ config
        const cfgRes = await fetch('/api/config').then(r => r.json()).catch(() => null);
        if (cfgRes?.custom_augments && Array.isArray(cfgRes.custom_augments)) {
          setSlotsState(parseCustomAugmentsToSlots(cfgRes.custom_augments, list));
        }
      } catch (e) {
        console.warn('Could not load augments:', e);
        setAugmentsLoaded(true);
      }
    };

    if (window.pywebview) {
      initAugments();
    } else {
      window.addEventListener('pywebviewready', initAugments);
      initAugments();
    }

    // Callback nhận thông báo từ Python Backend
    window.onAppStateUpdate = (data: any) => {
      if (data?.overlay_config?.custom_augments !== undefined) {
        const ca = data.overlay_config.custom_augments;
        setSlotsState(parseCustomAugmentsToSlots(ca, augmentsList));
      }
      if (data?.fetch_status) {
        if (data.fetch_status.success) {
          setToastMessage(data.fetch_status.message || 'Đã nạp trận mới nhất');
          setShowSuccessToast(true);
          setTimeout(() => setShowSuccessToast(false), 4000);
        }
      }
      if (data?.active_match) {
        setToastMessage(`Trận mới: ${data.active_match.match_id || 'Đã đồng bộ'}`);
        setShowSuccessToast(true);
        setTimeout(() => setShowSuccessToast(false), 3000);
      }
    };

    // Kết nối WS cục bộ để nhận thông báo OVERLAY_RENDERED
    let socket: WebSocket | null = null;
    let reconnectTimer: any = null;

    const connectWs = () => {
      try {
        socket = new WebSocket('ws://127.0.0.1:8080/ws');

        socket.onopen = () => {
          setObsConnected(true);
        };

        socket.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'OVERLAY_RENDERED') {
              const src = msg.source ? ` (${msg.source})` : '';
              setToastMessage(`Overlay cập nhật: ${msg.match_id || 'OK'}${src}`);
              setToastDuration('instant');
              setShowSuccessToast(true);
              setTimeout(() => setShowSuccessToast(false), 3500);
            }
          } catch (e) {}
        };

        socket.onclose = () => {
          setObsConnected(false);
          reconnectTimer = setTimeout(connectWs, 1500);
        };

        socket.onerror = () => {
          if (socket) socket.close();
        };
      } catch (e) {
        setObsConnected(false);
        reconnectTimer = setTimeout(connectWs, 2000);
      }
    };

    if (window.location.protocol.startsWith('http')) {
      connectWs();
    }

    return () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (socket) socket.close();
    };
  }, [augmentsList]);

  // Lưu Augments và re-render overlay
  const handleSaveAugments = async () => {
    if (isSavingAugments) return;
    setIsSavingAugments(true);
    try {
      // Flatten slotsState into array of up to 6 elements
      const flatList: (string | null)[] = [];
      for (const slot of slotsState) {
        flatList.push(slot.main);
        const mainAug = slot.main ? augmentsList.find(a => a.image === slot.main) : null;
        if (getDestinyTier(mainAug) !== null) {
          flatList.push(slot.bonus);
        }
      }

      if (window.pywebview?.api?.save_custom_augments) {
        const res = await window.pywebview.api.save_custom_augments(flatList);
        if (res?.success) {
          setToastMessage('✓ Augments saved & overlay re-rendered!');
          setShowSuccessToast(true);
          setTimeout(() => setShowSuccessToast(false), 4000);
        } else {
          throw new Error(res?.error || 'Unknown error');
        }
      } else {
        const res = await fetch('/api/augments', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ custom_augments: flatList }),
        }).then(r => r.json());
        if (res?.success) {
          setToastMessage('✓ Augments saved & overlay re-rendered!');
          setShowSuccessToast(true);
          setTimeout(() => setShowSuccessToast(false), 4000);
        } else {
          throw new Error(res?.error || 'Failed to save augments');
        }
      }
    } catch (err: any) {
      alert('Error saving augments: ' + (err?.message || err));
    } finally {
      setIsSavingAugments(false);
    }
  };

  // Thực thi Render Overlay
  const handleTriggerRender = async () => {
    if (isRendering) return;

    setIsRendering(true);
    setRenderProgress(20);
    setShowSuccessToast(false);

    const startTime = performance.now();

    try {
      if (window.pywebview?.api?.render_overlay) {
        setRenderProgress(45);
        const res = await window.pywebview.api.render_overlay();
        const elapsedSec = ((performance.now() - startTime) / 1000).toFixed(2);

        setRenderProgress(100);
        setTimeout(() => {
          setIsRendering(false);
          if (res?.success) {
            setToastMessage(`✓ Overlay rendered: ${res.match_id} (${res.mode})`);
            setToastDuration(`${elapsedSec}s`);
            setShowSuccessToast(true);
            setIsVisible(true);
            setTimeout(() => setShowSuccessToast(false), 4500);
          } else {
            alert('Render Error: ' + (res?.error || 'Unknown error'));
          }
        }, 300);
      } else {
        setRenderProgress(40);
        const res = await fetch('/api/render', {
          method: 'POST',
        }).then(r => r.json());

        const elapsedSec = ((performance.now() - startTime) / 1000).toFixed(2);
        setRenderProgress(100);
        setTimeout(() => {
          setIsRendering(false);
          if (res?.success) {
            setToastMessage(`✓ Overlay rendered: ${res.match_id || 'OK'}`);
            setToastDuration(`${elapsedSec}s`);
            setShowSuccessToast(true);
            setIsVisible(true);
            setTimeout(() => setShowSuccessToast(false), 4500);
          } else {
            alert('Render Error: ' + (res?.error || 'Unknown error'));
          }
        }, 300);
      }
    } catch (err: any) {
      setIsRendering(false);
      alert('Exception: ' + (err?.message || err));
    }
  };

  const handleToggleVisibility = async () => {
    const nextVis = !isVisible;
    setIsVisible(nextVis);
    if (window.pywebview?.api?.toggle_overlay_visibility) {
      try {
        await window.pywebview.api.toggle_overlay_visibility(nextVis);
      } catch (e) {
        console.warn('Toggle overlay error:', e);
      }
    }
  };

  const handleClose = async () => {
    setIsClosed(true);
    if (window.pywebview?.api?.close_panel) {
      try {
        await window.pywebview.api.close_panel();
      } catch (e) {
        console.warn('Close error:', e);
      }
    }
  };

  if (isClosed) {
    return (
      <div className="flex flex-col items-center justify-center p-8 bg-zinc-950 rounded-xl border border-zinc-800 shadow-2xl">
        <div className="text-zinc-400 text-sm mb-3 font-medium flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-amber-400" />
          <span>TFT Post-Match Studio — Closed</span>
        </div>
        <button
          onClick={() => setIsClosed(false)}
          className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold rounded-md border border-zinc-700 transition-all shadow-md flex items-center gap-2"
        >
          <RefreshCw className="w-3.5 h-3.5 text-blue-400" />
          Reopen Panel
        </button>
      </div>
    );
  }

  return (
    <div className={`w-[460px] max-w-full bg-zinc-900/95 text-zinc-200 rounded-xl border border-zinc-800 shadow-2xl backdrop-blur-md select-none font-sans transition-all flex flex-col
      ${!isVisible ? 'opacity-90' : 'opacity-100'}`}
      style={{ maxHeight: '100dvh' }}
    >
      {/* 1. Header — cố định, không co rút */}
      <div className="px-3.5 py-2.5 bg-zinc-950/80 border-b border-zinc-800/80 flex flex-col gap-1 shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${isVisible ? 'bg-blue-500 animate-pulse' : 'bg-emerald-500'}`} />
            <h1 className="text-xs font-bold text-zinc-100 uppercase tracking-wider leading-none">
              TFT POST-MATCH STUDIO
            </h1>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={handleClose}
              title="Close Panel"
              className="p-1 text-zinc-400 hover:text-red-400 hover:bg-zinc-800/80 rounded transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* OBS Status Bar */}
        <div className="flex items-center justify-between pt-1 mt-0.5 border-t border-zinc-800/60">
          <div className="flex items-center gap-1.5 text-[10px] text-zinc-400 font-mono">
            <Monitor className="w-3 h-3" />
            <span className={obsConnected ? 'text-emerald-400' : 'text-zinc-500'}>
              {obsConnected ? '● Server Online' : '○ Connecting...'}
            </span>
            <span className="text-zinc-600">|</span>
            <span
              className="text-blue-400 hover:text-blue-300 cursor-pointer transition-colors"
              title="OBS Browser Source URL — Click to copy"
              onClick={() => {
                navigator.clipboard?.writeText(obsUrl).catch(() => {});
              }}
            >
              Copy URL
            </span>
          </div>
          <span className="text-[9px] font-mono text-zinc-500 tracking-tight italic">
            Live Real-time
          </span>
        </div>
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-3 space-y-3"
        style={{
          scrollbarWidth: 'thin',
          scrollbarColor: '#3f3f46 transparent',
        }}
      >
        {/* Augments Selection Card */}
        <div className="bg-zinc-950/70 border border-zinc-800/80 rounded-lg p-3 flex flex-col gap-2.5 shadow-inner">
          <div className="flex items-center justify-between border-b border-zinc-800/60 pb-1.5">
            <span className="text-[11px] font-semibold text-zinc-200 tracking-wide flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              Augments Selection
            </span>
            <button
              onClick={handleSaveAugments}
              disabled={isSavingAugments || !augmentsLoaded}
              className={`px-2.5 py-1 rounded text-[10px] font-semibold flex items-center gap-1 border transition-all ${
                isSavingAugments
                  ? 'bg-amber-950/60 border-amber-600/60 text-amber-300 cursor-wait'
                  : 'bg-amber-600/90 hover:bg-amber-500 border-amber-500 text-white shadow-sm'
              }`}
            >
              <Save className="w-3 h-3" />
              <span>{isSavingAugments ? 'Saving...' : 'Save & Sync'}</span>
            </button>
          </div>

          {/* Augment Slot Pickers */}
          {!augmentsLoaded ? (
            <div className="flex items-center justify-center py-4 text-zinc-500 text-[11px] font-mono">
              <RefreshCw className="w-3.5 h-3.5 animate-spin mr-1.5" /> Loading augments...
            </div>
          ) : (
            <div className="flex flex-col gap-2.5">
              {[0, 1, 2].map(slotIdx => {
                const currentMain = slotsState[slotIdx]?.main;
                const mainAug = currentMain ? augmentsList.find(a => a.image === currentMain) : null;
                const destinyTier = getDestinyTier(mainAug);

                return (
                  <div key={slotIdx} className="flex flex-col gap-2 p-2.5 rounded-lg bg-zinc-900/50 border border-zinc-800/70">
                    <AugmentSlotPicker
                      slotIndex={slotIdx}
                      augmentsList={augmentsList}
                      value={currentMain}
                      onChange={img => {
                        setSlotsState(prev => {
                          const next = [...prev];
                          const newMainAug = img ? augmentsList.find(a => a.image === img) : null;
                          const isDest = getDestinyTier(newMainAug) !== null;
                          next[slotIdx] = {
                            main: img,
                            bonus: isDest ? next[slotIdx]?.bonus || null : null,
                          };
                          return next;
                        });
                      }}
                    />

                    {/* Nếu slot này là Destiny Augment -> Hiện thêm ô Bonus Augment */}
                    {destinyTier !== null && (
                      <div className="ml-2 pl-2.5 pt-1.5 pb-1 border-l-2 border-amber-500/70 flex flex-col gap-1.5 bg-amber-950/15 rounded-r">
                        <div className="flex items-center justify-between text-[10px] text-amber-300 font-medium">
                          <span className="flex items-center gap-1 font-semibold">
                            <Sparkles className="w-3 h-3 text-amber-400" />
                            Bonus Augment ({destinyTier === 1 ? 'Bạc / Silver' : destinyTier === 2 ? 'Vàng / Gold' : 'Kim Cương / Prismatic'})
                          </span>
                          <span className="text-[9px] text-amber-400/80 font-mono">Cùng bậc</span>
                        </div>
                        <AugmentSlotPicker
                          slotIndex={slotIdx}
                          labelOverride={`Bonus Slot ${['I', 'II', 'III'][slotIdx]} (Cùng bậc)`}
                          filterTier={destinyTier}
                          augmentsList={augmentsList}
                          value={slotsState[slotIdx]?.bonus || null}
                          onChange={img => {
                            setSlotsState(prev => {
                              const next = [...prev];
                              next[slotIdx] = {
                                ...next[slotIdx],
                                bonus: img,
                              };
                              return next;
                            });
                          }}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          <div className="text-[9px] font-mono text-zinc-500 pt-0.5 border-t border-zinc-800/40">
            Slot “Auto” uses live match augments. Destiny augments allow picking an extra augment of the same tier.
          </div>
        </div>

        {/* Hidden Indicator */}
        {!isVisible && (
          <div className="bg-amber-950/40 border border-amber-800/50 text-amber-300 text-[11px] px-3 py-1.5 rounded-md flex items-center justify-between font-mono">
            <div className="flex items-center gap-1.5">
              <EyeOff className="w-3.5 h-3.5 text-amber-400" />
              <span>Overlay Hidden from Stream Output</span>
            </div>
          </div>
        )}

        {/* Toast Notification */}
        {showSuccessToast && (
          <div className="bg-emerald-950/80 border border-emerald-700/60 text-emerald-200 text-[11px] px-3 py-1.5 rounded-md flex items-center justify-between font-mono animate-fade-in shadow-lg">
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              <span>{toastMessage}</span>
            </div>
            <span className="text-[9px] text-emerald-400/80">{toastDuration}</span>
          </div>
        )}

        {/* Main Action Controls */}
        <div className="pt-1">
          <div className="grid grid-cols-3 gap-2">
            {/* Render Button */}
            <button
              onClick={handleTriggerRender}
              disabled={isRendering}
              className={`relative overflow-hidden py-2 px-3 rounded-md text-xs font-semibold tracking-wide transition-all shadow-md flex items-center justify-center gap-1.5 border ${
                isRendering
                  ? 'bg-blue-950 border-blue-700 text-blue-200 cursor-wait'
                  : 'bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white border-blue-500 shadow-blue-950/50'
              }`}
            >
              {isRendering ? (
                <>
                  <div
                    className="absolute inset-0 bg-blue-500/30 transition-all duration-150"
                    style={{ width: `${renderProgress}%` }}
                  />
                  <RefreshCw className="w-3.5 h-3.5 animate-spin z-10 text-blue-200" />
                  <span className="z-10 font-mono text-[11px]">{renderProgress}%</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Render</span>
                </>
              )}
            </button>

            {/* Xem / Ẩn Cửa Sổ Preview */}
            <button
              onClick={handleToggleVisibility}
              title={isVisible ? "Ẩn cửa sổ xem trước trên màn hình" : "Mở cửa sổ xem trước Overlay trên màn hình"}
              className={`py-2 px-3 rounded-md text-xs font-medium tracking-wide transition-all flex items-center justify-center gap-1.5 border ${
                isVisible
                  ? 'bg-blue-950/60 hover:bg-blue-900/60 text-blue-300 border-blue-700/80'
                  : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border-zinc-700'
              }`}
            >
              {isVisible ? (
                <>
                  <EyeOff className="w-3.5 h-3.5 text-blue-400" />
                  <span>Ẩn Preview</span>
                </>
              ) : (
                <>
                  <Eye className="w-3.5 h-3.5 text-zinc-400" />
                  <span>Xem Preview</span>
                </>
              )}
            </button>

            {/* Close Button */}
            <button
              onClick={handleClose}
              className="py-2 px-3 bg-zinc-800 hover:bg-zinc-700 active:bg-zinc-850 text-zinc-300 hover:text-white rounded-md text-xs font-medium border border-zinc-700 transition-all flex items-center justify-center gap-1.5"
            >
              <X className="w-3.5 h-3.5 text-zinc-400" />
              <span>Close</span>
            </button>
          </div>

          {/* OBS Setup Hint */}
          <div className="mt-2 text-[10px] font-mono text-zinc-600 text-center">
            OBS → Add Browser Source →{' '}
            <span
              className="text-blue-500 cursor-pointer hover:text-blue-400"
              onClick={() => navigator.clipboard?.writeText(obsUrl).catch(() => {})}
              title="Click to copy OBS URL"
            >
              {obsUrl}
            </span>
            {' '}(1920×1080)
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// AugmentSlotPicker — Searchable combobox cho 1 slot lõi
// ============================================================
interface AugmentSlotPickerProps {
  slotIndex: number;
  labelOverride?: string;
  filterTier?: number;
  augmentsList: AugmentItem[];
  value: string | null;          // image filename or null = Auto
  onChange: (img: string | null) => void;
}

function AugmentSlotPicker({
  slotIndex,
  labelOverride,
  filterTier,
  augmentsList,
  value,
  onChange,
}: AugmentSlotPickerProps) {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({});
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Tìm thông tin augment hiện tại
  const currentAug = value ? augmentsList.find(a => a.image === value) : null;

  // Filter logic: nếu có filterTier thì lọc theo tier (trừ khi có search query cụ thể)
  const filtered = useMemo((): AugmentItem[] => {
    let base = augmentsList;
    if (filterTier) {
      base = augmentsList.filter(a => getAugmentTier(a) === filterTier);
    }
    const q = query.trim().toLowerCase();
    if (!q) return base;
    const starts = base.filter(a => a.name.toLowerCase().startsWith(q));
    const includes = base.filter(a =>
      !a.name.toLowerCase().startsWith(q) && a.name.toLowerCase().includes(q)
    );
    return [...starts, ...includes];
  }, [augmentsList, query, filterTier]);

  // Đóng khi click ngoài
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  const handleOpen = () => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    const dropdownHeight = 260;
    const openUpward = spaceBelow < dropdownHeight + 8 && rect.top > dropdownHeight;
    setDropdownStyle({
      position: 'fixed',
      left: rect.left,
      width: rect.width,
      zIndex: 9999,
      ...(openUpward
        ? { bottom: window.innerHeight - rect.top + 4 }
        : { top: rect.bottom + 4 }),
    });
    setIsOpen(true);
    setQuery('');
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  const handleSelect = (aug: AugmentItem | null) => {
    onChange(aug?.image ?? null);
    setIsOpen(false);
    setQuery('');
  };

  const slotLabel = labelOverride || (['Augment I', 'Augment II', 'Augment III'][slotIndex] ?? `Slot ${slotIndex + 1}`);
  const IMG_BASE = '/TFT_DDragon/img/augment/';

  return (
    <div ref={containerRef} className="relative flex flex-col gap-1">
      {/* Label */}
      <span className="text-[9px] font-mono text-zinc-500 uppercase tracking-widest">{slotLabel}</span>

      {/* Trigger button */}
      <button
        ref={triggerRef}
        type="button"
        onClick={handleOpen}
        className={`w-full flex items-center gap-2 px-2 py-1.5 rounded border text-left transition-all ${
          isOpen
            ? 'border-amber-500/70 bg-zinc-900 ring-1 ring-amber-500/30'
            : 'border-zinc-700/80 bg-zinc-900/70 hover:border-zinc-600'
        }`}
      >
        {/* Augment icon preview */}
        {currentAug ? (
          <img
            src={`${IMG_BASE}${currentAug.image}`}
            alt={currentAug.name}
            className="w-5 h-5 rounded object-cover shrink-0"
            onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
          />
        ) : (
          <div className="w-5 h-5 rounded bg-zinc-800 border border-zinc-700 flex items-center justify-center shrink-0">
            <Sparkles className="w-2.5 h-2.5 text-zinc-600" />
          </div>
        )}

        {/* Name display */}
        <span className={`text-[11px] flex-1 truncate ${ currentAug ? 'text-zinc-200 font-medium' : 'text-zinc-500 italic' }`}>
          {currentAug ? currentAug.name : 'Auto (from match)'}
        </span>

        <ChevronDown className={`w-3 h-3 text-zinc-500 shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown panel */}
      {isOpen && (
        <div
          className="bg-zinc-950 border border-amber-600/40 rounded-lg shadow-2xl shadow-black/60 flex flex-col overflow-hidden"
          style={{ ...dropdownStyle, maxHeight: '260px' }}
        >
          {/* Search input */}
          <div className="flex items-center gap-1.5 px-2.5 py-2 border-b border-zinc-800">
            <Search className="w-3 h-3 text-zinc-400 shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search augments..."
              className="flex-1 bg-transparent text-[11px] text-zinc-200 placeholder-zinc-600 outline-none"
            />
            {query && (
              <button onClick={() => setQuery('')} className="text-zinc-600 hover:text-zinc-400">
                <X className="w-3 h-3" />
              </button>
            )}
          </div>

          {/* Scrollable list */}
          <div className="overflow-y-auto flex-1" style={{ maxHeight: '196px' }}>
            {/* Auto option */}
            <button
              type="button"
              onClick={() => handleSelect(null)}
              className={`w-full flex items-center gap-2 px-2.5 py-1.5 hover:bg-zinc-800/70 transition-colors text-left border-b border-zinc-800/50 ${
                value === null ? 'bg-amber-950/40' : ''
              }`}
            >
              <div className="w-5 h-5 rounded bg-zinc-800 border border-zinc-700 flex items-center justify-center shrink-0">
                <Sparkles className="w-2.5 h-2.5 text-amber-500" />
              </div>
              <div className="flex flex-col min-w-0">
                <span className="text-[11px] text-amber-300 font-semibold">Auto</span>
                <span className="text-[9px] text-zinc-600 font-mono">Use live match data</span>
              </div>
              {value === null && <CheckCircle2 className="w-3 h-3 text-amber-400 ml-auto shrink-0" />}
            </button>

            {/* Augment items */}
            {filtered.length === 0 ? (
              <div className="py-6 text-center text-[11px] text-zinc-600 font-mono">No augments found</div>
            ) : (
              filtered.map(aug => (
                <button
                  key={aug.id}
                  type="button"
                  onClick={() => handleSelect(aug)}
                  className={`w-full flex items-center gap-2 px-2.5 py-1.5 hover:bg-zinc-800/70 transition-colors text-left ${
                    value === aug.image ? 'bg-amber-950/30' : ''
                  }`}
                >
                  <img
                    src={`${IMG_BASE}${aug.image}`}
                    alt={aug.name}
                    className="w-5 h-5 rounded object-cover shrink-0"
                    onError={e => {
                      const el = e.target as HTMLImageElement;
                      el.style.display = 'none';
                    }}
                  />
                  <div className="flex flex-col flex-1 min-w-0">
                    <span className={`text-[11px] truncate ${ value === aug.image ? 'text-amber-200 font-semibold' : 'text-zinc-300' }`}>
                      {aug.name}
                    </span>
                    <span className="text-[9px] text-zinc-500 font-mono">
                      {aug.tier === 1 ? 'Tier I (Bạc)' : aug.tier === 3 ? 'Tier III (Kim Cương)' : 'Tier II (Vàng)'}
                      {aug.is_destiny ? ' • Destiny' : ''}
                    </span>
                  </div>
                  {value === aug.image && <CheckCircle2 className="w-3 h-3 text-amber-400 ml-auto shrink-0" />}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
