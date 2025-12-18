import React from 'react';
import GlassCard from '../components/common/GlassCard';

function AboutProjectPage() {
  return (
    <div style={{ maxWidth: '800px', margin: 'auto', textAlign: 'left' }}>
      <h2>About the Project</h2>
      <GlassCard>
        <p>This project, BioGPT-DI, is a real-world AI healthcare assistant designed to predict drug-drug interactions (DDI) and generate explainable clinical reports.</p>
        <p>It leverages a powerful two-engine AI system:</p>
        <ul>
          <li>A custom-trained **BioBERT** model, fine-tuned on the DDI 2013 Corpus, serves as a high-accuracy classifier to predict the specific type of interaction.</li>
          <li>Microsoft's **BioGPT**, a generative model, then writes detailed, human-readable summaries based on the prediction, tailored for both healthcare professionals and patients.</li>
        </ul>
        <p>The goal is to move beyond simple database lookups and provide actionable, context-aware insights to improve medication safety.</p>
      </GlassCard>
    </div>
  );
}


export default AboutProjectPage;
