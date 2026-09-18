import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Navbar } from './components/Navbar';
import { CatalogPage } from './pages/CatalogPage';
import { TrebyPage } from './pages/TrebyPage';
import { ConfessionPage } from './pages/ConfessionPage';
import { StreamsPage } from './pages/StreamsPage';
import { AnalyticsDashboard } from './pages/AnalyticsDashboard';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Navbar />
      <Routes>
        <Route path="/" element={<CatalogPage />} />
        <Route path="/treby" element={<TrebyPage />} />
        <Route path="/confession" element={<ConfessionPage />} />
        <Route path="/streams" element={<StreamsPage />} />
        <Route path="/analytics" element={<AnalyticsDashboard />} />
      </Routes>
    </BrowserRouter>
  );
};
export default App;
