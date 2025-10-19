import React, { useState } from 'react';
import axios from 'axios';
import GlassCard from '../components/common/GlassCard';
import './AnalyzerPage.css';

const API_BASE_URL = '';

function AnalyzerPage() {
  const [drug1, setDrug1] = useState('');
  const [drug2, setDrug2] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [activeTab, setActiveTab] = useState('patient');
  const [showDownloadModal, setShowDownloadModal] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  const handleAnalyze = async () => {
    if (!drug1 || !drug2) {
      setError('Please enter both drug names.');
      return;
    }
    setIsLoading(true);
    setError('');
    setResult(null);

    try {
      const response = await axios.post(`${API_BASE_URL}/api/predict`, { 
        drug1, 
        drug2 
      });
      setResult(response.data);
      setActiveTab('patient');
    } catch (err) {
      setError('An error occurred during analysis. Please try again.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownloadPDF = async (reportType) => {
    setIsDownloading(true);
    
    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/generate-pdf`,
        {
          drug1,
          drug2,
          report_type: reportType,
          prediction_data: result
        },
        {
          responseType: 'blob'
        }
      );

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute(
        'download',
        `DDI_Report_${reportType}_${drug1}_${drug2}.pdf`
      );
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      setShowDownloadModal(false);
    } catch (err) {
      setError('Failed to generate PDF report. Please try again.');
      console.error(err);
    } finally {
      setIsDownloading(false);
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
      <p className="page-subtitle">
        Enter two drugs to analyze their potential interaction.
      </p>
      
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
            {isLoading ? 'Analyzing...' : 'Analyze Interaction'}
          </button>
        </div>
        {error && <p className="error-message">{error}</p>}
      </GlassCard>

      {isLoading && (
        <div className="loader-container">
          <div className="loader"></div>
          <p>Analyzing drug interaction...</p>
        </div>
      )}

      {result && (
        <>
          <GlassCard style={{ maxWidth: '800px', margin: '2rem auto', textAlign: 'left' }}>
            <div className="result-header-container">
              <h3>Analysis Report</h3>
              <button 
                className="download-btn"
                onClick={() => setShowDownloadModal(true)}
              >
                📥 Download Detailed Report
              </button>
            </div>
            
            <div className="result-header">
              <span className={`severity-badge ${getSeverityClass(result.severity)}`}>
                {result.severity}
              </span>
              <span className="prediction-type">
                Interaction Type: <strong>{result.prediction}</strong>
              </span>
            </div>
            
            <div className="tabs">
              <button 
                className={`tab-button ${activeTab === 'patient' ? 'active' : ''}`}
                onClick={() => setActiveTab('patient')}
              >
                Patient Summary
              </button>
              <button 
                className={`tab-button ${activeTab === 'professional' ? 'active' : ''}`}
                onClick={() => setActiveTab('professional')}
              >
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

          {/* Download Modal */}
          {showDownloadModal && (
            <div className="modal-overlay" onClick={() => setShowDownloadModal(false)}>
              <GlassCard 
                className="modal-content" 
                onClick={(e) => e.stopPropagation()}
                style={{ maxWidth: '500px' }}
              >
                <h3>Download Detailed Report</h3>
                <p style={{ marginBottom: '1.5rem' }}>
                  Choose the type of detailed PDF report you'd like to download:
                </p>
                
                <div className="download-options">
                  <div className="download-option">
                    <h4>👤 Patient Report</h4>
                    <p>
                      Easy-to-understand explanation with practical guidance for patients 
                      and caregivers. Includes what to watch for and questions to ask your doctor.
                    </p>
                    <button
                      className="download-option-btn patient-btn"
                      onClick={() => handleDownloadPDF('patient')}
                      disabled={isDownloading}
                    >
                      {isDownloading ? 'Generating...' : 'Download Patient Report'}
                    </button>
                  </div>

                  <div className="download-option">
                    <h4>⚕️ Professional Report</h4>
                    <p>
                      Comprehensive clinical analysis with pharmacological mechanisms, 
                      monitoring parameters, and evidence-based management strategies.
                    </p>
                    <button
                      className="download-option-btn professional-btn"
                      onClick={() => handleDownloadPDF('professional')}
                      disabled={isDownloading}
                    >
                      {isDownloading ? 'Generating...' : 'Download Professional Report'}
                    </button>
                  </div>
                </div>

                <button 
                  className="close-modal-btn"
                  onClick={() => setShowDownloadModal(false)}
                  disabled={isDownloading}
                >
                  Cancel
                </button>
              </GlassCard>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default AnalyzerPage;
