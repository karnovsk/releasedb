import { Routes, Route, Navigate } from 'react-router-dom';
import ReleasesPage from './pages/ReleasesPage';
import LineagePage from './pages/LineagePage';

export default function App() {
  return (
    <div className="flex flex-col h-full bg-gray-950">
      <header className="flex items-center gap-3 px-6 py-3 border-b border-gray-800 shrink-0">
        <span className="text-lg font-semibold tracking-tight text-white">ReleaseDB</span>
        <span className="text-gray-600 text-sm">read-only view</span>
      </header>
      <main className="flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<ReleasesPage />} />
          <Route path="/lineage/:id" element={<LineagePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
