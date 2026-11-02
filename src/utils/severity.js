export const severityClass = (severity) => {
  switch (severity?.toLowerCase()) {
    case 'contraindicated': return 'severity-contraindicated';
    case 'major': return 'severity-major';
    case 'moderate': return 'severity-moderate';
    case 'minor': return 'severity-minor';
    case 'none known': return 'severity-none';
    default: return 'severity-unknown';
  }
};
