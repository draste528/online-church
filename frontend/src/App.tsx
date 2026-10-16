import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Navbar } from './components/Navbar';
import { I18nProvider, useI18n } from './i18n';
import { ChatPage } from './pages/ChatPage';
import { DonatePage } from './pages/DonatePage';
import { ForgivenessPage } from './pages/ForgivenessPage';
import { HomePage } from './pages/HomePage';
import { LibraryPage } from './pages/LibraryPage';
import { ShopPage } from './pages/ShopPage';

const Footer: React.FC = () => {
  const { m } = useI18n();
  return <footer className="footer">{m.footer}</footer>;
};

export const App: React.FC = () => (
  <I18nProvider>
    <BrowserRouter>
      <Navbar />
      <main>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/shop" element={<ShopPage />} />
          <Route path="/forgiveness" element={<ForgivenessPage />} />
          <Route path="/library" element={<LibraryPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/donate" element={<DonatePage />} />
          <Route path="/donations" element={<Navigate to="/donate" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <Footer />
    </BrowserRouter>
  </I18nProvider>
);

export default App;
