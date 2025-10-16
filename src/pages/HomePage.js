import React from 'react';
import { Link } from 'react-router-dom';
import './HomePage.css';

function HomePage() {
  return (
    <div className="home-container">
      <h1 className="home-title">AI-Powered Drug Interaction Analysis</h1>
      <p className="home-subtitle">Leveraging state-of-the-art biomedical language models to provide accurate DDI predictions and generate clear, explainable clinical reports for both professionals and patients.</p>
      <Link to="/analyzer" className="cta-button">
        Start Analyzing
      </Link>
    </div>
  );
}

export default HomePage;