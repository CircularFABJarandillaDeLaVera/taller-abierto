/* Sondeo privado: conserva borradores y confirma solo cortes entregados por el servidor. */
(() => {
  const script = document.currentScript;
  const baseDelay = Math.max(5, Number(script?.dataset.pollSeconds) || 10) * 1000;
  const counter = document.querySelector('[data-news-count]');
  const toast = document.querySelector('[data-news-toast]');
  const toastText = toast?.querySelector('[data-news-text]');
  const toastLink = toast?.querySelector('[data-news-link]');
  const conversation = document.querySelector('[data-conversation]');
  const showNew = document.querySelector('[data-show-new]');
  const csrf = document.querySelector('input[name="csrf_token"]')?.value;
  let grid = document.querySelector('[data-order-grid]');
  let receivedId = Number(conversation?.dataset.shownId || 0);
  let confirmedId = 0;
  let pendingCursor = conversation?.dataset.readCursor || null;
  let pendingTarget = receivedId;
  let previous = null;
  let stopped = false;
  let busy = false;
  let delay = baseDelay;
  let timer;
  let toastTimer;

  function schedule() {
    clearTimeout(timer);
    if (!stopped && !document.hidden) timer = setTimeout(poll, delay);
  }
  function stop() {
    stopped = true;
    clearTimeout(timer);
    clearTimeout(toastTimer);
    if (toast) toast.hidden = true;
  }
  document.querySelector('form[action="/salir"]')?.addEventListener('submit', stop);

  async function confirmPending() {
    if (!conversation || !pendingCursor || !csrf) return;
    const cursor = pendingCursor;
    const target = pendingTarget;
    const response = await fetch(`/panel/solicitudes/${conversation.dataset.conversation}/lectura`, {
      method: 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ csrf_token: csrf, read_cursor: cursor })
    });
    if (response.status === 401 || response.status === 404) stop();
    if (!response.ok) throw new Error('No se pudo confirmar el corte de lectura');
    if (pendingCursor === cursor) {
      confirmedId = Math.max(confirmedId, target);
      conversation.dataset.confirmedId = String(confirmedId);
      pendingCursor = null;
    }
  }

  function cardFromServer(html) {
    const holder = document.createElement('template');
    holder.innerHTML = html.trim();
    return holder.content.firstElementChild;
  }
  function syncCard(existing, incoming) {
    existing.dataset.activity = incoming.dataset.activity;
    const currentStatus = existing.querySelector('.status-pill');
    const nextStatus = incoming.querySelector('.status-pill');
    currentStatus.className = nextStatus.className;
    currentStatus.textContent = nextStatus.textContent;
    for (const selector of ['[data-card-notice]', '[data-card-quiet]']) {
      const current = existing.querySelector(selector);
      const next = incoming.querySelector(selector);
      current.hidden = next.hidden;
      current.textContent = next.textContent;
    }
    const currentDetails = existing.querySelectorAll('.order-facts dd');
    const nextDetails = incoming.querySelectorAll('.order-facts dd');
    currentDetails.forEach((detail, index) => { detail.textContent = nextDetails[index].textContent; });
    const currentTime = existing.querySelector('.order-facts time');
    const nextTime = incoming.querySelector('.order-facts time');
    if (currentTime && nextTime) currentTime.dateTime = nextTime.dateTime;
  }
  function updateCards(cards, items, role) {
    let empty = document.querySelector('[data-empty-state]');
    if (!grid && cards.length) {
      grid = document.createElement('div');
      grid.className = 'order-grid';
      grid.dataset.orderGrid = '';
      empty?.before(grid);
    }
    if (!grid) return;
    const allowed = new Set(cards.map(card => String(card.order_id)));
    for (const card of grid.querySelectorAll('[data-order-id]')) {
      if (!allowed.has(card.dataset.orderId)) card.remove();
    }
    for (const item of cards) {
      const incoming = cardFromServer(item.html);
      const existing = grid.querySelector(`[data-order-id="${item.order_id}"]`);
      if (existing) syncCard(existing, incoming);
      else grid.append(incoming);
    }
    if (!cards.length && !empty) {
      empty = document.createElement('section');
      empty.className = 'empty-state';
      empty.dataset.emptyState = '';
      const heading = document.createElement('h2');
      heading.textContent = role === 'student' ? 'Aún no tienes solicitudes asignadas' : role === 'teacher' ? 'Todavía no hay encargos' : 'Aquí aparecerán tus encargos';
      const explanation = document.createElement('p');
      explanation.textContent = 'Cuando haya encargos para ti, aparecerán aquí mientras esta web esté abierta.';
      empty.append(heading, explanation);
      grid.after(empty);
    }
    if (empty) empty.hidden = cards.length > 0;
    const withNews = new Set(items.map(item => String(item.order_id)));
    const nodes = [...grid.querySelectorAll('[data-order-id]')];
    nodes.sort((a, b) => Number(withNews.has(b.dataset.orderId)) - Number(withNews.has(a.dataset.orderId)) || b.dataset.activity.localeCompare(a.dataset.activity) || Number(b.dataset.orderId) - Number(a.dataset.orderId));
    nodes.forEach(node => grid.append(node));
  }

  function announce(item) {
    if (!toast || !toastText || !toastLink) return;
    toastText.textContent = `Encargo #${item.order_id}: ${item.label}.`;
    toastLink.href = item.href;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.hidden = true; }, 9000);
  }
  async function poll() {
    if (busy || stopped || document.hidden) return;
    busy = true;
    try {
      const response = await fetch('/panel/novedades', { credentials: 'same-origin', cache: 'no-store' });
      if (response.status === 401) { stop(); return; }
      if (!response.ok) throw new Error('No se pudieron consultar novedades');
      const data = await response.json();
      const current = new Map(data.items.map(item => [item.order_id, item]));
      counter.textContent = String(data.count);
      counter.hidden = data.count === 0;
      updateCards(data.cards, data.items, data.role);
      if (toast && !toast.hidden) {
        const linked = Number(toastLink.href.split('/').pop());
        if (!data.items.some(item => item.order_id === linked)) toast.hidden = true;
      }
      if (conversation) {
        const item = data.items.find(item => item.order_id === Number(conversation.dataset.conversation));
        showNew.hidden = !(pendingCursor || (item && item.kind === 'messages' && item.unread_messages > 0));
        showNew.textContent = pendingCursor ? 'Reintentar lectura' : 'Ver mensajes nuevos';
      }
      if (previous !== null) {
        const fresh = data.items.find(item => {
          const old = previous.get(item.order_id);
          return !old || (item.kind === 'messages' && item.unread_messages > old.unread_messages)
            || (item.kind === 'assignment' && item.assignment_version > old.assignment_version);
        });
        if (fresh) announce(fresh);
      }
      previous = current;
      delay = baseDelay;
    } catch (_) {
      delay = Math.min(delay * 2, 60000);
    } finally {
      busy = false;
      schedule();
    }
  }

  showNew?.addEventListener('click', async () => {
    showNew.disabled = true;
    try {
      if (pendingCursor) await confirmPending();
      const id = conversation.dataset.conversation;
      const response = await fetch(`/panel/solicitudes/${id}/mensajes/nuevos?despues=${receivedId}`, { credentials: 'same-origin', cache: 'no-store' });
      if (response.status === 401 || response.status === 404) { stop(); return; }
      if (!response.ok) throw new Error('No se pudieron cargar mensajes');
      const data = await response.json();
      const list = document.querySelector('[data-message-list]');
      for (const message of data.messages) {
        const article = document.createElement('article');
        article.className = `message${message.own ? ' message-own' : ''}`;
        article.dataset.messageId = String(message.id);
        const heading = document.createElement('div');
        heading.className = 'message-heading';
        const author = document.createElement('strong');
        author.textContent = message.author;
        const date = document.createElement('time');
        date.dateTime = message.iso_date;
        date.textContent = message.date;
        heading.append(author, date);
        const body = document.createElement('p');
        body.textContent = message.body;
        article.append(heading, body);
        list.append(article);
        receivedId = message.id;
        conversation.dataset.receivedId = String(receivedId);
      }
      if (data.messages.length) {
        pendingCursor = data.read_cursor;
        pendingTarget = receivedId;
        await confirmPending();
      }
      showNew.hidden = true;
      poll();
    } catch (_) {
      showNew.hidden = false;
      showNew.textContent = pendingCursor ? 'Reintentar lectura' : 'No se pudieron cargar. Reintentar';
    } finally {
      showNew.disabled = false;
    }
  });

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) clearTimeout(timer);
    else if (!stopped) poll();
  });
  (async () => {
    if (conversation) {
      try { await confirmPending(); }
      catch (_) { showNew.hidden = false; showNew.textContent = 'Reintentar lectura'; }
    }
    poll();
  })();
})();
