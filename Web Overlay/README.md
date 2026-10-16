# Web Overlay - Desktop Control Panel

Frontend control panel for TFT Post-Match Studio, built with React 19, TypeScript, and Tailwind CSS v4.

The control panel manages match synchronization, tournament titles, Riot account switching, augment selection, and overlay rendering.

---

## Architecture and Runtime Modes

The application runs in two operational contexts:

1. **PyWebView Desktop Mode (Default)**:
   - Launched by `desktop/app.py` inside a Microsoft Edge WebView2 window.
   - Built with `vite-plugin-singlefile` to bundle HTML, JavaScript, and CSS into a single `dist/index.html` file.
   - Communicates with the Python backend via the native `window.pywebview.api` IPC bridge (`StudioBridge`).

2. **Standalone Browser Mode**:
   - Served over HTTP by FastAPI at `http://localhost:8080/app`.
   - Useful for remote control from a second monitor, tablet, or browser window on the local network.

---

## Tech Stack

- **Framework**: React 19
- **Build Tool**: Vite 8
- **Language**: TypeScript 5.7
- **Styling**: Tailwind CSS v4 via `@tailwindcss/vite`
- **Icons**: Lucide React
- **Packaging**: `vite-plugin-singlefile`
- **Formatter**: oxfmt

---

## Getting Started

### Prerequisites

- Node.js version 18 or higher
- npm or pnpm package manager

### Available Scripts

Install dependencies:
```bash
npm install
```

Start Vite development server:
```bash
npm run dev
```
The development server starts at `http://localhost:5173`. When running without PyWebView, the panel uses local HTTP REST endpoints against the running backend at `http://localhost:8080`.

Build for production:
```bash
npm run build
```
Outputs the standalone distribution file to `dist/index.html`. This file is loaded by `desktop/app.py` and bundled by PyInstaller into release executables.

Preview the production build:
```bash
npm run preview
```

Format code:
```bash
npm run format
```

---

## Component Structure

```text
Web Overlay/
├── src/
│   ├── components/
│   │   └── SourceTransformPanel.tsx  # Main panel (Riot ID, augment selector, tournament config, render trigger)
│   ├── App.tsx                       # Root container, background grid, and status footer
│   ├── index.css                     # Tailwind CSS v4 theme entrypoint
│   ├── main.tsx                      # React DOM root entrypoint
│   └── vite-env.d.ts                 # Vite environment type declarations
├── dist/                             # Compiled bundle (index.html)
├── package.json                      # Dependencies and npm scripts
├── tsconfig.json                     # TypeScript compiler configuration
└── vite.config.ts                    # Vite plugins and bundle settings
```

---

## IPC Bridge Communication

When running in PyWebView, React invokes Python methods on the global object:

```typescript
// Example: trigger overlay render via PyWebView IPC
if (window.pywebview?.api?.render_overlay) {
  const result = await window.pywebview.api.render_overlay();
  console.log('Render status:', result);
}
```

The Python backend also sends state updates back to React by evaluating JavaScript callbacks:

```javascript
// Window event fired on configuration updates
window.dispatchEvent(new CustomEvent('onAppStateUpdate', { detail: payload }));
```
