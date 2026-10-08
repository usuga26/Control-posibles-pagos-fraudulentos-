/**
 * VELUM — Sliding Window Visualizer v3
 * Nodos alternados arriba/abajo. Posicionamiento por índice (nunca solapan).
 * Tooltip único global controlado por JS.
 * Selector de usuarios con scroll horizontal silencioso.
 */

let activeUserEmail = null;

/* ─────────────────────────────────────────────────────────────
   TOOLTIP GLOBAL ÚNICO — un solo elemento en el <body>
   JS lo posiciona y rellena. Solo uno activo a la vez.
   ───────────────────────────────────────────────────────────── */
function ensureGlobalTooltip() {
  if (document.getElementById('timeline-tooltip')) return;
  const tt = document.createElement('div');
  tt.id = 'timeline-tooltip';
  tt.innerHTML = `
    <div class="tooltip-inner">
      <div class="tt-header">TRANSACCIÓN</div>
      <div class="tt-id" id="tt-id">—</div>
      <div class="tt-row"><span class="tt-label">Hora</span><span class="tt-value" id="tt-time">—</span></div>
      <div class="tt-row"><span class="tt-label">Monto</span><span class="tt-value" id="tt-monto">—</span></div>
      <div class="tt-row"><span class="tt-label">Estado</span><span class="tt-value" id="tt-estado">—</span></div>
      <div class="tt-row"><span class="tt-label">Ventana</span><span class="tt-value" id="tt-conteo">—</span></div>
      <div class="tt-row" id="tt-row-sev" style="display:none"><span class="tt-label">Severidad</span><span class="tt-value" id="tt-severidad">—</span></div>
      <div class="tt-rule" id="tt-rule" style="display:none"></div>
    </div>
    <div class="tooltip-arrow" id="tt-arrow"></div>
  `;
  document.body.appendChild(tt);
}

function showTooltip(dot, data) {
  var tt = document.getElementById('timeline-tooltip');
  if (!tt) return;

  var isSusp     = data.estado === 'SOSPECHOSA';
  var colorEstado= isSusp ? '#f87171' : '#34d399';
  var colorSev   = data.severidad === 'CRITICO' ? '#f87171'
                 : data.severidad === 'ALTO'    ? '#fb923c'
                 : data.severidad === 'MEDIO'   ? '#facc15'
                 : '#94a3b8';

  document.getElementById('tt-id').textContent    = data.idTxn;
  document.getElementById('tt-time').textContent  = data.timestamp.split('T')[1].substring(0, 12);
  document.getElementById('tt-monto').textContent = '$' + Number(data.valor).toLocaleString('es-CO');

  var elEstado = document.getElementById('tt-estado');
  elEstado.textContent = data.estado;
  elEstado.style.color = colorEstado;

  document.getElementById('tt-conteo').textContent = data.conteoVentana + ' txns';

  var rowSev = document.getElementById('tt-row-sev');
  var elSev  = document.getElementById('tt-severidad');
  if (data.severidad) {
    rowSev.style.display = 'flex';
    elSev.textContent    = data.severidad;
    elSev.style.color    = colorSev;
  } else {
    rowSev.style.display = 'none';
  }

  var elRule = document.getElementById('tt-rule');
  if (data.reglaDetectada) {
    elRule.style.display = 'block';
    elRule.textContent   = data.reglaDetectada;
  } else {
    elRule.style.display = 'none';
  }

  tt.classList.add('visible');
  positionTooltip(dot, data.isAbove);
}

function positionTooltip(dot, isAbove) {
  var tt    = document.getElementById('timeline-tooltip');
  var arrow = document.getElementById('tt-arrow');
  if (!tt || !dot) return;

  var rect       = dot.getBoundingClientRect();
  var ttW        = tt.offsetWidth  || 240;
  var ttH        = tt.offsetHeight || 170;
  var gap        = 12;
  var arrowH     = 7;
  var centerX    = rect.left + rect.width / 2;
  var top;

  if (isAbove) {
    /* Nodo arriba del eje → tooltip aparece encima del label (más arriba aún) */
    top = rect.top - ttH - arrowH - gap;
    if (top < 10) {
      top = rect.bottom + arrowH + gap;
      arrow.classList.add('arrow-up');
      arrow.style.top = '-14px';
      arrow.style.bottom = 'auto';
    } else {
      arrow.classList.remove('arrow-up');
      arrow.style.bottom = '-14px';
      arrow.style.top    = 'auto';
    }
  } else {
    /* Nodo abajo del eje → tooltip aparece debajo del label */
    top = rect.bottom + arrowH + gap;
    if (top + ttH > window.innerHeight - 10) {
      top = rect.top - ttH - arrowH - gap;
      arrow.classList.remove('arrow-up');
      arrow.style.bottom = '-14px';
      arrow.style.top    = 'auto';
    } else {
      arrow.classList.add('arrow-up');
      arrow.style.top    = '-14px';
      arrow.style.bottom = 'auto';
    }
  }

  var left = Math.max(8, Math.min(centerX - ttW / 2, window.innerWidth - ttW - 8));
  tt.style.top  = top  + 'px';
  tt.style.left = left + 'px';

  /* Ajustar flecha para apuntar exactamente al dot */
  var arrowLeft = Math.max(10, Math.min(centerX - left - 7, ttW - 24));
  arrow.style.position   = 'absolute';
  arrow.style.marginLeft = '0';
  arrow.style.left       = arrowLeft + 'px';
}

function hideTooltip() {
  var tt = document.getElementById('timeline-tooltip');
  if (tt) tt.classList.remove('visible');
}

/* ─────────────────────────────────────────────────────────────
   CARGA DE DATOS
   ───────────────────────────────────────────────────────────── */
async function loadUserTimeline(email) {
  email = email || activeUserEmail;
  var trackEl = document.getElementById('timeline-track');
  
  if (!email) {
    if (trackEl) trackEl.innerHTML = emptyMsg('No hay usuarios monitoreados. Envía transacciones para generar la visualización.');
    return;
  }
  
  activeUserEmail = email;

  document.querySelectorAll('.user-quick-btn').forEach(function(btn) {
    btn.classList.toggle('active',
      btn.getAttribute('data-email').toLowerCase() === email.toLowerCase());
  });

  try {
    var res = await fetch('/api/dashboard/timeline-sliding-window/' + encodeURIComponent(email));
    if (!res.ok) {
      trackEl.innerHTML = emptyMsg(
        res.status === 404
          ? 'Sin transacciones para <strong>' + email + '</strong>.'
          : 'Error HTTP ' + res.status
      );
      return;
    }
    var data = await res.json();
    if (!data.entries || data.entries.length === 0) {
      trackEl.innerHTML = emptyMsg('Sin transacciones para <strong>' + email + '</strong>.');
      return;
    }
    renderTimelineNodes(data.entries, trackEl);
  } catch (err) {
    console.error('Error cargando timeline:', err);
    trackEl.innerHTML = emptyMsg('Error de conexión.', 'var(--status-rejected)');
  }
}

function emptyMsg(msg, color) {
  return '<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);'
       + 'color:' + (color || 'var(--text-muted)') + ';font-size:13px;text-align:center;">'
       + msg + '</div>';
}

/* ─────────────────────────────────────────────────────────────
   RENDERIZADO — NODOS ALTERNADOS, POSICIÓN POR ÍNDICE
   ───────────────────────────────────────────────────────────── */
function renderTimelineNodes(entries, container) {
  if (!entries || entries.length === 0) {
    container.innerHTML = emptyMsg('Sin transacciones.');
    return;
  }

  /* 6 entradas → ~130px de separación mínima garantizada en 900px de track */
  var visible = entries.slice(-6);
  var n       = visible.length;

  /* Calcular sombreado de ventana por tiempo (cosmético) */
  var tFirst = new Date(visible[0].timestamp).getTime();
  var tLast  = new Date(visible[n - 1].timestamp).getTime();
  var tSpan  = (tLast - tFirst) || 3000;
  var wStart = tLast - 3000;
  var pctS   = Math.max(2,  Math.min(93, ((wStart - tFirst) / tSpan) * 78 + 10));
  var pctE   = Math.max(7,  Math.min(97, ((tLast  - tFirst) / tSpan) * 78 + 10));
  var wWidth = Math.max(10, pctE - pctS);

  var html = '<div class="timeline-axis"></div>'
    + '<div class="timeline-window-shade" style="left:' + pctS + '%;width:' + wWidth + '%;">'
    + '<span class="timeline-window-tag">VENTANA [t−3s, t]</span></div>';

  visible.forEach(function(entry, idx) {
    /*
      POSICIÓN POR ÍNDICE — espaciado uniforme garantizado.
      Aunque 6 transacciones ocurran en 100ms, los nodos quedan
      distribuidos visualmente de forma legible.
      El timestamp real está en la etiqueta y en el tooltip.
    */
    var posPct = n === 1 ? 50 : (idx / (n - 1)) * 78 + 10;

    var isSusp  = entry.estado === 'SOSPECHOSA';
    var isAbove = (idx % 2 === 0);   /* par=ARRIBA, impar=ABAJO */
    var dotCls  = isSusp ? 'suspicious' : '';
    var timeL   = entry.timestamp.split('T')[1].substring(0, 8);
    var shortId = entry.idTxn.length > 9
      ? entry.idTxn.substring(0, 9) + '\u2026'
      : entry.idTxn;
    var labelColor  = isSusp ? 'var(--status-critical)' : 'var(--text-muted)';
    var labelWeight = isSusp ? '700' : '400';

    /* Dot con datos embebidos como atributos data-* */
    var dotHtml = '<div class="node-dot ' + dotCls + '"'
      + ' data-id="'       + entry.idTxn                + '"'
      + ' data-valor="'    + entry.valor                 + '"'
      + ' data-estado="'   + entry.estado                + '"'
      + ' data-conteo="'   + entry.conteoVentana         + '"'
      + ' data-severidad="'+ (entry.severidad        || '') + '"'
      + ' data-regla="'    + (entry.reglaDetectada   || '') + '"'
      + ' data-ts="'       + entry.timestamp             + '"'
      + ' data-above="'    + isAbove                     + '"'
      + '></div>';

    /* Etiqueta: hora + ID corto */
    var labelHtml = '<div class="node-label" style="color:' + labelColor
      + ';font-weight:' + labelWeight + ';">' + timeL + '<br>' + shortId + '</div>';

    var stemHtml = '<div class="node-stem"></div>';

    if (isAbove) {
      /*
        node-above: orden DOM → [label, stem, dot]
        CSS: translateX(-50%) translateY(-100%)
        → El nodo SUBE completamente. El DOT (último hijo) queda
          exactamente en top:180px (el eje). El LABEL queda arriba.
      */
      html += '<div class="timeline-node node-above" style="left:' + posPct + '%;">'
        + labelHtml + stemHtml + dotHtml + '</div>';
    } else {
      /*
        node-below: orden DOM → [dot, stem, label]
        CSS: translateX(-50%) translateY(0)
        → El nodo empieza en top:180px. El DOT (primer hijo) queda
          en el eje. El LABEL cuelga hacia abajo.
      */
      html += '<div class="timeline-node node-below" style="left:' + posPct + '%;">'
        + dotHtml + stemHtml + labelHtml + '</div>';
    }
  });

  container.innerHTML = html;

  /* Vincular tooltip a cada dot */
  container.querySelectorAll('.node-dot').forEach(function(dot) {
    dot.addEventListener('mouseenter', function() {
      showTooltip(dot, {
        idTxn:          dot.dataset.id,
        valor:          dot.dataset.valor,
        estado:         dot.dataset.estado,
        conteoVentana:  dot.dataset.conteo,
        severidad:      dot.dataset.severidad  || null,
        reglaDetectada: dot.dataset.regla      || null,
        timestamp:      dot.dataset.ts,
        isAbove:        dot.dataset.above === 'true',
      });
    });
    dot.addEventListener('mouseleave', hideTooltip);
    dot.addEventListener('mousemove', function() {
      positionTooltip(dot, dot.dataset.above === 'true');
    });
  });
}

/* ─────────────────────────────────────────────────────────────
   INICIALIZACIÓN DEL SELECTOR DE USUARIOS
   La etiqueta "Usuario activo:" va FUERA del contenedor
   scrollable para que no desaparezca al hacer scroll horizontal.
   ───────────────────────────────────────────────────────────── */
async function initSlidingWindowControls() {
  var container = document.querySelector('.user-selector-group');
  if (!container) return;

  var displayUsers = [];

  try {
    var res = await fetch('/api/dashboard/users-directory?periodo=todos');
    if (res.ok) {
      var data  = await res.json();
      var users = data.users || [];
      users.forEach(function(u) {
        if (!displayUsers.some(function(b) {
          return b.email.toLowerCase() === u.email.toLowerCase();
        })) {
          displayUsers.push({ email: u.email, label: u.email });
        }
      });
      
      if (displayUsers.length > 0) {
        if (!activeUserEmail || !displayUsers.some(u => u.email.toLowerCase() === activeUserEmail.toLowerCase())) {
          activeUserEmail = displayUsers[0].email;
        }
      } else {
        activeUserEmail = null;
      }
    }
  } catch (e) {
    console.error('Error cargando usuarios para timeline:', e);
  }

  /*
    Insertar el span "Usuario activo:" ANTES del contenedor scrollable.
    Si ya existe (de una llamada anterior), reutilizarlo.
  */
  var labelEl = container.previousElementSibling;
  if (!labelEl || !labelEl.classList.contains('user-selector-label')) {
    labelEl = document.createElement('span');
    labelEl.className   = 'user-selector-label';
    labelEl.textContent = 'Usuario activo:';
    container.parentNode.insertBefore(labelEl, container);
  }

  /* Sólo botones dentro del contenedor scrollable */
  var btnsHtml = '';
  displayUsers.forEach(function(u) {
    var isActive = activeUserEmail && u.email.toLowerCase() === activeUserEmail.toLowerCase();
    var cls = 'user-quick-btn' + (isActive ? ' active' : '');
    btnsHtml += '<button class="' + cls + '" data-email="' + u.email + '">'
      + u.label + '</button>';
  });
  container.innerHTML = btnsHtml;

  container.querySelectorAll('.user-quick-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      loadUserTimeline(btn.getAttribute('data-email'));
    });
  });
}

/* ─────────────────────────────────────────────────────────────
   ARRANQUE
   ───────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', async function() {
  ensureGlobalTooltip();
  await initSlidingWindowControls();
  loadUserTimeline(activeUserEmail);

  /* Auto-refresco cada 3 segundos */
  setInterval(function() {
    if (activeUserEmail) loadUserTimeline(activeUserEmail);
  }, 3000);

  /* Controles de scroll de usuarios */
  document.getElementById('scroll-left-btn')?.addEventListener('click', function() {
    var container = document.querySelector('.user-selector-group');
    if (container) container.scrollBy({ left: -200, behavior: 'smooth' });
  });
  document.getElementById('scroll-right-btn')?.addEventListener('click', function() {
    var container = document.querySelector('.user-selector-group');
    if (container) container.scrollBy({ left: 200, behavior: 'smooth' });
  });
});

window.refreshSlidingWindow = async function() {
  await initSlidingWindowControls();
  loadUserTimeline(activeUserEmail); 
};
window.loadTimeline = function(userId, email) { loadUserTimeline(email); };
