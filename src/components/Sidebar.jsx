import { useState } from 'react';

export default function Sidebar({ t }) {
  const [active] = useState('productManagement');

  const menuItems = [
    { key: 'dashboard', icon: '⊞', label: t.dashboard },
    { key: 'productManagement', icon: '⟳', label: t.productManagement },
    { key: 'inventory', icon: '☰', label: t.inventory },
    { key: 'orders', icon: '☰', label: t.orders },
    { key: 'settings', icon: '⚙', label: t.settings },
  ];

  return (
    <div className="sidebar">
      <div className="sidebar-logo">
        <span className="logo-text">ERP</span>
      </div>
      <nav className="sidebar-nav">
        {menuItems.map((item) => (
          <div
            key={item.key}
            className={`nav-item ${active === item.key ? 'active' : ''}`}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
          </div>
        ))}
      </nav>
      <div className="sidebar-footer">
        <div className="nav-item">
          <span className="nav-icon">⏻</span>
          <span className="nav-label">{t.logout}</span>
        </div>
      </div>
    </div>
  );
}
