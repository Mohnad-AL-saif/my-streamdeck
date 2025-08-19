let actionLock = false;
let appConfig = null;
let currentPageId = 'home';
const pageStack = [];

function getPageById(id) {
  return appConfig.pages.find(p => p.id === id);
}

async function loadConfig() {
  const res = await fetch('/buttons');
  appConfig = await res.json();
}

function setHeaderTitle(title) {
  const titleEl = document.getElementById('title');
  if (titleEl) titleEl.textContent = `🖲️ ${title}`;
}

async function renderPage() {
  const page = getPageById(currentPageId);
  const container = document.getElementById('buttonsContainer');
  const backBtn = document.getElementById('backBtn');

  container.innerHTML = '';
  setHeaderTitle(page?.label || 'Stream Deck');

  if (currentPageId === 'home') backBtn.classList.add('hidden');
  else backBtn.classList.remove('hidden');

  // صفحة VMware ديناميكية
  if (currentPageId === 'vmware') {
    // زر تحديث
    const refresh = document.createElement('button');
    refresh.className = 'stream-button';
    refresh.textContent = '🔄 تحديث القائمة';
    refresh.onclick = () => renderPage();
    container.appendChild(refresh);

    // احضر القائمة
    const res = await fetch('/vms');
    const { vms } = await res.json();

    if (!vms || vms.length === 0) {
      const empty = document.createElement('div');
      empty.style.opacity = '0.85';
      empty.textContent = 'لا توجد آلات .vmx في المسارات المحددة';
      container.appendChild(empty);
      return;
    }

    // لكل VM: اسم + تشغيل + إيقاف
    vms.forEach(vm => {
      const row = document.createElement('div');
      row.style.display = 'grid';
      row.style.gridTemplateColumns = '1.2fr 0.9fr 0.9fr';
      row.style.gap = '10px';
      row.style.alignItems = 'center';

      const nameBtn = document.createElement('button');
      nameBtn.className = 'stream-button';
      nameBtn.textContent = vm.name;

      const startBtn = document.createElement('button');
      startBtn.className = 'stream-button';
      startBtn.textContent = '▶️ تشغيل';
      startBtn.onclick = () => runAction({ type: 'vmware', op: 'start', vmx: vm.vmx });

      const stopBtn = document.createElement('button');
      stopBtn.className = 'stream-button';
      stopBtn.textContent = '⏹️ إيقاف';
      stopBtn.onclick = () => runAction({ type: 'vmware', op: 'stop', vmx: vm.vmx });

      row.appendChild(nameBtn);
      row.appendChild(startBtn);
      row.appendChild(stopBtn);
      container.appendChild(row);
    });

    return; // انتهت صفحة VMware
  }

  // الصفحات العادية (روابط/أكشن)
  (page?.items || []).forEach(item => {
    const btn = document.createElement('button');
    btn.className = 'stream-button';
    btn.textContent = item.label;

    if (item.type === 'page_link') {
      btn.onclick = () => {
        pageStack.push(currentPageId);
        currentPageId = item.page_id;
        renderPage();
      };
    } else if (item.type === 'action') {
      btn.onclick = () => runAction(item.action);
    }

    container.appendChild(btn);
  });
}

async function runAction(action) {
  if (actionLock) return;
  actionLock = true;
  try {
    await fetch('/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(action)
    });
  } catch (e) {
    console.error('خطأ أثناء تنفيذ الإجراء:', e);
  } finally {
    setTimeout(() => { actionLock = false; }, 500);
  }
}

document.getElementById('backBtn').onclick = () => {
  if (pageStack.length > 0) currentPageId = pageStack.pop();
  else currentPageId = 'home';
  renderPage();
};

window.onload = async () => {
  await loadConfig();
  renderPage();
};
