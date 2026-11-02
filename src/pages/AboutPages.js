import React from 'react';
import GlassCard from '../components/common/GlassCard';

function AboutProjectPage() {
  return (
    <div style={{ maxWidth: '800px', margin: 'auto', textAlign: 'left' }}>
      <h2>About the Project</h2>
      <GlassCard>
        <p>
          BioGPT-DDI is a research prototype for explainable drug–drug interaction (DDI) screening. It is built
          so that every severity it reports can be traced back to a mechanism and a source.
        </p>
        <h3>How a result is produced</h3>
        <ol>
          <li>
            <strong>Normalization</strong> – brand names, salts, doses and combination products (e.g. Percocet,
            Bactrim) are mapped to active ingredients. Typos are never auto-corrected; you get suggestions instead.
          </li>
          <li>
            <strong>Curated rules</strong> – interactions documented in product labeling and FDA safety
            communications, each with mechanism, clinical effect, management and sources.
          </li>
          <li>
            <strong>Mechanism engine</strong> – infers interactions from CYP450 / P-glycoprotein roles (FDA
            index-drug classification), prodrug activation, and pharmacodynamic risk axes such as serotonin
            toxicity, QT prolongation, CNS depression, bleeding and hyperkalaemia.
          </li>
          <li>
            <strong>Grounded reports</strong> – patient and professional summaries are assembled only from those
            findings, so the explanation can never contradict the severity.
          </li>
        </ol>
        <h3>Where BioGPT fits</h3>
        <p>
          Microsoft's BioGPT is a biomedical language model whose documented strength is relation extraction from
          literature. In this project it is an optional, clearly labelled source of literature-style context and
          never decides severity. The roadmap uses it to mine PubMed for emerging interactions.
        </p>
        <h3>Limitations</h3>
        <p>
          The knowledge base covers a curated set of about 230 common ingredients. It does not yet model dose, renal or hepatic
          function, or pharmacogenomics. It has not been clinically validated and is not a substitute for a
          pharmacist or a licensed interaction database.
        </p>
      </GlassCard>
    </div>
  );
}

export default AboutProjectPage;
