import React from 'react';
import { Link } from 'react-router-dom';
import './HomePage.css';

function HomePage() {
  return (
    <div className="home-container">
      <h1 className="home-title">AI-Powered Drug Interaction Analysis</h1>
      <p className="home-subtitle">Mechanism-aware, source-cited drug–drug interaction screening with clear reports for both patients and healthcare professionals. A research prototype, not medical advice.</p>
      <Link to="/analyzer" className="cta-button">
        Start Analyzing
      </Link>
    </div>
  );
}

export default HomePage;