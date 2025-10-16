import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Navbar from './components/common/Navbar';
import HomePage from './pages/HomePage';
import AnalyzerPage from './pages/AnalyzerPage';
import AboutProjectPage from './pages/AboutProjectPage';
import AboutGroupPage from './pages/AboutGroupPage';
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
          <Route path="/about-project" element={<AboutProjectPage />} />
          <Route path="/about-group" element={<AboutGroupPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;