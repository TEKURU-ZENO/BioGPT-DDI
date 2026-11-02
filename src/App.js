import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Navbar from './components/common/Navbar';
import HomePage from './pages/HomePage';
import AnalyzerPage from './pages/AnalyzerPage';
import RegimenPage from './pages/RegimenPage';
import AboutProjectPage from './pages/AboutPages';
import AboutGroupPage from './pages/AboutGroup';
import './App.css';

function App() {
  return (
    <div className="App">
      <div className="background-gradient"></div>
      <Navbar />
      <main className="content">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/analyzer" element={<AnalyzerPage />} />
          <Route path="/regimen" element={<RegimenPage />} />
          <Route path="/about-project" element={<AboutProjectPage />} />
          <Route path="/about-group" element={<AboutGroupPage />} />
        </Routes>
      </main>
    </div>
  );
}


export default App;
