import React, { useState } from 'react';
import axios from 'axios';
import GlassCard from '../components/common/GlassCard';
import { severityClass } from '../utils/severity';
import './AnalyzerPage.css';
import './RegimenPage.css';

const PHENOTYPES = {
  CYP2D6: ['', 'PM', 'IM', 'NM', 'UM'],
  CYP2C19: ['', 'PM', 'IM', 'NM', 'RM', 'UM'],
  CYP2C9: ['', 'PM', 'IM', 'NM'],
};
const PHENO_LABEL = { '': 'Unknown', PM: 'Poor', IM: 'Intermediate', NM: 'Normal', RM: 'Rapid', UM: 'Ultrarapid' };
const MAX_DRUGS = 15;

function RegimenPage() {
  const [drugs, setDrugs] = useState(['', '', '']);
  const [age, setAge] = useState('');
  const [egfr, setEgfr] = useState('');
  const [pgx, setPgx] = useState({ CYP2D6: '', CYP2C19: '', CYP2C9: '' });
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [openPair, setOpenPair] = useState(null);

  const updateDrug = (i, v) => setDrugs((d) => d.map((x, j) => (j === i ? v : x)));
  const removeDrug = (i) => setDrugs((d) => (d.length > 2 ? d.filter((_, j) => j !== i) : d));
  const addDrug = () => setDrugs((d) => (d.length < MAX_DRUGS ? [...d, ''] : d));

  const handleCheck = async () => {
    const list = drugs.map((d) => d.trim()).filter(Boolean);
    if (list.length < 2) {
      setError('Enter at least two medicines.');
      return;
    }
    const patient = {};
    if (age !== '') patient.age = Number(age);
    if (egfr !== '') patient.egfr = Number(egfr);
    const genotypes = Object.fromEntries(Object.entries(pgx).filter(([, v]) => v));
    if (Object.keys(genotypes).length) patient.pgx = genotypes;

    setIsLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await axios.post('/api/regimen', { drugs: list, patient });
      setResult(res.data);
      setOpenPair(null);
    } catch (err) {
      setError(err.response?.status === 422
        ? 'Please check the inputs (drug names, age 0-120, eGFR 0-200).'
        : 'An error occurred during analysis. Please try again.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const unrecognized = result?.drugs.filter((d) => !d.recognized) || [];
  const interacting = result?.pairs.filter((p) => p.findings.length > 0) || [];
  const burden = result?.burden;

  return (
    <div className="analyzer-container">
      <h2>Medication List Check</h2>
      <p className="page-subtitle">
        Screen a whole medication list: every pair, cumulative risks, and optional patient context.
      </p>
      <p className="disclaimer-banner" role="note">
        For education and research only. Not medical advice and not a substitute for a pharmacist or a licensed
        interaction database.
      </p>

      <GlassCard style={{ maxWidth: '700px', margin: 'auto' }}>
        <div className="input-form">
          {drugs.map((d, i) => (
            <div className="drug-row" key={i}>
              <input
                type="text"
                value={d}
                aria-label={`Medicine ${i + 1}`}
                onChange={(e) => updateDrug(i, e.target.value)}
                placeholder={`Medicine ${i + 1}`}
              />
              {drugs.length > 2 && (
                <button type="button" className="icon-btn" aria-label={`Remove medicine ${i + 1}`}
                  onClick={() => removeDrug(i)}>×</button>
              )}
            </div>
          ))}
          {drugs.length < MAX_DRUGS && (
            <button type="button" className="secondary-btn" onClick={addDrug}>+ Add medicine</button>
          )}

          <details className="patient-panel">
            <summary>Patient context (optional)</summary>
            <div className="patient-grid">
              <label>Age (years)
                <input type="number" min="0" max="120" value={age} onChange={(e) => setAge(e.target.value)} />
              </label>
              <label>eGFR (mL/min/1.73m²)
                <input type="number" min="0" max="200" value={egfr} onChange={(e) => setEgfr(e.target.value)} />
              </label>
              {Object.entries(PHENOTYPES).map(([gene, options]) => (
                <label key={gene}>{gene} phenotype
                  <select value={pgx[gene]} onChange={(e) => setPgx({ ...pgx, [gene]: e.target.value })}>
                    {options.map((o) => <option key={o} value={o}>{PHENO_LABEL[o]}{o ? ` (${o})` : ''}</option>)}
                  </select>
                </label>
              ))}
            </div>
          </details>

          <button onClick={handleCheck} disabled={isLoading}>
            {isLoading ? 'Checking...' : 'Check Medication List'}
          </button>
        </div>
        {error && <p className="error-message">{error}</p>}
      </GlassCard>

      {isLoading && <div className="loader-container"><div className="loader"></div></div>}

      {result && (
        <GlassCard style={{ maxWidth: '900px', margin: '2rem auto', textAlign: 'left' }}>
          <div className="result-header">
            <span className={`severity-badge ${severityClass(result.highest_severity)}`}>
              {result.highest_severity}
            </span>
            <span className="prediction-type">
              Highest pairwise severity across {result.drugs.length} medicines
            </span>
          </div>

          {unrecognized.length > 0 && (
            <div className="status-note status-unrecognized_drug">
              Not recognised (not checked): {unrecognized.map((d) => d.input).join(', ')}.
              {unrecognized.some((d) => d.suggestions?.length) && (
                <> Did you mean {unrecognized.flatMap((d) => d.suggestions).join(', ')}?</>
              )}
            </div>
          )}

          {result.patient_alerts?.length > 0 && (
            <>
              <h3>Patient-specific alerts</h3>
              {result.patient_alerts.map((a, i) => (
                <div key={i} className={`alert-card alert-${a.level}`}>
                  <strong>{a.title}</strong>
                  <p>{a.message}</p>
                  {a.source && <p className="finding-meta">{a.source}</p>}
                </div>
              ))}
            </>
          )}

          {burden && (
            <>
              <h3>Cumulative risk</h3>
              <div className="burden-grid">
                <div className="burden-tile"><span>{burden.anticholinergic.total}</span>Anticholinergic burden (ACB)</div>
                <div className="burden-tile"><span>{burden.qt_known_risk.length}</span>Known-risk QT drugs</div>
                <div className="burden-tile"><span>{burden.serotonergic.length}</span>Serotonergic drugs</div>
                <div className="burden-tile"><span>{burden.cns_active.length}</span>CNS-active drugs</div>
                <div className="burden-tile"><span>{burden.bleeding_risk.length}</span>Bleeding-risk drugs</div>
              </div>
              {burden.alerts.map((a) => (
                <div key={a.axis} className={`alert-card alert-${a.level}`}>
                  <p>{a.message}</p>
                  <p className="finding-meta">{a.source}</p>
                </div>
              ))}
            </>
          )}

          <h3>Interacting pairs ({interacting.length})</h3>
          {interacting.length === 0 && (
            <p className="report-text">
              No pairwise interactions found in this knowledge base. This does not guarantee the combination is safe.
            </p>
          )}
          {interacting.map((p) => {
            const key = `${p.drug1}|${p.drug2}`;
            const open = openPair === key;
            return (
              <div key={key} className="finding-card">
                <button className="pair-toggle" aria-expanded={open} onClick={() => setOpenPair(open ? null : key)}>
                  <span className={`severity-badge small ${severityClass(p.severity)}`}>{p.severity}</span>
                  <strong>{p.drug1} + {p.drug2}</strong>
                  <span className="finding-meta"> · {p.findings.length} finding(s) {open ? '▲' : '▼'}</span>
                </button>
                {open && p.findings.map((f) => (
                  <div key={f.title} className="pair-finding">
                    <p><span className={`severity-badge small ${severityClass(f.severity)}`}>{f.severity}</span>
                      <strong>{f.title}</strong></p>
                    {f.pk_estimate && <p className="finding-meta">Estimated exposure change: {f.pk_estimate.summary}</p>}
                    <p><strong>Effect:</strong> {f.effect}</p>
                    <p><strong>Management:</strong> {f.management}</p>
                  </div>
                ))}
              </div>
            );
          })}
          <p className="kb-footnote">Knowledge base v{result.kb_version}</p>
        </GlassCard>
      )}
    </div>
  );
}

export default RegimenPage;
