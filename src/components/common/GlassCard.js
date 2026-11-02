import React from 'react';
import './GlassCard.css';

const GlassCard = ({ children, style, className = '', ...rest }) => {
  return (
    <div className={`glass-card ${className}`.trim()} style={style} {...rest}>
      {children}
    </div>
  );
};

export default GlassCard;
