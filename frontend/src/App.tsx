import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Navbar } from './components/Navbar';
import { ChatPage } from './pages/ChatPage';
import { HomePage } from './pages/HomePage';
import { ShopPage } from './pages/ShopPage';

export const App: React.FC = () => (
  <BrowserRouter>
    <Navbar />
    <main>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/shop" element={<ShopPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </main>
    <footer className="footer">© Онлайн-Церковь · Православный приход</footer>
  </BrowserRouter>
);

export default App;
