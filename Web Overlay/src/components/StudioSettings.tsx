import { useEffect, useState } from 'react';
import { StudioApi } from '../lib/api';

export default function StudioSettings({onMessage}: {onMessage: (message: string) => void}) {
  const [riotId, setRiotId] = useState('');
  const [region, setRegion] = useState('VN');
  const [apiKey, setApiKey] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    StudioApi.getAppState().then(state => {
      if (active) { setRiotId(state.config?.riot_id || ''); setRegion(state.config?.region || 'VN'); }
    }).catch(() => {});
    return () => { active = false; };
  }, []);
  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    try { await action(); } catch (error) { onMessage(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(false); }
  };
  return <details className="rounded-lg border border-zinc-700 p-3 text-xs">
    <summary className="cursor-pointer font-semibold">Cài đặt Riot & xuất ảnh</summary>
    <form className="mt-3 space-y-2" onSubmit={event => {
      event.preventDefault();
      void run(async () => {
        const result = await StudioApi.saveRiotSettings({riot_id: riotId, region, ...(apiKey ? {api_key: apiKey} : {})});
        if (!result.success) throw new Error(result.error);
        setApiKey('');
        onMessage('Đã lưu cấu hình Riot. Chọn Tải trận mới nhất để lấy dữ liệu.');
      });
    }}>
      <label className="block">Riot ID
        <input required value={riotId} onChange={e => setRiotId(e.target.value)} placeholder="GameName#TagLine" className="mt-1 w-full rounded bg-zinc-800 p-2" />
      </label>
      <label className="block">Khu vực
        <select value={region} onChange={e => setRegion(e.target.value)} className="mt-1 w-full rounded bg-zinc-800 p-2">
          {['VN','VN2','SG','SG2','TH','TH2','PH','PH2','TW','TW2','SEA','KR','JP','JP1','NA','NA1','BR','BR1','LAN','LA1','LAS','LA2','OCE','OC1','EUW','EUW1','EUNE','EUN1','TR','TR1','RU'].map(r => <option key={r}>{r}</option>)}
        </select>
      </label>
      <label className="block">API key mới (để trống để giữ key hiện tại)
        <input type="password" autoComplete="off" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="RGAPI-…" className="mt-1 w-full rounded bg-zinc-800 p-2" />
      </label>
      <button disabled={busy} className="rounded bg-blue-800 px-3 py-2 disabled:opacity-50">Lưu cấu hình</button>
    </form>
    <div className="mt-3 flex flex-wrap gap-2">
      <button disabled={busy} className="rounded bg-zinc-800 p-2" onClick={() => void run(async () => {
        const result = await StudioApi.fetchLatestMatch();
        if (!result.success) throw new Error(result.error);
        onMessage(result.message || 'Đang tải trận…');
      })}>Tải trận mới nhất</button>
      <button disabled={busy} className="rounded bg-zinc-800 p-2" onClick={() => void run(async () => {
        const result = await StudioApi.exportOverlayImage();
        if (!result.success) throw new Error(result.error);
        onMessage(`Đã xuất ảnh: ${result.filePath}`);
      })}>Xuất PNG</button>
      <button className="rounded bg-zinc-800 p-2" onClick={() => void run(() => StudioApi.openBrowserPanel())}>Browser Panel</button>
    </div>
  </details>;
}
