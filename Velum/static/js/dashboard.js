/**
 * VELUM — Dashboard Analytics & Charts Controller
 * Gestiona el consumo de métricas, los 5 KPI y la renderización de 4 gráficos con Chart.js local.
 */

let currentPeriod = localStorage.getItem('velum_period') || 'todo';
let currentTheme = localStorage.getItem('velum_theme') || 'dark';

let chartTransactions = null;
let chartHourlyAnomalies = null;
let chartSeverity = null;
let chartPayment = null;
let chartRevision = null;

// Colores según tema
function getThemeColors() {
  const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
  return {
    text: isDark ? '#f0f4f8' : '#0f172a',
    muted: isDark ? '#64748b' : '#94a3b8',
    grid: isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)',
    cardBg: isDark ? '#182234' : '#ffffff',
  };
}

// 1. Verificación de Salud
async function checkSystemHealth() {
  const badge = document.getElementById('system-health-badge');
  const label = document.getElementById('system-health-text');
  try {
    const res = await fetch('/health');
    if (res.ok) {
      const data = await res.json();
      badge.className = 'status-badge';
      label.textContent = `Sistema operativo (${data.environment})`;
    } else {
      badge.className = 'status-badge offline';
      label.textContent = 'Degradado';
    }
  } catch (err) {
    badge.className = 'status-badge offline';
    label.textContent = 'Sin conexión';
  }
}

// 2. Formateo de números
function formatCOP(num) {
  const n = parseFloat(num) || 0;
  return '$ ' + n.toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// 3. Cargar estadísticas y actualizar KPIs + Gráficos
async function fetchDashboardStats(periodo = currentPeriod) {
  currentPeriod = periodo;
  try {
    const res = await fetch(`/api/dashboard/stats?periodo=${periodo}`);
    if (!res.ok) throw new Error('Error al obtener estadísticas');
    const data = await res.json();

    updateKPIs(data);
    renderCharts(data);
  } catch (err) {
    console.error('Error cargando estadísticas del dashboard:', err);
  }
}

function updateKPIs(data) {
  // 1. Total Transacciones
  document.getElementById('kpi-total-txns').textContent = data.by_status.total.toLocaleString();
  
  // Tendencia badge
  const trendEl = document.getElementById('kpi-trend-badge');
  if (data.tendencia !== null && data.tendencia !== undefined) {
    const isUp = data.tendencia >= 0;
    trendEl.className = `badge-trend ${isUp ? 'up' : 'down'}`;
    trendEl.textContent = `${isUp ? '+' : ''}${data.tendencia}% vs periodo anterior`;
  } else {
    trendEl.className = 'badge-trend';
    trendEl.textContent = 'Sin histórico previo';
  }

  // 2. Anomalías detectadas
  document.getElementById('kpi-total-anomalies').textContent = data.anomalias.total.toLocaleString();

  // 3. Tasa de anomalías
  document.getElementById('kpi-anomaly-rate').textContent = `${data.anomalias.porcentaje}%`;

  // 4. Monto en riesgo
  document.getElementById('kpi-risk-amount').textContent = formatCOP(data.anomalias.monto_sospechoso);

  // 5. Usuarios recurrentes
  document.getElementById('kpi-recurring-users').textContent = data.anomalias.recurrentes.toLocaleString();

  // 6. Promedio de transacciones
  const avgTxnsEl = document.getElementById('kpi-avg-txns');
  if (avgTxnsEl) {
    avgTxnsEl.textContent = data.promedio_txns_usuario.toFixed(2);
  }
}

function renderCharts(data) {
  const colors = getThemeColors();

  const hoursLabels = data.by_hour.map(h => `${String(h.hora).padStart(2, '0')}:00`);
  const txnsByHour = data.by_hour.map(h => h.transacciones);
  const anomaliesByHour = data.by_hour.map(h => h.anomalias);

  // Gráfico 1: Línea - Transacciones vs Anomalías por Hora
  const ctxTxns = document.getElementById('chart-transactions-hourly').getContext('2d');
  if (chartTransactions) chartTransactions.destroy();
  chartTransactions = new Chart(ctxTxns, {
    type: 'line',
    data: {
      labels: hoursLabels,
      datasets: [
        {
          label: 'Total Transacciones',
          data: txnsByHour,
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59, 130, 246, 0.15)',
          fill: true,
          tension: 0.35,
          pointRadius: 3,
        },
        {
          label: 'Anomalías (Posible Fraude)',
          data: anomaliesByHour,
          borderColor: '#ef4444',
          backgroundColor: 'rgba(239, 68, 68, 0.2)',
          fill: true,
          tension: 0.35,
          pointRadius: 4,
          pointBackgroundColor: '#ef4444',
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: colors.text, font: { size: 11 } } },
      },
      scales: {
        x: { grid: { color: colors.grid }, ticks: { color: colors.muted, font: { size: 10 } } },
        y: { grid: { color: colors.grid }, ticks: { color: colors.muted, precision: 0 } },
      }
    }
  });

  // Gráfico 2: Barras - Anomalías por hora con pico resaltado
  const ctxHourly = document.getElementById('chart-hourly-anomalies').getContext('2d');
  const barColors = anomaliesByHour.map((val, idx) => {
    return (data.pico_hora !== null && idx === data.pico_hora && val > 0)
      ? '#dc2626'
      : '#f59e0b';
  });

  if (chartHourlyAnomalies) chartHourlyAnomalies.destroy();
  chartHourlyAnomalies = new Chart(ctxHourly, {
    type: 'bar',
    data: {
      labels: hoursLabels,
      datasets: [{
        label: 'Anomalías detectadas',
        data: anomaliesByHour,
        backgroundColor: barColors,
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            afterLabel: (ctx) => (data.pico_hora !== null && ctx.dataIndex === data.pico_hora) ? '⚡ Hora Pico Detectada' : ''
          }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: colors.muted, font: { size: 10 } } },
        y: { grid: { color: colors.grid }, ticks: { color: colors.muted, precision: 0 } },
      }
    }
  });

  // Gráfico 3: Dona - Severidad
  const ctxSeverity = document.getElementById('chart-severity').getContext('2d');
  if (chartSeverity) chartSeverity.destroy();
  chartSeverity = new Chart(ctxSeverity, {
    type: 'doughnut',
    data: {
      labels: ['Bajo', 'Medio', 'Alto', 'Crítico'],
      datasets: [{
        data: [
          data.by_severity.bajo,
          data.by_severity.medio,
          data.by_severity.alto,
          data.by_severity.critico,
        ],
        backgroundColor: ['#10b981', '#f59e0b', '#f97316', '#dc2626'],
        borderWidth: 2,
        borderColor: colors.cardBg,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: colors.text, boxWidth: 12 } }
      },
      cutout: '70%',
    }
  });

  // Gráfico 4: Dona - Métodos de Pago
  const ctxPayment = document.getElementById('chart-payment-method').getContext('2d');
  if (chartPayment) chartPayment.destroy();
  chartPayment = new Chart(ctxPayment, {
    type: 'doughnut',
    data: {
      labels: ['Tarjeta', 'PSE', 'Transferencia', 'Otro'],
      datasets: [{
        data: [
          data.by_payment_method.tarjeta,
          data.by_payment_method.pse,
          data.by_payment_method.transferencia,
          data.by_payment_method.otro,
        ],
        backgroundColor: ['#3b82f6', '#06b6d4', '#8b5cf6', '#64748b'],
        borderWidth: 2,
        borderColor: colors.cardBg,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: colors.text, boxWidth: 12 } }
      },
      cutout: '70%',
    }
  });

  // Gráfico 5: Dona - Estado de Revisión
  const canvasRevision = document.getElementById('chart-revision-status');
  if (canvasRevision) {
    const ctxRevision = canvasRevision.getContext('2d');
    if (chartRevision) chartRevision.destroy();
    chartRevision = new Chart(ctxRevision, {
      type: 'doughnut',
      data: {
        labels: ['Nuevas', 'Abiertas', 'Revisadas', 'Descartadas'],
        datasets: [{
          data: [
            data.by_revision.nueva,
            data.by_revision.abierta,
            data.by_revision.revisada,
            data.by_revision.descartada,
          ],
          backgroundColor: ['#ef4444', '#f59e0b', '#10b981', '#64748b'],
          borderWidth: 2,
          borderColor: colors.cardBg,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'bottom', labels: { color: colors.text, boxWidth: 12 } }
        },
        cutout: '70%',
      }
    });
  }
}

// 4. Gestión de Tema y Periodo
function initTheme() {
  document.documentElement.setAttribute('data-theme', currentTheme);
  const themeBtn = document.getElementById('btn-toggle-theme');
  if (themeBtn) {
    themeBtn.textContent = currentTheme === 'light' ? '🌙' : '☀️';
    themeBtn.addEventListener('click', () => {
      currentTheme = currentTheme === 'light' ? 'dark' : 'light';
      document.documentElement.setAttribute('data-theme', currentTheme);
      localStorage.setItem('velum_theme', currentTheme);
      themeBtn.textContent = currentTheme === 'light' ? '🌙' : '☀️';
      if (chartTransactions) fetchDashboardStats(currentPeriod);
    });
  }
}

function initPeriodSelector() {
  const buttons = document.querySelectorAll('.app-header .period-btn, [data-period]');
  buttons.forEach(btn => {
    const p = btn.getAttribute('data-period');
    if (!p) return;
    if (p === currentPeriod) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const newP = btn.getAttribute('data-period');
      if (!newP) return;
      currentPeriod = newP;
      localStorage.setItem('velum_period', newP);
      fetchDashboardStats(newP);
      loadUsersHistory();
      syncLiveTransactionsLog();
    });
  });
}

// 5. Historial y Directorio de Usuarios
let cachedUsersDirectory = [];

async function loadUsersHistory(highlightEmail = null) {
  const tbody = document.getElementById('users-directory-tbody');
  if (!tbody) return;

  try {
    const res = await fetch(`/api/dashboard/users-directory?periodo=${currentPeriod}`);
    if (!res.ok) throw new Error('Error al cargar directorio de usuarios');
    const data = await res.json();
    cachedUsersDirectory = data.users || [];
    renderUsersTable(cachedUsersDirectory, highlightEmail);
  } catch (err) {
    console.error('Error cargando historial de usuarios:', err);
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: var(--text-muted); padding: 18px;">Error al cargar directorio de usuarios</td></tr>`;
  }
}

function renderUsersTable(users, highlightEmail = null) {
  const tbody = document.getElementById('users-directory-tbody');
  const countEl = document.getElementById('users-directory-count');
  if (!tbody) return;

  if (countEl) {
    const pLabel = currentPeriod === 'hoy' ? 'HOY' : (currentPeriod === 'semana' ? 'ÚLTIMOS 7 DÍAS' : (currentPeriod === 'mes' ? 'ÚLTIMOS 30 DÍAS' : 'HISTÓRICO COMPLETO'));
    countEl.innerHTML = `<strong>${users.length}</strong> usuarios monitoreados · Métricas del periodo: <span style="color:#38bdf8; font-weight:700;">${pLabel}</span>`;
  }

  if (users.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: var(--text-muted); padding: 20px;">No se encontraron usuarios en este periodo</td></tr>`;
    return;
  }

  tbody.innerHTML = users.map(u => {
    let riskBadgeClass = 'badge-risk-bajo';
    if (u.riesgo === 'CRITICO') riskBadgeClass = 'badge-risk-critico';
    else if (u.riesgo === 'ALTO') riskBadgeClass = 'badge-risk-alto';
    else if (u.riesgo === 'MEDIO') riskBadgeClass = 'badge-risk-medio';

    const statusBadgeClass = u.estado === 'ACTIVO' ? 'badge-trend up' : 'badge-trend down';
    const isHighlighted = (highlightEmail && u.email.toLowerCase() === highlightEmail.toLowerCase());
    const rowClass = isHighlighted ? 'row-updated-flash' : '';

    return `
      <tr class="${rowClass}">
        <td style="font-family: var(--font-mono); font-weight: 700; color: var(--text-muted);">#${u.id}</td>
        <td>
          <div style="font-weight: 700; display:flex; align-items:center; gap:6px;">
            ${u.email}
            ${isHighlighted ? '<span class="badge-risk badge-risk-critico" style="font-size:9px;">ACTUALIZADO</span>' : ''}
          </div>
          <div style="font-size: 11px; color: var(--text-secondary);">${u.nombre}</div>
        </td>
        <td><span class="${statusBadgeClass}">${u.estado}</span></td>
        <td><span class="badge-risk ${riskBadgeClass}">● ${u.riesgo}</span></td>
        <td>
          <div style="font-family: var(--font-mono); font-weight: 700;">${u.total_transacciones}</div>
          <div style="font-size: 10px; color: var(--text-muted);">${u.historico_total_txns} total</div>
        </td>
        <td style="font-family: var(--font-mono); font-weight: 700; color: ${u.total_anomalias > 0 ? 'var(--status-critical)' : 'var(--text-secondary)'};">
          ${u.total_anomalias}
        </td>
        <td style="font-family: var(--font-mono); font-weight: 700;">$ ${parseFloat(u.monto_total).toLocaleString('es-CO', { minimumFractionDigits: 2 })}</td>
        <td>
          <button class="btn-inspect-window" onclick="inspectUserWindow(${u.id}, '${u.email}')">
            🔍 Ver Ventana
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

function initUserSearch() {
  const searchInput = document.getElementById('user-search-input');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase().trim();
      const filtered = cachedUsersDirectory.filter(u => 
        u.email.toLowerCase().includes(q) || 
        u.nombre.toLowerCase().includes(q) ||
        u.estado.toLowerCase().includes(q) ||
        u.riesgo.toLowerCase().includes(q)
      );
      renderUsersTable(filtered);
    });
  }
}

window.inspectUserWindow = (userId, email) => {
  const targetBtn = document.querySelector(`.user-quick-btn[data-email="${email}"]`);
  if (targetBtn) {
    targetBtn.click();
  } else if (window.loadTimeline) {
    window.loadTimeline(userId, email);
  }
  const vizSection = document.querySelector('.visualizer-card');
  if (vizSection) {
    vizSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
};

// 6. Sincronización en vivo del Terminal y Tabla de Auditoría
let seenTxnIds = new Set();
let cachedLiveTxns = [];
let currentTxFilter = 'all';
let currentTxSearch = '';

function initTxFilters() {
  document.querySelectorAll('[data-tx-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-tx-filter]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentTxFilter = btn.getAttribute('data-tx-filter');
      renderLiveTxnsTable();
    });
  });

  const searchInput = document.getElementById('live-txns-search');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      currentTxSearch = e.target.value.trim();
      renderLiveTxnsTable();
    });
  }
}

function renderLiveTxnsTable() {
  const tbody = document.getElementById('live-txns-tbody');
  const subtitle = document.getElementById('live-txns-subtitle');
  if (!tbody) return;

  const totalFrauds = cachedLiveTxns.filter(t => t.isAnomaly || t.status === 'SOSPECHOSA').length;
  const totalApproved = cachedLiveTxns.filter(t => t.status === 'APROBADA').length;

  const btnAll = document.getElementById('btn-tx-all');
  const btnFraud = document.getElementById('btn-tx-fraud');
  const btnApp = document.getElementById('btn-tx-approved');
  if (btnAll) btnAll.textContent = `Todas (${cachedLiveTxns.length})`;
  if (btnFraud) btnFraud.textContent = `🚨 Solo Fraude (${totalFrauds})`;
  if (btnApp) btnApp.textContent = `✅ Aprobadas (${totalApproved})`;

  let filtered = cachedLiveTxns.filter(t => {
    const isFraud = t.isAnomaly || t.status === 'SOSPECHOSA';
    if (currentTxFilter === 'fraud' && !isFraud) return false;
    if (currentTxFilter === 'approved' && isFraud) return false;
    if (currentTxSearch) {
      const q = currentTxSearch.toLowerCase();
      return (t.idTxn && t.idTxn.toLowerCase().includes(q)) || 
             (t.user && t.user.toLowerCase().includes(q)) || 
             (t.paymentMethod && t.paymentMethod.toLowerCase().includes(q));
    }
    return true;
  });

  if (subtitle) {
    const pLabel = currentPeriod === 'hoy' ? 'HOY' : (currentPeriod === 'semana' ? 'ÚLTIMOS 7 DÍAS' : (currentPeriod === 'mes' ? 'ÚLTIMOS 30 DÍAS' : 'HISTÓRICO COMPLETO'));
    subtitle.innerHTML = `Filtro periodo: <strong style="color:#38bdf8;">${pLabel}</strong> · Mostrando <strong>${filtered.length}</strong> de <strong>${cachedLiveTxns.length}</strong> transacciones · 🚨 <span style="color:#f87171; font-weight:700;">${totalFrauds} intentos de fraude detectados</span>`;
  }

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color: var(--text-muted); padding: 20px;">No hay transacciones registradas que coincidan con el filtro</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(t => {
    const isFraud = t.isAnomaly || t.status === 'SOSPECHOSA';
    const statusBadge = isFraud 
      ? '<span class="badge-risk badge-risk-critico">SOSPECHOSA</span>' 
      : '<span class="badge-trend up">APROBADA</span>';
    
    let diagBadge = '';
    if (isFraud) {
      diagBadge = `<span style="color:#f87171; font-weight:700; display:flex; align-items:center; gap:4px;">🚨 POSIBLE FRAUDE <small style="color:var(--text-muted)">(${t.burst || 'Ráfaga <3s'})</small></span>`;
    } else {
      diagBadge = `<span style="color:#4ade80;">✅ Normal</span>`;
    }

    let sevBadge = '<span style="color:var(--text-muted)">-</span>';
    if (t.severity === 'CRITICO') sevBadge = '<span class="badge-risk badge-risk-critico">CRÍTICO</span>';
    else if (t.severity === 'ALTO') sevBadge = '<span class="badge-risk badge-risk-alto">ALTO</span>';
    else if (t.severity === 'MEDIO') sevBadge = '<span class="badge-risk badge-risk-medio">MEDIO</span>';
    else if (t.severity === 'BAJO') sevBadge = '<span class="badge-risk badge-risk-bajo">BAJO</span>';

    const timeStr = t.date ? (t.date.length >= 19 ? t.date.replace('T', ' ').substring(11, 23) : t.date) : 'N/A';
    const valFmt = parseFloat(t.value).toLocaleString('es-CO', { minimumFractionDigits: 2 });
    const rowClass = isFraud ? 'row-updated-flash' : '';

    return `
      <tr class="${rowClass}">
        <td style="font-family: var(--font-mono); font-size: 12px; color: var(--text-secondary);">${timeStr}</td>
        <td style="font-family: var(--font-mono); font-weight: 700; color: #38bdf8;">${t.idTxn}</td>
        <td>
          <div style="font-weight: 600;">${t.user}</div>
        </td>
        <td style="font-family: var(--font-mono); font-weight: 700;">$ ${valFmt}</td>
        <td><span class="tag">${t.paymentMethod}</span></td>
        <td>${statusBadge}</td>
        <td>${diagBadge}</td>
        <td>${sevBadge}</td>
      </tr>
    `;
  }).join('');
}

async function syncLiveTransactionsLog() {
  const terminal = document.getElementById('sim-log-terminal');

  try {
    const pParam = (currentPeriod && currentPeriod !== 'todo' && currentPeriod !== 'todos') ? `&periodo=${encodeURIComponent(currentPeriod)}` : '';
    const res = await fetch(`/api/transacciones?limit=250${pParam}`);
    if (!res.ok) return;
    const data = await res.json();
    const txns = data.transactions || [];
    cachedLiveTxns = txns;

    renderLiveTxnsTable();

    if (!terminal) return;

    if (txns.length === 0) {
      if (seenTxnIds.size > 0) {
        seenTxnIds.clear();
        terminal.innerHTML = `
          <div class="log-entry">
            <span class="log-time">[Sistema]</span>
            <span class="log-status approved">Terminal listo. Sin transacciones pendientes.</span>
          </div>
        `;
      }
      return;
    }

    if (seenTxnIds.size === 0) {
      terminal.innerHTML = '';
      for (const t of txns.slice().reverse()) {
        seenTxnIds.add(t.idTxn);
        appendTxnToTerminal(t, terminal);
      }
      return;
    }

    const newTxns = txns.filter(t => !seenTxnIds.has(t.idTxn));
    for (const t of newTxns.reverse()) {
      seenTxnIds.add(t.idTxn);
      appendTxnToTerminal(t, terminal);
    }
  } catch (err) {
    console.error('Error sincronizando telemetría en vivo:', err);
  }
}

function appendTxnToTerminal(t, terminal) {
  const timeStr = t.date ? (t.date.length >= 19 ? t.date.substring(11, 23) : t.date) : new Date().toLocaleTimeString();
  const isSuspicious = t.status === 'SOSPECHOSA';
  const statusClass = isSuspicious ? 'suspicious' : 'approved';
  const icon = isSuspicious ? '🚨 FRAUDE' : '✅ OK';
  const valFmt = parseFloat(t.value).toLocaleString('es-CO', { minimumFractionDigits: 2 });

  const entry = document.createElement('div');
  entry.className = 'log-entry';
  entry.innerHTML = `
    <span class="log-time">[${timeStr}]</span>
    <span class="log-status ${statusClass}">
      ${icon} | <strong>${t.idTxn}</strong> | ${t.user} | $${valFmt} | ${t.status} (${t.paymentMethod})
    </span>
  `;
  terminal.prepend(entry);

  while (terminal.children.length > 250) {
    terminal.removeChild(terminal.lastChild);
  }
}

// Inicialización global
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initPeriodSelector();
  initUserSearch();
  initTxFilters();
  checkSystemHealth();
  fetchDashboardStats(currentPeriod);
  loadUsersHistory();
  syncLiveTransactionsLog();

  // Actualizar salud cada 30 segundos
  setInterval(checkSystemHealth, 30000);

  // Botón Reiniciar Datos
  const btnReset = document.getElementById('btn-reset-data');
  if (btnReset) {
    btnReset.addEventListener('click', async () => {
      if (!confirm('¿Estás seguro de que deseas eliminar todas las transacciones, anomalías y vaciar la memoria del detector? Esta acción no se puede deshacer.')) return;
      
      const originalText = btnReset.textContent;
      btnReset.textContent = 'Borrando...';
      btnReset.disabled = true;
      
      try {
        const res = await fetch('/api/dashboard/reset', { method: 'POST' });
        if (!res.ok) throw new Error('Error al reiniciar datos');
        
        // Limpiar terminal
        const terminal = document.getElementById('sim-log-terminal');
        if (terminal) terminal.innerHTML = '';
        if (typeof seenTxnIds !== 'undefined') seenTxnIds.clear();
        
        // Forzar refresco global
        window.refreshDashboard();
        if (window.refreshSlidingWindow) window.refreshSlidingWindow();
      } catch (e) {
        console.error(e);
        alert('Error al reiniciar los datos.');
      } finally {
        btnReset.textContent = originalText;
        btnReset.disabled = false;
      }
    });
  }

  // Auto-refresco en vivo cada 2.5 segundos (Telemetría + Tabla Auditoría + KPIs + Directorio)
  setInterval(() => {
    syncLiveTransactionsLog();
    fetchDashboardStats(currentPeriod);
    loadUsersHistory();
  }, 2500);
});

window.refreshDashboard = () => {
  fetchDashboardStats(currentPeriod);
  loadUsersHistory();
  syncLiveTransactionsLog();
};
window.loadUsersHistory = loadUsersHistory;
