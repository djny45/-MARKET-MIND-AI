/* MARKET-MIND-AI private dashboard renderer (read-only).
 *
 * Reads the snapshot published by scripts/jupyter_dashboard_bridge.py and paints
 * the dashboard. It never contacts a backend, never writes data, and never
 * places an order.
 *
 * The page is served from two places with different policies:
 *   Jupyter  /user/<n>/files/...  sandboxed frame, inline script allowed
 *   proxy    /market_mind_live.html  CSP `script-src 'self'` -> external JS only
 * So the snapshot ships as <script type="application/json"> (a data block, not
 * code, and unaffected by script-src) and this file holds all behaviour.
 */
(function () {
  'use strict';

  var DATA_ID = 'mm-snapshot';
  var REFRESH_MS = 60000;

  function readSnapshot() {
    var node = document.getElementById(DATA_ID);
    if (!node) return null;
    var raw = (node.textContent || '').trim();
    if (!raw) return null;
    try {
      var parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? parsed : null;
    } catch (e) {
      // Never surface raw payload or an exception message in the UI.
      return null;
    }
  }

  function num(n, d) {
    var v = Number(n);
    return (isFinite(v) ? v : 0).toFixed(d === undefined ? 2 : d);
  }

  function esc(s) {
    return String(s === null || s === undefined ? '' : s).replace(/[&<>"']/g, function (c) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c];
    });
  }

  function byId(id) {
    return document.getElementById(id);
  }

  function fill(sel, rows, cells) {
    var body = document.querySelector(sel + ' tbody');
    if (!body) return;
    if (!rows || !rows.length) {
      var cols = document.querySelectorAll(sel + ' thead th').length || 1;
      body.innerHTML = '<tr><td colspan="' + cols + '" style="color:#8093a8">(none)</td></tr>';
      return;
    }
    body.innerHTML = rows.map(function (r) {
      return '<tr>' + cells(r).map(function (c) { return '<td>' + c + '</td>'; }).join('') + '</tr>';
    }).join('');
  }

  function render(d) {
    var status = byId('status');
    if (!d) {
      if (status) status.textContent = 'snapshot unavailable';
      return false;
    }

    var ts = String(d.generated_at || '');
    if (status) {
      status.textContent = 'backend snapshot ' + (ts ? ts.slice(11, 19) + 'Z' : 'unknown');
    }

    var p = d.pnl || {};
    byId('kpi').innerHTML = [
      ['Agents', num(p.registered_agents, 0)],
      ['Active', num(p.active_agents_with_positions, 0)],
      ['Virtual capital', '$' + num(p.total_virtual_capital)],
      ['Equity', '$' + num(p.total_portfolio_value)],
      ['Realized P&L', '$' + num(p.realized_pnl)],
      ['Max drawdown', num(p.max_drawdown_pct) + '%']
    ].map(function (pair) {
      return '<div><b>' + pair[1] + '</b><span>' + pair[0] + '</span></div>';
    }).join('');

    byId('mktnote').textContent = d.market_data_status === 'available'
      ? 'STORED market observations with source provenance \u2014 not a live feed.'
      : 'NO VERIFIED LIVE FEED: no licensed live provider configured. '
        + 'No live prices are displayed.';

    fill('#mkt', d.market_prices, function (r) {
      return [esc(r.symbol), num(r.close, 4), esc(r.source || '-'),
              esc(r.status || '-'), esc(String(r.timestamp || '').slice(0, 19))];
    });
    fill('#pos', d.open_positions, function (r) {
      return [esc(r.agent_id), esc(r.symbol), num(r.quantity), num(r.avg_entry, 4),
              num(r.current_price, 4),
              r.stop_loss_pct === null || r.stop_loss_pct === undefined ? '-' : esc(r.stop_loss_pct),
              r.take_profit_pct === null || r.take_profit_pct === undefined ? '-' : esc(r.take_profit_pct)];
    });
    fill('#ord', d.virtual_orders, function (r) {
      var pnl = Number(r.pnl || 0);
      return [esc(String(r.executed_at || '').slice(11, 19)), esc(r.agent_id), esc(r.symbol),
              esc(r.side), num(r.quantity), num(r.price, 4),
              '<span class="' + (pnl >= 0 ? 'pos' : 'neg') + '">' + num(pnl) + '</span>'];
    });
    return true;
  }

  function start() {
    render(readSnapshot());
    // The bridge rewrites this page every 20s, but the snapshot only reaches the
    // browser on load, so reload periodically to pick it up. Deliberately slow:
    // a fast reload cycle would fight the reader on a phone.
    setTimeout(function () { location.reload(); }, REFRESH_MS);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
