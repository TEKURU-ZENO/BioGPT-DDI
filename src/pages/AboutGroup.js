import React from 'react';
import GlassCard from '../components/common/GlassCard';

function AboutGroupPage() {
  return (
    <div style={{ maxWidth: '800px', margin: 'auto', textAlign: 'left' }}>
      <h2>About the Group</h2>
      <GlassCard>
        <p>This is where you can describe your team or group.</p>
        <p>You can add information about your members, your mission, and your collective expertise in fields like NLP, Generative AI, Health AI, and Bioinformatics.</p>
        {/* Example Member */}
        <div style={{ marginTop: '20px' }}>
          <strong>Team Member 1:</strong> Lead AI Architect
        </div>
        <div style={{ marginTop: '10px' }}>
          <strong>Team Member 2:</strong> Frontend & UI/UX Specialist
        </div>
        <div style={{ marginTop: '10px' }}>
          <strong>Team Member 3:</strong> Data Analyst & Researcher
        </div>
      </GlassCard>
    </div>
  );
}

export default AboutGroupPage;