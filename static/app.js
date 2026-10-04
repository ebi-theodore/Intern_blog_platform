const state = { csrfToken: '', user: null, posts: [], category: 'All stories', query: '', activePost: null, toastTimer: null };
const grid = document.querySelector('#story-grid');
const backdrop = document.querySelector('#modal-backdrop');
const modal = document.querySelector('#modal');
const modalContent = document.querySelector('#modal-content');
const searchInput = document.querySelector('#search-input');

function escapeHtml(value = '') {
  return String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}
function paragraphs(value = '') {
  return String(value).split(/\n\s*\n/).map(text => `<p>${escapeHtml(text).replace(/\n/g, '<br>')}</p>`).join('');
}
function friendlyDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(date);
}
function readTime(text = '') { return `${Math.max(1, Math.ceil(text.trim().split(/\s+/).length / 220))} min read`; }
function showToast(message) {
  const toast = document.querySelector('#toast');
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => toast.classList.remove('show'), 2800);
}
async function api(path, options = {}) {
  const headers = { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(options.method && options.method !== 'GET' ? { 'X-CSRF-Token': state.csrfToken } : {}), ...options.headers };
  let response = await fetch(path, { credentials: 'same-origin', ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || 'Something went wrong. Please try again.');
  return data;
}
async function refreshCsrf() { const data = await api('/api/auth/csrf'); state.csrfToken = data.csrfToken; }
async function loadAccount() {
  const data = await api('/api/auth/me');
  state.user = data.user;
  renderAccount();
}
function renderAccount() {
  const target = document.querySelector('#account-actions');
  target.innerHTML = state.user
    ? `<div class="account-menu"><button class="button button-dark button-small" data-action="write">Write a story <span aria-hidden="true">↗</span></button><button class="search-trigger" data-action="logout" title="Sign out">${escapeHtml(state.user.username)} · Sign out</button></div>`
    : '<button class="button button-dark button-small" data-action="open-auth">Sign in <span aria-hidden="true">↗</span></button>';
}
async function loadPosts() {
  grid.innerHTML = '<div class="loading-state">Gathering a few good thoughts…</div>';
  try {
    const params = new URLSearchParams();
    if (state.query) params.set('q', state.query);
    if (state.category !== 'All stories') params.set('category', state.category);
    const data = await api(`/api/posts?${params}`);
    state.posts = data.posts;
    renderPosts();
  } catch (error) { grid.innerHTML = `<div class="loading-state">${escapeHtml(error.message)}</div>`; }
}
function renderPosts() {
  const empty = document.querySelector('#empty-state');
  if (!state.posts.length) {
    grid.innerHTML = '';
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');
  grid.innerHTML = state.posts.map((post, index) => `
    <article class="story-card" data-open-post="${post.id}" tabindex="0" role="button" aria-label="Read ${escapeHtml(post.title)}">
      <div class="story-cover cover-${index % 6}"><div class="cover-shape"></div><span class="cover-label">${escapeHtml(post.category)}</span></div>
      <h3 class="card-title">${escapeHtml(post.title)}</h3>
      <p class="card-excerpt">${escapeHtml(post.excerpt)}</p>
      <div class="card-meta"><span class="author-mark"><span class="avatar">${escapeHtml(post.author.slice(0, 1))}</span>${escapeHtml(post.author)}</span><span class="card-read">${readTime(post.body)} &nbsp;·&nbsp; ${post.comment_count} comments</span></div>
    </article>`).join('');
}
function openModal(content, wide = false) {
  modal.classList.toggle('modal-wide', wide);
  modalContent.innerHTML = content;
  backdrop.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  modal.querySelector('input,textarea,button')?.focus({ preventScroll: true });
}
function closeModal() {
  backdrop.classList.add('hidden');
  document.body.style.overflow = '';
  state.activePost = null;
}
function authForm(mode = 'login', message = '') {
  const registering = mode === 'register';
  openModal(`<span class="eyebrow"><span class="eyebrow-line"></span> Your commonplace</span>
    <h2 id="modal-title">${registering ? 'Make yourself at home.' : 'Welcome back.'}</h2>
    <p class="modal-intro">${registering ? 'Create an account to share a thought or join the conversation.' : 'Sign in to leave a note, or share a story of your own.'}</p>
    <form id="auth-form" data-mode="${mode}">
      ${registering ? '<label class="form-field"><span>Your name</span><input name="username" autocomplete="name" maxlength="24" required></label><label class="form-field"><span>Email address</span><input name="email" type="email" autocomplete="email" maxlength="254" required></label>' : '<label class="form-field"><span>Email or name</span><input name="identity" autocomplete="username" required></label>'}
      <label class="form-field"><span>Password</span><input name="password" type="password" autocomplete="${registering ? 'new-password' : 'current-password'}" minlength="8" required></label>
      <p class="form-error" id="form-error">${escapeHtml(message)}</p><button class="button button-dark form-submit" type="submit">${registering ? 'Create account' : 'Sign in'} <span>↗</span></button>
    </form><p class="form-switch">${registering ? 'Already have an account?' : 'New around here?'} <button data-action="switch-auth" data-mode="${registering ? 'login' : 'register'}">${registering ? 'Sign in' : 'Create an account'}</button></p>`);
}
function editorForm(post = null, error = '') {
  const editing = Boolean(post);
  openModal(`<div class="editor-heading"><span class="eyebrow"><span class="eyebrow-line"></span> Your journal</span><h2 id="modal-title">${editing ? 'Give it another thought.' : 'Leave a little something.'}</h2><p>${editing ? 'Make your changes, then save when you are ready.' : 'A good story can start anywhere.'}</p></div>
    <form id="post-form" data-id="${editing ? post.id : ''}">
      <label class="form-field"><span>Story title</span><input name="title" maxlength="120" value="${escapeHtml(post?.title || '')}" placeholder="The thing I keep coming back to…" required></label>
      <label class="form-field"><span>Topic</span><select name="category">${['Life', 'Culture', 'Creativity', 'Notes'].map(category => `<option ${post?.category === category ? 'selected' : ''}>${category}</option>`).join('')}</select></label>
      <label class="form-field"><span>A short introduction <small>(optional)</small></span><input name="excerpt" maxlength="220" value="${escapeHtml(post?.excerpt || '')}" placeholder="A sentence to draw someone in"></label>
      <label class="form-field"><span>Your story</span><textarea name="body" rows="8" minlength="20" maxlength="20000" placeholder="Take your time…" required>${escapeHtml(post?.body || '')}</textarea></label>
      <p class="form-error" id="form-error">${escapeHtml(error)}</p>
      <div class="editor-actions">${editing ? '<button type="button" class="delete-link" data-action="delete-post">Delete story</button>' : '<span></span>'}<button class="button button-dark" type="submit">${editing ? 'Save changes' : 'Publish story'} <span>↗</span></button></div>
    </form>`, true);
}
async function showPost(postId) {
  state.activePost = postId;
  openModal('<div class="loading-state">Opening this story…</div>', true);
  try {
    const data = await api(`/api/posts/${postId}`);
    if (state.activePost !== postId) return;
    const post = data.post;
    const canEdit = state.user && state.user.id === post.author_id;
    modalContent.innerHTML = `<article class="story-detail"><span class="detail-category">${escapeHtml(post.category)} · A commonplace story</span><h2 id="modal-title">${escapeHtml(post.title)}</h2><div class="detail-byline">By <strong>${escapeHtml(post.author)}</strong> &nbsp;·&nbsp; ${friendlyDate(post.created_at)} &nbsp;·&nbsp; ${readTime(post.body)}</div>
      ${canEdit ? `<div class="detail-controls"><button data-action="edit-post" data-id="${post.id}">Edit story</button></div>` : ''}<div class="detail-body">${paragraphs(post.body)}</div>
      <section class="comments"><h3>A few thoughts <span>(${data.comments.length})</span></h3>
        ${data.comments.length ? data.comments.map(comment => `<article class="comment"><div class="comment-meta"><span class="avatar">${escapeHtml(comment.author.slice(0, 1))}</span><strong>${escapeHtml(comment.author)}</strong><time>${friendlyDate(comment.created_at)}</time></div><p>${escapeHtml(comment.body)}</p></article>`).join('') : '<p class="no-comments">No notes yet. Be the first to leave one.</p>'}
        ${state.user ? `<form class="comment-form" id="comment-form" data-id="${post.id}"><textarea name="body" maxlength="2000" placeholder="Add a thoughtful note…" required></textarea><button class="button button-dark button-small" type="submit">Leave a note <span>↗</span></button><p class="form-error" id="form-error"></p></form>` : '<p class="form-switch">Want to join in? <button data-action="open-auth">Sign in or make an account</button></p>'}
      </section></article>`;
  } catch (error) { modalContent.innerHTML = `<p class="form-error">${escapeHtml(error.message)}</p>`; }
}
async function handleAuthSubmit(form) {
  const values = Object.fromEntries(new FormData(form));
  const mode = form.dataset.mode;
  const payload = mode === 'register' ? values : { identity: values.identity, password: values.password };
  try {
    const data = await api(`/api/auth/${mode}`, { method: 'POST', body: JSON.stringify(payload) });
    state.user = data.user;
    await refreshCsrf();
    renderAccount();
    closeModal();
    showToast(mode === 'register' ? 'Welcome to Commonplace.' : 'Good to have you back.');
    if (!state.posts.length) loadPosts();
  } catch (error) { document.querySelector('#form-error').textContent = error.message; }
}
document.addEventListener('click', async event => {
  const actionElement = event.target.closest('[data-action]');
  if (actionElement) {
    const action = actionElement.dataset.action;
    if (action === 'open-auth') authForm();
    if (action === 'close-modal') closeModal();
    if (action === 'switch-auth') authForm(actionElement.dataset.mode);
    if (action === 'write') state.user ? editorForm() : authForm('login', 'Sign in or create an account to publish a story.');
    if (action === 'edit-post') {
      try { const data = await api(`/api/posts/${actionElement.dataset.id}`); editorForm(data.post); }
      catch (error) { showToast(error.message); }
    }
    if (action === 'delete-post') {
      const id = document.querySelector('#post-form').dataset.id;
      if (confirm('Delete this story and all its comments? This cannot be undone.')) {
        try { await api(`/api/posts/${id}`, { method: 'DELETE' }); closeModal(); await loadPosts(); showToast('Your story has been removed.'); }
        catch (error) { document.querySelector('#form-error').textContent = error.message; }
      }
    }
    if (action === 'logout') {
      try { await api('/api/auth/logout', { method: 'POST' }); state.user = null; await refreshCsrf(); renderAccount(); showToast('You have signed out.'); }
      catch (error) { showToast(error.message); }
    }
    return;
  }
  const category = event.target.closest('[data-category]');
  if (category) {
    state.category = category.dataset.category;
    document.querySelectorAll('.category-chip').forEach(chip => chip.classList.toggle('selected', chip === category));
    loadPosts();
    return;
  }
  const card = event.target.closest('[data-open-post]');
  if (card) showPost(Number(card.dataset.openPost));
  if (event.target === backdrop) closeModal();
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && !backdrop.classList.contains('hidden')) closeModal();
  if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('[data-open-post]')) { event.preventDefault(); showPost(Number(event.target.dataset.openPost)); }
});
document.addEventListener('submit', async event => {
  const form = event.target;
  if (form.id === 'auth-form') { event.preventDefault(); await handleAuthSubmit(form); return; }
  if (form.id === 'post-form') {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(form));
    const id = form.dataset.id;
    try {
      const result = await api(id ? `/api/posts/${id}` : '/api/posts', { method: id ? 'PUT' : 'POST', body: JSON.stringify(payload) });
      closeModal(); await loadPosts(); showToast(id ? 'Your changes are saved.' : 'Your story is out in the world.');
      if (id) showPost(Number(id)); else if (result.id) showPost(Number(result.id));
    } catch (error) { document.querySelector('#form-error').textContent = error.message; }
    return;
  }
  if (form.id === 'comment-form') {
    event.preventDefault();
    const id = form.dataset.id;
    try { await api(`/api/posts/${id}/comments`, { method: 'POST', body: JSON.stringify({ body: new FormData(form).get('body') }) }); await showPost(Number(id)); await loadPosts(); showToast('Your note has been added.'); }
    catch (error) { form.querySelector('.form-error').textContent = error.message; }
  }
});
document.querySelector('#search-trigger').addEventListener('click', () => {
  const box = document.querySelector('#search-box');
  box.scrollIntoView({ behavior: 'smooth', block: 'center' });
  searchInput.focus({ preventScroll: true });
});
let searchTimer;
searchInput.addEventListener('input', () => {
  state.query = searchInput.value.trim();
  document.querySelector('#clear-search').style.display = searchInput.value ? 'block' : 'none';
  clearTimeout(searchTimer);
  searchTimer = setTimeout(loadPosts, 220);
});
document.querySelector('#clear-search').addEventListener('click', () => { searchInput.value = ''; state.query = ''; document.querySelector('#clear-search').style.display = 'none'; loadPosts(); });
(async function boot() {
  try { await refreshCsrf(); await loadAccount(); } catch (error) { showToast(error.message); }
  await loadPosts();
})();
