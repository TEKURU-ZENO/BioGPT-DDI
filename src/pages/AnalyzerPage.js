import React, { useState } from 'react';
import axios from 'axios';
import GlassCard from '../components/common/GlassCard';
import './AnalyzerPage.css';

const API_BASE_URL = ''; // Vercel handles this automatically

function AnalyzerPage() {
  const = useState('');
  const = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const = useState(null);
  const = useState('patient');

  const handleAnalyze = async () => {
    if (!drug1 ||!drug2) {
      setError('Please enter both drug names.');
      return;
    }
    setIsLoading(true);
    setError('');
    setResult(null);

    try {
      const response = await axios.post(`${API_BASE_URL}/api/predict`, { drug1, drug2 });
      setResult(response.data);
      setActiveTab('patient'); // Default to patient tab on new result
    } catch (err) {
      setError('An error occurred. The AI model might be starting up (cold start). Please try again in a moment.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const getSeverityClass = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'major': return 'severity-major';
      case 'moderate': return 'severity-moderate';
      case 'minor': return 'severity-minor';
      default: return 'severity-unknown';
    }
  };

  return (
    <div className="analyzer-container">
      <h2>Drug Interaction Analyzer</h2>
      <p className="page-subtitle">Enter two drugs to analyze their potential interaction.</p>
      
      <GlassCard style={{ maxWidth: '600px', margin: 'auto' }}>
        <div className="input-form">
          <input
            type="text"
            value={drug1}
            onChange={(e) => setDrug1(e.target.value)}
            placeholder="Enter Drug 1 (e.g., Warfarin)"
          />
          <input
            type="text"
            value={drug2}
            onChange={(e) => setDrug2(e.target.value)}
            placeholder="Enter Drug 2 (e.g., Aspirin)"
          />
          <button onClick={handleAnalyze} disabled={isLoading}>
            {isLoading? 'Analyzing...' : 'Analyze Interaction'}
          </button>
        </div>
        {error && <p className="error-message">{error}</p>}
      </GlassCard>

      {isLoading && <div className="loader"></div>}

      {result && (
        <GlassCard style={{ maxWidth: '800px', margin: '2rem auto', textAlign: 'left' }}>
          <h3>Analysis Report</h3>
          <div className="result-header">
            <span className={`severity-badge ${getSeverityClass(result.severity)}`}>
              {result.severity}
            </span>
            <span className="prediction-type">
              Predicted Interaction Type: <strong>{result.prediction}</strong>
            </span>
          </div>
          
          <div className="tabs">
            <button 
              className={`tab-button ${activeTab === 'patient'? 'active' : ''}`}
              onClick={() => setActiveTab('patient')}>
              Patient Summary
            </button>
            <button 
              className={`tab-button ${activeTab === 'professional'? 'active' : ''}`}
              onClick={() => setActiveTab('professional')}>
              Professional Details
            </button>
          </div>

          <div className="tab-content">
            {activeTab === 'patient' && (
              <div>
                <h4>Summary for Patients</h4>
                <p className="report-text">{result.patient_report}</p>
              </div>
            )}
            {activeTab === 'professional' && (
              <div>
                <h4>Summary for Healthcare Professionals</h4>
                <p className="report-text">{result.professional_report}</p>
              </div>
            )}
          </div>
        </GlassCard>
      )}
    </div>
  );
}

export default AnalyzerPage;