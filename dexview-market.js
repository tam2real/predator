/**
 * DexView Market Mode — Standalone Module
 * Extracted from DexView (dex-view.html)
 * Provides: SVG candlestick chart factory, OHLCV fetching (CoinGecko/Binance/Yahoo), trade overlay rendering
 * Used by: Predator dashboard, Gaze dashboard
 */

const DexViewMarket = (function () {
  'use strict';

  // ========== CONSTANTS ==========
  const MARKET_PROVIDER = 'mothership_market_bridge';
  const MARKET_MOCK_PROVIDER = 'mock_local_preview';
  const MARKET_PROVIDER_LABEL = 'Live market bridge';
  const MARKET_MOCK_PROVIDER_LABEL = 'Mock/local preview fallback';
  const MARKET_BRIDGE_UNAVAILABLE_LABEL = 'Live bridge unavailable';
  const MARKET_PROVIDER_OFFLINE_FALLBACK_LABEL = 'Live bridge online / provider offline / mock fallback';
  const MARKET_LAST_GOOD_STORAGE_PREFIX = 'sage.market.lastGood';
  const MARKET_LAST_GOOD_PRICE_PREFIX = 'sage.market.lastGoodPrice';
  const MARKET_PROVIDER_RETRYING_LABEL = 'Provider retrying';

  const CG_DAYS = { '1m':'1','5m':'1','15m':'1','1H':'2','4H':'14','1D':'90' };
  const BINANCE_INT = { '1m':'1m','5m':'5m','15m':'15m','1H':'1h','4H':'4h','1D':'1d' };
  const BINANCE_LIM = { '1m':120,'5m':100,'15m':96,'1H':168,'4H':90,'1D':180 };
  const YAHOO_INT   = { '1m':'2m','5m':'5m','15m':'15m','1H':'60m','4H':'60m','1D':'1d' };
  const YAHOO_RNG   = { '1m':'1d','5m':'5d','15m':'1mo','1H':'3mo','4H':'6mo','1D':'2y' };

  const TOP_CRYPTO_SYMBOLS = {
    BTC:  { name:'Bitcoin', cg:'bitcoin', binance:'BTCUSDT', color:'#f7931a' },
    ETH:  { name:'Ethereum', cg:'ethereum', binance:'ETHUSDT', color:'#627eea' },
    SOL:  { name:'Solana', cg:'solana', binance:'SOLUSDT', color:'#9945ff' },
    XRP:  { name:'XRP', cg:'ripple', binance:'XRPUSDT', color:'#346aa9' },
    BCH:  { name:'Bitcoin Cash', cg:'bitcoin-cash', binance:'BCHUSDT', color:'#8dc351' },
    ZEC:  { name:'Zcash', cg:'zcash', binance:'ZECUSDT', color:'#f4b400' },
    HYPE: { name:'Hyperliquid', cg:'hyperliquid', color:'#00d7b5' },
    AIP:  { name:'AIP', cg:'aip', color:'#7dc4ff' },
    DOGE: { name:'Dogecoin', cg:'dogecoin', binance:'DOGEUSDT', color:'#c2a633' },
    AVAX: { name:'Avalanche', cg:'avalanche-2', binance:'AVAXUSDT', color:'#e84142' },
    SUI:  { name:'Sui', cg:'sui', binance:'SUIUSDT', color:'#6ec8ff' },
    NEAR: { name:'NEAR', cg:'near', binance:'NEARUSDT', color:'#9af15d' },
    TAO:  { name:'Bittensor', cg:'bittensor', binance:'TAOUSDT', color:'#7c3aed' },
    LINK: { name:'Chainlink', cg:'chainlink', binance:'LINKUSDT', color:'#375bd2' },
    ADA:  { name:'Cardano', cg:'cardano', binance:'ADAUSDT', color:'#0033ad' },
    MATIC:{ name:'Polygon', cg:'matic-network', binance:'MATICUSDT', color:'#8247e5' },
    BNB:  { name:'BNB', cg:'binancecoin', binance:'BNBUSDT', color:'#f3ba2f' },
  };

  // ========== UTILITIES ==========
  function normalizeAssetSymbol(raw) {
    return String(raw || '').trim().toUpperCase().replace(/[^A-Z0-9]/g, '');
  }

  function marketTimeframeKey(tf) {
    const raw = String(tf || '1H').trim();
    return raw.toLowerCase().endsWith('m')
      ? `${raw.slice(0, -1)}M`
      : raw.toUpperCase();
  }

  function marketCacheKey(assetId, tf) {
    return `${MARKET_LAST_GOOD_STORAGE_PREFIX}.${normalizeAssetSymbol(assetId)}.${marketTimeframeKey(tf)}`;
  }

  function marketPriceCacheKey(assetId) {
    return `${MARKET_LAST_GOOD_PRICE_PREFIX}.${normalizeAssetSymbol(assetId)}`;
  }

  function isValidRealCandles(data) {
    if (!Array.isArray(data) || data.length < 2) return false;
    const closes = data.map(point => Number(point?.close)).filter(Number.isFinite);
    if (closes.length < 2) return false;
    return Math.max(...closes) !== Math.min(...closes);
  }

  function formatMiniPrice(value) {
    const n = Number(value || 0);
    if (!Number.isFinite(n)) return '$-';
    if (n < 1) return `$${n.toFixed(4)}`;
    if (n < 100) return `$${n.toFixed(2)}`;
    return `$${n.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
  }

  function buildCryptoAsset(symbol) {
    const id = normalizeAssetSymbol(symbol);
    if (!id) return null;
    const meta = TOP_CRYPTO_SYMBOLS[id] || {};
    return {
      id,
      name: meta.name || id,
      source: 'crypto',
      symbol: meta.binance || `${id}USDT`,
      color: meta.color || '#4db6ff',
      cg: meta.cg || '',
    };
  }

  // ========== CACHE HELPERS ==========
  function readLastGoodCandles(assetId, tf) {
    try {
      const parsed = JSON.parse(localStorage.getItem(marketCacheKey(assetId, tf)) || 'null');
      if (!parsed || parsed.mock === true || !isValidRealCandles(parsed.candles)) return null;
      return parsed;
    } catch (_) {
      return null;
    }
  }

  function writeLastGoodCandles(assetId, tf, payload = {}) {
    if (!isValidRealCandles(payload.candles)) return;
    try {
      const record = {
        symbol: normalizeAssetSymbol(assetId),
        timeframe: marketTimeframeKey(tf),
        candles: payload.candles,
        source: payload.source || 'live_provider',
        providerLabel: payload.providerLabel || payload.source || 'Live provider',
        updatedAt: payload.updatedAt || new Date().toISOString(),
        mock: false,
      };
      localStorage.setItem(marketCacheKey(assetId, tf), JSON.stringify(record));
    } catch (_) {}
  }

  function readLastGoodPrice(assetId) {
    try {
      const parsed = JSON.parse(localStorage.getItem(marketPriceCacheKey(assetId)) || 'null');
      if (!parsed || parsed.mock === true || !Number.isFinite(Number(parsed.price))) return null;
      return parsed;
    } catch (_) {
      return null;
    }
  }

  function writeLastGoodPrice(assetId, payload = {}) {
    if (!Number.isFinite(Number(payload.price))) return;
    try {
      localStorage.setItem(marketPriceCacheKey(assetId), JSON.stringify({
        symbol: normalizeAssetSymbol(assetId),
        price: Number(payload.price),
        change: Number(payload.change || 0),
        source: payload.source || 'live_provider',
        providerLabel: payload.providerLabel || payload.source || 'Live provider',
        updatedAt: payload.updatedAt || new Date().toISOString(),
        mock: false,
      }));
    } catch (_) {}
  }

  let _lastData = [];
  // ========== CHART FACTORY ==========
  function createChart(container, assetColor) {
    const color = assetColor || '#5eff9f';
    container.innerHTML = `
      <svg class="dex-mini-chart" viewBox="0 0 420 220" preserveAspectRatio="none">
        <g class="chart-grid">
          <line x1="0" y1="38" x2="420" y2="38"></line>
          <line x1="0" y1="108" x2="420" y2="108"></line>
          <line x1="0" y1="178" x2="420" y2="178"></line>
        </g>
        <line class="chart-range chart-high" x1="8" y1="24" x2="372" y2="24"></line>
        <text class="chart-label chart-high-label" x="10" y="19">H $-</text>
        <line class="chart-mid" x1="8" y1="106" x2="372" y2="106"></line>
        <text class="chart-label chart-mid-label" x="10" y="101">M $-</text>
        <line class="chart-range chart-low" x1="8" y1="188" x2="372" y2="188"></line>
        <text class="chart-label chart-low-label" x="10" y="183">L $-</text>
        <path class="chart-fill" fill="${color}"></path>
        <polyline class="chart-line" stroke="${color}" points="8,106 372,106"></polyline>
        <g class="trade-overlay"></g>
        <circle class="chart-dot" cx="372" cy="106" r="3.2" fill="${color}" style="color:${color};"></circle>
        <rect class="chart-price-box" x="378" y="97" width="36" height="18" rx="4" stroke="${color}"></rect>
        <text class="chart-price-text" x="396" y="109" text-anchor="middle" fill="${color}">$-</text>
        <text class="chart-status" x="8" y="210">LOADING FEED</text>
        <text class="chart-meta" x="412" y="210" text-anchor="end">LIVE</text>
      </svg>`;

    const svg = container.querySelector('.dex-mini-chart');
    const fill = svg.querySelector('.chart-fill');
    const line = svg.querySelector('.chart-line');
    const dot = svg.querySelector('.chart-dot');
    const high = svg.querySelector('.chart-high');
    const low = svg.querySelector('.chart-low');
    const mid = svg.querySelector('.chart-mid');
    const highLabel = svg.querySelector('.chart-high-label');
    const lowLabel = svg.querySelector('.chart-low-label');
    const midLabel = svg.querySelector('.chart-mid-label');
    const priceBox = svg.querySelector('.chart-price-box');
    const priceText = svg.querySelector('.chart-price-text');
    const statusText = svg.querySelector('.chart-status');
    const metaText = svg.querySelector('.chart-meta');
    const tradeOverlay = svg.querySelector('.trade-overlay');

    let renderState = { min: 0, max: 1, span: 1, top: 24, bottom: 188, left: 8, right: 372 };
    let _lastTradePlan = null;

    function projectY(value) {
      const n = Number(value);
      if (!Number.isFinite(n)) return renderState.bottom;
      return renderState.bottom - (((n - renderState.min) / renderState.span) * (renderState.bottom - renderState.top));
    }

    function renderTradeOverlay(plan) {
      if (!tradeOverlay) return;
      tradeOverlay.innerHTML = '';
      if (!plan || plan.hidden) return;
      const levelVisibility = plan.level_visibility || {};
      const selectedLevel = String(plan.selected_level || '');
      const levels = [
        { key: 'entry',     value: plan.entry,               tone: 'entry', label: 'ENTRY' },
        { key: 'stop_loss', value: plan.stop_loss,           tone: 'stop',  label: 'STOP'  },
        { key: 'tp1',       value: plan.take_profits?.tp1 ?? plan.tp1, tone: 'tp', label: 'TP1' },
        { key: 'tp2',       value: plan.take_profits?.tp2 ?? plan.tp2, tone: 'tp', label: 'TP2' },
        { key: 'tp3',       value: plan.take_profits?.tp3 ?? plan.tp3, tone: 'tp', label: 'TP3' },
      ].filter(level => levelVisibility[level.key] !== false && Number.isFinite(Number(level.value)));

      levels.forEach(level => {
        const y = projectY(level.value);
        const exactPrice = String(level.value);
        const selected = selectedLevel === level.key;
        const wireLevelClick = (el) => {
          el.setAttribute('data-plan-level', level.key);
          el.setAttribute('data-plan-price', exactPrice);
          el.addEventListener('click', (event) => {
            event.stopPropagation();
            if (typeof plan.onLevelClick === 'function') plan.onLevelClick(level.key, exactPrice);
          });
        };
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('class', `trade-line ${level.tone}${selected ? ' selected' : ''}`);
        line.setAttribute('x1', '8'); line.setAttribute('x2', '372');
        line.setAttribute('y1', y.toFixed(2)); line.setAttribute('y2', y.toFixed(2));
        wireLevelClick(line);
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('class', `trade-label ${level.tone}${selected ? ' selected' : ''}`);
        text.setAttribute('x', '320'); text.setAttribute('y', (y - 4).toFixed(2));
        text.textContent = `${level.label} ${formatMiniPrice(level.value)}`;
        wireLevelClick(text);
        tradeOverlay.appendChild(line);
        tradeOverlay.appendChild(text);
      });
    }

    function render(data = []) {
      _lastData = Array.isArray(data) ? data : [];
      const closes = Array.isArray(data)
        ? data.map(point => Number(point && point.close)).filter(Number.isFinite)
        : [];
      if (!closes.length) {
        line.setAttribute('points', '8,106 372,106');
        fill.setAttribute('d', 'M8 188 L8 106 L372 106 L372 188 Z');
        dot.setAttribute('cx', '372');
        dot.setAttribute('cy', '106');
        high.setAttribute('y1', '38');
        high.setAttribute('y2', '38');
        low.setAttribute('y1', '178');
        low.setAttribute('y2', '178');
        mid.setAttribute('y1', '106');
        mid.setAttribute('y2', '106');
        highLabel.textContent = 'H $-';
        midLabel.textContent = 'M $-';
        lowLabel.textContent = 'L $-';
        priceBox.setAttribute('y', '97');
        priceText.setAttribute('y', '109');
        priceText.textContent = '$-';
        renderTradeOverlay(_lastTradePlan);
        statusText.textContent = 'NO CHART DATA';
        metaText.textContent = 'OFFLINE';
        return;
      }
      const min = Math.min(...closes);
      const max = Math.max(...closes);
      const span = (max - min) || Math.max(1, max * 0.01);
      const top = 24;
      const bottom = 188;
      const left = 8;
      const right = 372;
      const width = right - left;
      renderState = { min, max, span, top, bottom, left, right };
      // projectY lives at createChart scope (see makeProjectY below), NOT here.
      // Declared as a local const inside render(), it was invisible to
      // renderTradeOverlay(), which threw ReferenceError on every render that
      // had a trade plan — leaving the chart blank.
      const projectY = makeProjectY(min, max, span, top, bottom);
      const points = closes.map((value, index) => {
        const x = left + ((width * index) / Math.max(1, closes.length - 1));
        const y = projectY(value);
        return [x, y];
      });
      const pointString = points.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
      const fillPath = `M${left} ${bottom} L${points.map(([x, y]) => `${x.toFixed(2)} ${y.toFixed(2)}`).join(' L')} L${right} ${bottom} Z`;
      const latest = closes[closes.length - 1];
      const latestY = projectY(latest);
      const midValue = (min + max) / 2;
      const midY = projectY(midValue);

      line.setAttribute('points', pointString);
      fill.setAttribute('d', fillPath);
      dot.setAttribute('cx', right);
      dot.setAttribute('cy', latestY.toFixed(2));
      high.setAttribute('y1', top);
      high.setAttribute('y2', top);
      low.setAttribute('y1', bottom);
      low.setAttribute('y2', bottom);
      mid.setAttribute('y1', midY.toFixed(2));
      mid.setAttribute('y2', midY.toFixed(2));
      highLabel.setAttribute('y', (top - 5).toFixed(2));
      lowLabel.setAttribute('y', (bottom - 5).toFixed(2));
      midLabel.setAttribute('y', (midY - 5).toFixed(2));
      highLabel.textContent = `H ${formatMiniPrice(max)}`;
      lowLabel.textContent = `L ${formatMiniPrice(min)}`;
      midLabel.textContent = `M ${formatMiniPrice(midValue)}`;
      priceBox.setAttribute('y', (latestY - 10).toFixed(2));
      priceBox.setAttribute('stroke', color);
      priceText.setAttribute('y', (latestY + 3).toFixed(2));
      priceText.setAttribute('fill', color);
      priceText.textContent = formatMiniPrice(latest);
      renderTradeOverlay(_lastTradePlan);
      statusText.textContent = 'LIVE SIGNAL';
      metaText.textContent = `${closes.length} PTS`;
    }

    // Live ticker price, kept apart from the last candle close. The candle series
    // can be up to a full interval stale (an hourly bar is an hour behind), so
    // marking the chart with its own last close made the right-edge price disagree
    // with the header by hundreds of dollars.
    let livePrice = null;
    // Shared y-projector. render() and renderTradeOverlay() both need it.
    function makeProjectY(min, max, span, top, bottom) {
      return (value) => bottom - (((value - min) / span) * (bottom - top));
    }

    // Manual vertical zoom: 1 = full auto-scale, >1 = zoomed in.
    let zoomK = 1;
    let viewCenter = null;
    const clampK = (k) => Math.min(6, Math.max(1, k || 1));

    function drawLiveMarker() {
      if (!livePrice || !renderState) return;
      const st = renderState;
      const { min, max, top, bottom, left, right } = st;
      const full = (max - min);
      if (!full) return;

      // Refuse to plot a live price that sits outside the series we are drawing.
      // This is what drew NEAR's $4.86 onto BTC's 84k-86k axis, producing the flat
      // line pinned to the top with a cliff off the right edge. A price that far
      // outside the range means the series and the quote are different assets.
      const pad = full * 0.25;
      if (livePrice < min - pad || livePrice > max + pad) {
        return;
      }
      // Zoomed view keeps the live price inside the band when possible.
      const y = (() => {
        const rel = (livePrice - min) / full;         // 0..1 across full range
        const y0 = bottom - rel * (bottom - top);     // auto-scale position
        if (zoomK <= 1) return y0;
        // zoomed: recentre on the live price, clamped to the plot area
        const half = full / (2 * zoomK);
        let c = livePrice;
        if (viewCenter === null) viewCenter = c;
        c = Math.max(min + half, Math.min(min + full - half, viewCenter));
        return bottom - ((c - (viewCenter - half)) / (2 * half)) * (bottom - top);
      })();
      if (!isFinite(y)) return;
      dot.setAttribute('cx', right);
      dot.setAttribute('cy', y.toFixed(2));
      priceBox.setAttribute('y', (y - 10).toFixed(2));
      priceText.setAttribute('y', (y + 3).toFixed(2));
      priceText.textContent = formatMiniPrice(livePrice);
      // keep the fill/line endpoint honest too
      const pts = line.getAttribute('points');
      if (pts) {
        const parts = pts.trim().split(/\s+/);
        const last = parts[parts.length - 1].split(',');
        parts[parts.length - 1] = last[0] + ',' + y.toFixed(2);
        line.setAttribute('points', parts.join(' '));
      }
    }

    function applyZoom(k) {
      zoomK = clampK(k);
      viewCenter = livePrice;
      render(_lastData || []);
    }

    return {
      chart: {
        resize() {},
        remove() { container.innerHTML = ''; },
        timeScale() { return { fitContent() {} }; },
      },
      series: {
        setData(data) { _lastData = data; render(data); drawLiveMarker(); },
      },
      // Called by the page on every price tick so the marker tracks the live market.
      setLivePrice(p) {
        if (typeof p !== 'number' || !isFinite(p)) return;
        livePrice = p;
        // Extend the series with the live tick so the plotted LINE moves.
        // Previously only the marker dot moved, so the polyline itself sat frozen
        // on the last candle close and the chart looked stuck between refreshes.
        const d = _lastData;
        if (d && d.length) {
          const last = d[d.length - 1];
          const tfMins = (function () {
            const sel = document.querySelector('.tf-btn.active, .tf-btn[aria-checked="true"]');
            const map = { '1m':1,'5m':5,'15m':15,'1H':60,'4H':240,'1D':1440 };
            return map[sel && sel.dataset.tf] || 60;
          })();
          const nowS = Math.floor(Date.now() / 1000);
          const barS = (Number(last.time) > 1e9 ? Number(last.time) : Number(last.time) * 1000) / 1000;
          // Same bar? Mutate it. New bar? Append it.
          if (nowS - barS < tfMins * 60) {
            last.close = p;
            last.high = Math.max(Number(last.high) || p, p);
            last.low  = Math.min(Number(last.low)  || p, p);
          } else {
            const barNow = Math.floor(nowS / (tfMins * 60)) * tfMins * 60;
            d.push({ time: barNow, open: Number(last.close) || p, high: p, low: p, close: p, volume: 0 });
            if (d.length > 400) d.shift();
          }
        }
        render(d);
        drawLiveMarker();
      },
      zoomIn()  { applyZoom(zoomK * 1.5); },
      zoomOut() { applyZoom(zoomK / 1.5); },
      resetZoom() { zoomK = 1; viewCenter = null; render(_lastData || []); drawLiveMarker(); },
      get zoom() { return zoomK; },
      setTradePlan(plan) {
        _lastTradePlan = plan || null;
        renderTradeOverlay(_lastTradePlan);
      },
      setStatus(text) { statusText.textContent = text; },
      setMeta(text) { metaText.textContent = text; },
    };
  }

  // ========== MARKET DATA FETCHING ==========
  async function fetchBridgeMarketState(asset, tf = '1H') {
    // For standalone use, we skip the bridge and go directly to providers
    return localMarketStateForAsset(asset, tf, MARKET_BRIDGE_UNAVAILABLE_LABEL);
  }

  async function fetchLocalMarketState(asset, tf) {
    try {
      return await fetchBridgeMarketState(asset, tf || '1H');
    } catch (err) {
      return localMarketStateForAsset(asset, tf || '1H', err?.message || MARKET_BRIDGE_UNAVAILABLE_LABEL);
    }
  }

  function localMarketStateForAsset(asset, tf, message) {
    const id = normalizeAssetSymbol(asset?.id || asset);
    return {
      id,
      price: null,
      change_24h: null,
      candles: [],
      source: MARKET_MOCK_PROVIDER,
      chart_source: MARKET_MOCK_PROVIDER,
      status: 'mock',
      chart_status: 'mock',
      fallback: true,
      message,
      bridge_status: 'offline',
      market_status: 'offline',
      provider_label: MARKET_MOCK_PROVIDER_LABEL,
      provider_status: 'mock',
    };
  }

  async function fetchCurrentPrice(asset) {
    if (asset.source === 'stub') return { price: null, change: null, source: MARKET_MOCK_PROVIDER, message: 'Data unavailable in local preview.' };

    let localState = null;
    let providerFallbackAllowed = true;

    try {
      localState = await fetchLocalMarketState(asset, '1H');
      providerFallbackAllowed = localState?.fallback_allowed !== false && localState?.status !== 'signal_not_ready' && localState?.source !== 'unsupported';

      const localSource = String(localState?.price_source || localState?.source || '').toLowerCase();
      const localIsMock = localState?.fallback === true || localSource === MARKET_MOCK_PROVIDER || localState?.status === 'mock';

      if (!localIsMock && Number.isFinite(Number(localState?.price))) {
        return {
          price: Number(localState.price),
          change: Number(localState.change_24h || 0),
          source: localState.price_source || MARKET_PROVIDER,
          chartStatus: localState.chart_status || 'live',
          feedStatus: localState.status || 'live',
          cached: localState.price_status === 'cached',
          fallback: false,
          providerLabel: localState.provider_label || MARKET_PROVIDER_LABEL,
          bridgeStatus: localState.bridge_status || 'online',
          marketStatus: localState.market_status || localState.status || 'live',
          providerStatus: localState.provider_status || localState.status || 'live',
        };
      }
    } catch (_) {}

    if (!providerFallbackAllowed) throw new Error(localState?.reason || localState?.message || 'Unsupported source');

    // Use server API to avoid CORS blocks — route through :3001
    if (asset.cg) {
      try {
        const r = await fetch(`http://127.0.0.1:3001/api/market/ticker/${encodeURIComponent(asset.cg)}`, { cache: 'no-store' });
        if (!r.ok) throw new Error('ticker');
        const d = await r.json();
        return {
          price: d.price || 0,
          change: d.change_24h || 0,
          source: d.source || 'coingecko',
          chartStatus: 'live',
          feedStatus: 'live',
          cached: false,
          fallback: false,
          providerLabel: 'CoinGecko (via proxy)',
          bridgeStatus: localState?.bridge_status || 'online',
          marketStatus: 'live',
          providerStatus: 'coingecko',
        };
      } catch (_) {}
    }

    if (asset.source === 'crypto' || asset.source === 'binance') {
      try {
        const r = await fetch(`http://127.0.0.1:3001/api/market/ticker/${asset.symbol}`, { cache: 'no-store' });
        if (!r.ok) throw new Error('ticker');
        const d = await r.json();
        return {
          price: d.price || 0,
          change: d.change_24h || 0,
          source: d.source || 'binance',
          chartStatus: 'live',
          feedStatus: 'live',
          cached: false,
          fallback: false,
          providerLabel: 'Binance (via proxy)',
          bridgeStatus: localState?.bridge_status || 'unavailable',
          marketStatus: 'live',
          providerStatus: 'binance',
        };
      } catch (_) {}
    } else if (asset.source === 'yahoo') {
      try {
        const r = await fetch(`http://127.0.0.1:3001/api/market/ticker/${asset.symbol}`, { cache: 'no-store' });
        if (!r.ok) throw new Error('ticker');
        const d = await r.json();
        return {
          price: d.price || 0,
          change: d.change_24h || 0,
          source: d.source || 'yahoo',
          chartStatus: 'live',
          feedStatus: 'live',
          cached: false,
          fallback: false,
          providerLabel: 'Yahoo (via proxy)',
          bridgeStatus: localState?.bridge_status || 'unavailable',
          marketStatus: 'live',
          providerStatus: 'yahoo',
        };
      } catch (_) {}
    }

    if (Number.isFinite(Number(localState?.price)) && localState?.price_status === 'cached') {
      // Only trust a cached price if it belongs to THIS asset. Returning a cached
      // value for a different symbol is what made every asset display Bitcoin.
      if (String(localState.id || '').toUpperCase() !== normalizeAssetSymbol(asset.id)) {
        throw new Error('cached price belongs to a different asset');
      }
      return {
        price: Number(localState.price),
        change: Number(localState.change_24h || 0),
        source: localState.price_source || MARKET_MOCK_PROVIDER,
        chartStatus: localState.chart_status || 'mock',
        feedStatus: localState.status || 'mock',
        cached: localState.price_status === 'cached',
        fallback: true,
        providerLabel: localState.provider_label || MARKET_MOCK_PROVIDER_LABEL,
        bridgeStatus: localState.bridge_status || 'unavailable',
        marketStatus: localState.market_status || '',
        providerStatus: localState.provider_status || localState.status || '',
      };
    }

    throw new Error(localState?.message || 'Data unavailable in local preview.');
  }

  // ========== OHLCV FETCHING ==========
  async function fetchCoinGeckoOHLC(asset, tf) {
    if (!asset.cg) throw new Error('CoinGecko asset missing');
    const days = CG_DAYS[tf] || '7';
    // Send the real timeframe. It used to collapse everything to 'hourly', which is
    // why 1M/5M/15M rendered hourly candles under a 15M label.
    const interval = tf;
    const r = await fetch(`http://127.0.0.1:3001/api/market/ohlcv/${encodeURIComponent(asset.cg)}?days=${days}&interval=${encodeURIComponent(interval)}`, { cache: 'no-store' });
    if (!r.ok) throw new Error('ohlcv');
    const d = await r.json();
    return d.candles || [];
  }

  async function fetchBinanceOHLC(symbol, tf) {
    // Use server API to avoid CORS blocks
    const r = await fetch(`http://127.0.0.1:3001/api/market/ohlcv/${symbol}?days=7&interval=${encodeURIComponent(tf)}`, { cache: 'no-store' });
    if (!r.ok) throw new Error('binance ohlcv');
    const d = await r.json();
    return d.candles || [];
  }

  async function fetchYahooOHLC(symbol, tf) {
    // Use server API to avoid CORS blocks
    const r = await fetch(`http://127.0.0.1:3001/api/market/ohlcv/${symbol}?days=7&interval=${encodeURIComponent(tf)}`, { cache: 'no-store' });
    if (!r.ok) throw new Error('yahoo ohlcv');
    const d = await r.json();
    return d.candles || [];
  }

  // ========== PUBLIC API ==========
  return {
    // Chart factory
    createChart,
    formatMiniPrice,

    // Data fetching
    fetchCurrentPrice,
    fetchCoinGeckoOHLC,
    fetchBinanceOHLC,
    fetchYahooOHLC,
    fetchLocalMarketState,
    localMarketStateForAsset,

    // Cache
    readLastGoodCandles,
    writeLastGoodCandles,
    readLastGoodPrice,
    writeLastGoodPrice,

    // Asset helpers
    normalizeAssetSymbol,
    buildCryptoAsset,
    marketTimeframeKey,
    marketCacheKey,
    marketPriceCacheKey,
    isValidRealCandles,

    // Constants
    TOP_CRYPTO_SYMBOLS,
    CG_DAYS,
    BINANCE_INT,
    BINANCE_LIM,
    YAHOO_INT,
    YAHOO_RNG,
  };
})();

// Export for both browser and Node
if (typeof module !== 'undefined' && module.exports) {
  module.exports = DexViewMarket;
}
if (typeof window !== 'undefined') {
  window.DexViewMarket = DexViewMarket;
}