import React, { useState } from 'react';
import axios from 'axios';
import GlassCard from '../components/common/GlassCard';
import { severityClass } from '../utils/severity';
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
  const [analyzedPair, setAnalyzedPair] = useState(null);

  const runAnalysis = async (d1, d2) => {
    if (!d1.trim() || !d2.trim()) {
      setError('Please enter both drug names.');
      return;
    }
    setIsLoading(true);
    setError('');
    setResult(null);

    try {
      const response = await axios.post(`${API_BASE_URL}/api/predict`, { drug1: d1, drug2: d2 });
      setResult(response.data);
      setAnalyzedPair({ drug1: d1, drug2: d2 });
      setActiveTab('patient');
    } catch (err) {
      if (err.response?.status === 422) {
        setError('Please enter valid drug names (letters, numbers and basic punctuation, max 100 characters).');
      } else {
        setError('An error occurred during analysis. Please try again.');
      }
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAnalyze = () => runAnalysis(drug1, drug2);

  const applySuggestion = (which, value) => {
    const d1 = which === 1 ? value : drug1;
    const d2 = which === 2 ? value : drug2;
    setDrug1(d1);
    setDrug2(d2);
    runAnalysis(d1, d2);
  };

  const handleDownloadPDF = async (reportType) => {
    if (!analyzedPair) return;
    setIsDownloading(true);

    try {
      // The server re-runs the analysis; only the drug names are sent.
      const response = await axios.post(
        `${API_BASE_URL}/api/generate-pdf`,
        { ...analyzedPair, report_type: reportType },
        { responseType: 'blob' }
      );

      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
      const link = document.createElement('a');
      link.href = url;
      const safe = (t) => t.replace(/[^A-Za-z0-9_-]+/g, '_').slice(0, 40);
      link.setAttribute(
        'download',
        `DDI_Report_${reportType}_${safe(analyzedPair.drug1)}_${safe(analyzedPair.drug2)}.pdf`
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

  const getSeverityClass = severityClass;

  return (
    <div className="analyzer-container">
      <h2>Drug Interaction Analyzer</h2>
      <p className="page-subtitle">
        Enter two drugs (generic or brand names) to check for a documented or mechanism-based interaction.
      </p>
      <p className="disclaimer-banner" role="note">
        For education and research only. Not medical advice and not a substitute for a pharmacist or a licensed
        interaction database. No alert does not mean a combination is safe.
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
              {(result.status === 'interaction_found' || result.status === 'no_known_interaction') && (
                <button className="download-btn" onClick={() => setShowDownloadModal(true)}>
                  📥 Download Detailed Report
                </button>
              )}
            </div>

            <div className="result-header">
              <span className={`severity-badge ${getSeverityClass(result.severity)}`}>
                {result.severity}
              </span>
              <span className="prediction-type">
                {result.drug1?.display_name || result.drug1?.input} + {result.drug2?.display_name || result.drug2?.input}
                {' · '}<strong>{result.prediction}</strong>
              </span>
            </div>

            {result.status !== 'interaction_found' && (
              <div className={`status-note status-${result.status}`}>
                <p>{result.message}</p>
                {result.predicted_signals?.map((sig) => (
                  <p key={sig.drugs.join('|')} className="finding-meta">
                    <strong>{sig.label}</strong> ({sig.drugs.join(' + ')}, p={sig.probability}). {sig.note}
                  </p>
                ))}
                {[1, 2].map((n) => {
                  const d = result[`drug${n}`];
                  if (!d || d.recognized || !d.suggestions?.length) return null;
                  return (
                    <p key={n} className="suggestions">
                      Did you mean{' '}
                      {d.suggestions.map((sug) => (
                        <button key={sug} className="suggestion-chip" onClick={() => applySuggestion(n, sug)}>
                          {sug}
                        </button>
                      ))}
                      {' '}for “{d.input}”?
                    </p>
                  );
                })}
              </div>
            )}

            {result.status === 'interaction_found' && (
              <>
                {result.confidence && <p className="confidence-line">Confidence: {result.confidence}</p>}
                {result.severity_discrepancies?.map((d) => (
                  <p key={d.drugs.join('|')} className="status-note status-insufficient_data">
                    {d.source} grades {d.drugs.join(' + ')} as <strong>{d.source_severity}</strong> (this engine:{' '}
                    {d.engine_severity}). Check a clinical reference.
                  </p>
                ))}
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
                      {result.findings.map((f) => (
                        <p key={f.title} className="report-text">{f.patient_summary}</p>
                      ))}
                      {(() => {
                        const watch = [...new Set(result.findings.flatMap((f) => f.watch_for))];
                        return watch.length > 0 && (
                          <>
                            <h4>Get medical advice if you notice</h4>
                            <ul className="watch-list">
                              {watch.map((w) => <li key={w}>{w}</li>)}
                            </ul>
                          </>
                        );
                      })()}
                      <p className="report-text">
                        Do not stop or change any medicine on your own. Speak to your doctor or pharmacist first,
                        and seek emergency care for severe symptoms.
                      </p>
                    </div>
                  )}
                  {activeTab === 'professional' && (
                    <div>
                      <h4>Findings for Healthcare Professionals</h4>
                      {result.findings.map((f, i) => (
                        <div key={f.title} className="finding-card">
                          <div className="finding-title">
                            <span className={`severity-badge small ${getSeverityClass(f.severity)}`}>{f.severity}</span>
                            <strong>{i + 1}. {f.title}</strong>
                          </div>
                          <p className="finding-meta">{f.category} · {f.evidence_level}</p>
                          <p><strong>Mechanism:</strong> {f.mechanism}</p>
                          {f.pk_estimate && (
                            <p><strong>Estimated exposure change:</strong> {f.pk_estimate.summary}{' '}
                              <span className="finding-meta">({f.pk_estimate.model})</span></p>
                          )}
                          <p><strong>Clinical effect:</strong> {f.effect}</p>
                          <p><strong>Management:</strong> {f.management}</p>
                          {f.label_evidence?.filter((c) => c.excerpt).map((c) => (
                            <blockquote key={c.url} className="label-quote">
                              “{c.excerpt}”
                              <footer>
                                — <a href={c.url} target="_blank" rel="noopener noreferrer">{c.title || `${c.label_of} label`}</a>
                              </footer>
                            </blockquote>
                          ))}
                          {f.evidence.length > 0 && (
                            <details>
                              <summary>Sources ({f.evidence.length})</summary>
                              <ul>{f.evidence.map((e) => <li key={e}>{e}</li>)}</ul>
                            </details>
                          )}
                        </div>
                      ))}
                      {result.literature_context && (
                        <div className="finding-card experimental">
                          <p className="finding-meta">{result.literature_context_note}</p>
                          <p>{result.literature_context}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </>
            )}
            <p className="kb-footnote">Knowledge base v{result.kb_version}</p>
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

