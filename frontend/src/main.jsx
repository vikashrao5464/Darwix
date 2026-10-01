import React from 'react';
import { createRoot } from 'react-dom/client';
import CallDemo from './pages/CallDemo';
import LiveInsights from './pages/LiveInsights';
import './style.css';

function App() {
  return <main>
    <nav><a href="/call">Call demo</a><a href="/live">Live insights</a></nav>
    {window.location.pathname === '/live' ? <LiveInsights /> : <CallDemo />}
  </main>;
}

createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>);
