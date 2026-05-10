const state = {
  token: localStorage.getItem("library_token") || "",
  admin: null,
  view: "dashboard",
  books: [],
  readers: [],
  loans: [],
};

const titles = {
  dashboard: ["仪表盘", "系统运行概览"],
  books: ["图书管理", "维护馆藏图书和库存"],
  readers: ["读者管理", "维护借书证和读者状态"],
  loans: ["借阅归还", "登记借书并处理归还"],
  overdue: ["逾期记录", "查看逾期未归还记录"],
};

const $ = (selector) => document.querySelector(selector);
const validViews = new Set(Object.keys(titles));

function showToast(message, isError = false) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.hidden = false;
  setTimeout(() => {
    toast.hidden = true;
  }, 3200);
}

function setLoggedIn(loggedIn) {
  $("#login-view").hidden = loggedIn;
  $("#app-view").hidden = !loggedIn;
}

async function api(path, options = {}) {
  const headers = options.headers || {};
  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }
  if (options.body && typeof options.body !== "string") {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }
  const response = await fetch(path, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) {
      logout(false);
    }
    throw new Error(data.detail || "请求失败");
  }
  return data;
}

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function toInt(value, fallback = 0) {
  if (value === "" || value === null || value === undefined) return fallback;
  return Number.parseInt(value, 10);
}

function badge(value) {
  return `<span class="badge ${value}">${value}</span>`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function emptyRow(colspan, text) {
  return `<tr><td colspan="${colspan}">${escapeHtml(text)}</td></tr>`;
}

async function login(event) {
  event.preventDefault();
  const error = $("#login-error");
  error.hidden = true;
  try {
    const data = await api("/api/auth/login", {
      method: "POST",
      body: formData(event.currentTarget),
    });
    state.token = data.token;
    state.admin = data.admin;
    localStorage.setItem("library_token", state.token);
    $("#admin-name").textContent = data.admin.display_name;
    setLoggedIn(true);
    navigateTo("dashboard");
  } catch (err) {
    error.textContent = err.message;
    error.hidden = false;
  }
}

async function logout(callApi = true) {
  if (callApi && state.token) {
    await api("/api/auth/logout", { method: "POST" }).catch(() => {});
  }
  state.token = "";
  state.admin = null;
  localStorage.removeItem("library_token");
  setLoggedIn(false);
  if (window.location.hash !== "#login") {
    window.location.hash = "login";
  }
}

async function restoreSession() {
  if (!state.token) {
    setLoggedIn(false);
    return;
  }
  try {
    const data = await api("/api/auth/me");
    state.admin = data.admin;
    $("#admin-name").textContent = data.admin.display_name;
    setLoggedIn(true);
    routeFromHash();
  } catch {
    logout(false);
  }
}

function navigateTo(view) {
  if (window.location.hash === `#${view}`) {
    switchView(view);
    return;
  }
  window.location.hash = view;
}

function routeFromHash() {
  const view = window.location.hash.replace("#", "") || "dashboard";
  if (!state.token) {
    setLoggedIn(false);
    if (view !== "login") {
      window.location.hash = "login";
    }
    return;
  }
  if (view === "login") {
    navigateTo("dashboard");
    return;
  }
  switchView(validViews.has(view) ? view : "dashboard");
}

function switchView(view) {
  state.view = view;
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  document.querySelectorAll(".view-section").forEach((section) => {
    section.hidden = section.id !== `${view}-section`;
  });
  $("#view-title").textContent = titles[view][0];
  $("#view-subtitle").textContent = titles[view][1];
  loadCurrentView().catch((err) => showToast(err.message, true));
}

async function loadCurrentView() {
  if (state.view === "dashboard") return loadDashboard();
  if (state.view === "books") return loadBooks();
  if (state.view === "readers") return loadReaders();
  if (state.view === "loans") return loadLoans();
  if (state.view === "overdue") return loadOverdue();
}

async function loadDashboard() {
  const stats = await api("/api/dashboard/stats");
  const items = [
    ["图书种类", stats.books],
    ["可借册数", stats.available_books],
    ["有效读者", stats.active_readers],
    ["借出记录", stats.borrowed_loans],
    ["逾期记录", stats.overdue_loans],
  ];
  $("#stats-grid").innerHTML = items
    .map(([label, value]) => `<article class="stat"><span>${label}</span><strong>${value}</strong></article>`)
    .join("");
}

async function loadBooks() {
  const q = encodeURIComponent($("#book-search").value.trim());
  const data = await api(`/api/books${q ? `?q=${q}` : ""}`);
  state.books = data.items;
  $("#books-body").innerHTML = data.items.length
    ? data.items.map((book) => `
      <tr>
        <td>${book.id}</td>
        <td>${escapeHtml(book.isbn)}</td>
        <td>${escapeHtml(book.title)}</td>
        <td>${escapeHtml(book.author)}</td>
        <td>${escapeHtml(book.category)}</td>
        <td>${book.available_count}/${book.total_count}</td>
        <td>${badge(book.status)}</td>
        <td class="actions">
          <button class="secondary" data-edit-book="${book.id}">编辑</button>
          <button class="secondary" data-delete-book="${book.id}">删除</button>
        </td>
      </tr>
    `).join("")
    : emptyRow(8, "暂无图书数据");
}

function resetBookForm() {
  $("#book-form").reset();
  $("#book-form [name=id]").value = "";
  $("#book-form [name=total_count]").value = 1;
  $("#book-form [name=available_count]").value = 1;
}

async function saveBook(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const raw = formData(form);
  const payload = {
    isbn: raw.isbn,
    title: raw.title,
    author: raw.author,
    publisher: raw.publisher,
    category: raw.category,
    published_year: raw.published_year ? toInt(raw.published_year, null) : null,
    total_count: toInt(raw.total_count, 1),
    available_count: raw.available_count === "" ? null : toInt(raw.available_count, 0),
    location: raw.location,
    status: raw.status,
  };
  const id = raw.id;
  await api(id ? `/api/books/${id}` : "/api/books", {
    method: id ? "PUT" : "POST",
    body: payload,
  });
  resetBookForm();
  await loadBooks();
  await loadDashboard();
  showToast("图书已保存");
}

async function editBook(id) {
  const book = state.books.find((item) => item.id === Number(id));
  if (!book) return;
  const form = $("#book-form");
  Object.entries(book).forEach(([key, value]) => {
    if (form.elements[key]) form.elements[key].value = value ?? "";
  });
}

async function deleteBook(id) {
  if (!confirm("确认删除该图书？")) return;
  await api(`/api/books/${id}`, { method: "DELETE" });
  await loadBooks();
  await loadDashboard();
  showToast("图书已删除");
}

async function loadReaders() {
  const q = encodeURIComponent($("#reader-search").value.trim());
  const data = await api(`/api/readers${q ? `?q=${q}` : ""}`);
  state.readers = data.items;
  $("#readers-body").innerHTML = data.items.length
    ? data.items.map((reader) => `
      <tr>
        <td>${reader.id}</td>
        <td>${escapeHtml(reader.card_no)}</td>
        <td>${escapeHtml(reader.name)}</td>
        <td>${escapeHtml(reader.phone)}</td>
        <td>${escapeHtml(reader.department)}</td>
        <td>${badge(reader.status)}</td>
        <td class="actions">
          <button class="secondary" data-edit-reader="${reader.id}">编辑</button>
          <button class="secondary" data-delete-reader="${reader.id}">删除</button>
        </td>
      </tr>
    `).join("")
    : emptyRow(7, "暂无读者数据");
}

function resetReaderForm() {
  $("#reader-form").reset();
  $("#reader-form [name=id]").value = "";
}

async function saveReader(event) {
  event.preventDefault();
  const raw = formData(event.currentTarget);
  const payload = {
    card_no: raw.card_no,
    name: raw.name,
    phone: raw.phone,
    email: raw.email,
    department: raw.department,
    status: raw.status,
  };
  const id = raw.id;
  await api(id ? `/api/readers/${id}` : "/api/readers", {
    method: id ? "PUT" : "POST",
    body: payload,
  });
  resetReaderForm();
  await loadReaders();
  await loadDashboard();
  showToast("读者已保存");
}

async function editReader(id) {
  const reader = state.readers.find((item) => item.id === Number(id));
  if (!reader) return;
  const form = $("#reader-form");
  Object.entries(reader).forEach(([key, value]) => {
    if (form.elements[key]) form.elements[key].value = value ?? "";
  });
}

async function deleteReader(id) {
  if (!confirm("确认删除该读者？")) return;
  await api(`/api/readers/${id}`, { method: "DELETE" });
  await loadReaders();
  await loadDashboard();
  showToast("读者已删除");
}

async function loadLoanOptions() {
  const [books, readers] = await Promise.all([
    api("/api/books?status=active"),
    api("/api/readers?status=active"),
  ]);
  const bookSelect = $("#loan-form [name=book_id]");
  const readerSelect = $("#loan-form [name=reader_id]");
  bookSelect.innerHTML = books.items
    .filter((book) => book.available_count > 0)
    .map((book) => `<option value="${book.id}">${escapeHtml(book.title)}（可借 ${book.available_count}）</option>`)
    .join("");
  readerSelect.innerHTML = readers.items
    .map((reader) => `<option value="${reader.id}">${escapeHtml(reader.name)}（${escapeHtml(reader.card_no)}）</option>`)
    .join("");
}

async function loadLoans() {
  await loadLoanOptions();
  const data = await api("/api/loans?status=borrowed");
  state.loans = data.items;
  $("#loans-body").innerHTML = data.items.length
    ? data.items.map((loan) => `
      <tr>
        <td>${loan.id}</td>
        <td>${escapeHtml(loan.book_title)}</td>
        <td>${escapeHtml(loan.reader_name)}</td>
        <td>${loan.loan_date}</td>
        <td>${loan.due_date}</td>
        <td>${badge(loan.loan_status)}</td>
        <td class="actions"><button class="secondary" data-return-loan="${loan.id}">归还</button></td>
      </tr>
    `).join("")
    : emptyRow(7, "暂无未归还记录");
}

async function saveLoan(event) {
  event.preventDefault();
  const raw = formData(event.currentTarget);
  const payload = {
    book_id: toInt(raw.book_id),
    reader_id: toInt(raw.reader_id),
    days: toInt(raw.days, 30),
    note: raw.note,
  };
  await api("/api/loans", { method: "POST", body: payload });
  event.currentTarget.reset();
  $("#loan-form [name=days]").value = 30;
  await loadLoans();
  await loadDashboard();
  showToast("借书已登记");
}

async function returnLoan(id) {
  await api(`/api/loans/${id}/return`, { method: "POST", body: {} });
  await loadLoans();
  await loadOverdue();
  await loadDashboard();
  showToast("归还已完成");
}

async function loadOverdue() {
  const data = await api("/api/loans/overdue");
  $("#overdue-body").innerHTML = data.items.length
    ? data.items.map((loan) => `
      <tr>
        <td>${loan.id}</td>
        <td>${escapeHtml(loan.book_title)}</td>
        <td>${escapeHtml(loan.reader_name)}</td>
        <td>${loan.loan_date}</td>
        <td>${loan.due_date}</td>
        <td>${escapeHtml(loan.note)}</td>
        <td class="actions"><button class="secondary" data-return-loan="${loan.id}">归还</button></td>
      </tr>
    `).join("")
    : emptyRow(7, "暂无逾期记录");
}

document.addEventListener("DOMContentLoaded", () => {
  $("#login-form").addEventListener("submit", login);
  $("#logout-button").addEventListener("click", () => logout(true));
  $("#refresh-button").addEventListener("click", () => loadCurrentView().catch((err) => showToast(err.message, true)));
  $("#book-form").addEventListener("submit", (event) => saveBook(event).catch((err) => showToast(err.message, true)));
  $("#reader-form").addEventListener("submit", (event) => saveReader(event).catch((err) => showToast(err.message, true)));
  $("#loan-form").addEventListener("submit", (event) => saveLoan(event).catch((err) => showToast(err.message, true)));
  $("#book-reset").addEventListener("click", resetBookForm);
  $("#reader-reset").addEventListener("click", resetReaderForm);
  $("#book-search-button").addEventListener("click", () => loadBooks().catch((err) => showToast(err.message, true)));
  $("#reader-search-button").addEventListener("click", () => loadReaders().catch((err) => showToast(err.message, true)));

  document.querySelectorAll(".nav-button").forEach((button) => {
    button.addEventListener("click", () => navigateTo(button.dataset.view));
  });

  window.addEventListener("hashchange", routeFromHash);

  document.body.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.dataset.editBook) editBook(target.dataset.editBook);
    if (target.dataset.deleteBook) deleteBook(target.dataset.deleteBook).catch((err) => showToast(err.message, true));
    if (target.dataset.editReader) editReader(target.dataset.editReader);
    if (target.dataset.deleteReader) deleteReader(target.dataset.deleteReader).catch((err) => showToast(err.message, true));
    if (target.dataset.returnLoan) returnLoan(target.dataset.returnLoan).catch((err) => showToast(err.message, true));
  });

  restoreSession();
});
