import React from 'react';
import { NavLink } from 'react-router-dom';
import './Navbar.css';

function Navbar() {
  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <NavLink to="/">BioGPT-DI</NavLink>
      </div>
      <ul className="navbar-links">
        <li><NavLink to="/" className={({ isActive }) => (isActive? 'active' : '')}>Home</NavLink></li>
        <li><NavLink to="/analyzer" className={({ isActive }) => (isActive? 'active' : '')}>Analyzer</NavLink></li>
        <li><NavLink to="/about-project" className={({ isActive }) => (isActive? 'active' : '')}>About the Project</NavLink></li>
        <li><NavLink to="/about-group" className={({ isActive }) => (isActive? 'active' : '')}>About the Group</NavLink></li>
      </ul>
    </nav>
  );
}

export default Navbar;