import { Suspense, lazy, useState } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Navbar } from './components/layout/Navbar';

const Dashboard = lazy(() => import('./pages/Dashboard').then((m) => ({ default: m.Dashboard })));
const StockPicker = lazy(() => import('./pages/StockPicker').then((m) => ({ default: m.StockPicker })));
const SettingsModal = lazy(() => import('./components/SettingsModal').then((m) => ({ default: m.SettingsModal })));

function PageFallback() {
  return (
    <div className="flex-1 flex items-center justify-center text-text-muted text-sm">
      載入中...
    </div>
  );
}

function App() {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  return (
    <Router>
      <div className="min-h-screen flex flex-col">
        <Navbar onSettingsClick={() => setIsSettingsOpen(true)} />

        <main className="flex-1 flex flex-col">
          <Suspense fallback={<PageFallback />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/picker" element={<StockPicker />} />
            </Routes>
          </Suspense>
        </main>

        <Suspense fallback={null}>
          <SettingsModal
            isOpen={isSettingsOpen}
            onClose={() => setIsSettingsOpen(false)}
          />
        </Suspense>
      </div>
    </Router>
  );
}

export default App;
