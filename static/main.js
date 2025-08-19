let pages = [];
let currentPageId = null;

async function fetchPages() {
  const res = await fetch("/api/pages");
  const data = await res.json();
  pages = data.pages || [];
  return pages;
}

function byId(id) {
  return document.getElementById(id);
}

function showToast(msg, ok = true) {
  const t = document.createElement("div");
  t.className = "toast " + (ok ? "success" : "error");
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2200);
}

function renderSidebar() {
  const sidebar = byId("sidebar");
  sidebar.innerHTML = "";
  const home = pages.find((p) => p.id === "home");
  const links = (home?.items || []).filter((x) => x.type === "page_link");

  links.forEach((link) => {
    const a = document.createElement("a");
    a.href = "#";
    a.className =
      "page-link" + (link.page_id === currentPageId ? " active" : "");
    a.textContent = link.label;
    a.onclick = (e) => {
      e.preventDefault();
      loadPage(link.page_id);
    };
    sidebar.appendChild(a);
  });
}

function renderBreadcrumb(page) {
  const bc = byId("breadcrumb");
  bc.textContent = "الصفحة: " + (page?.label || "");
}

function renderPage(page) {
  currentPageId = page.id;
  renderSidebar();
  renderBreadcrumb(page);

  const itemsDiv = byId("items");
  itemsDiv.innerHTML = "";

  (page.items || []).forEach((item) => {
    const btn = document.createElement("button");
    btn.className = "action-btn";
    btn.textContent = item.label;

    if (item.type === "page_link") {
      btn.onclick = () => loadPage(item.page_id);
    } else if (
      item.type === "program" ||
      item.type === "shell" ||
      item.type === "shortcut"
    ) {
      btn.onclick = () => runAction({ page_id: currentPageId, ...item });
    } else if (item.type === "obs_ws") {
      btn.onclick = () =>
        runAction({
          page_id: currentPageId,
          type: "obs_ws",
          op: item.op,
          scene: item.scene,
          source: item.source,
          dir: item.dir,
        });
    } else if (item.type === "vmware") {
      btn.onclick = () =>
        runAction({
          page_id: currentPageId,
          type: "vmware",
          vmx: item.vmx,
          op: item.op || "start",
          guest_user: item.guest_user,
          guest_pass: item.guest_pass,
          keys: item.keys, // guest_key
          shell: item.shell, // guest_shell
          program: item.program, // guest_run
          args: item.args,
          env: item.env,
          text: item.text, // guest_type
          enter: item.enter,
        });
    }

    itemsDiv.appendChild(btn);
  });
}

async function runAction(payload) {
  try {
    let url = "/run";
    if (payload.type === "vmware") url = "/vmware/run"; // ← مهم

    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (res.ok) {
      showToast("تم 👍");
    } else {
      showToast(data.message || "خطأ", false);
    }
  } catch (e) {
    showToast("فشل الاتصال بالخادم", false);
  }
}

async function loadPage(id) {
  const page = pages.find((p) => p.id === id);
  if (!page) return;
  renderPage(page);
}

(async function init() {
  await fetchPages();
  const home = pages.find((p) => p.id === "home");
  const firstLink = (home?.items || []).find((x) => x.type === "page_link");
  const startId = firstLink ? firstLink.page_id : pages[0]?.id;
  loadPage(startId || "home");
})();
