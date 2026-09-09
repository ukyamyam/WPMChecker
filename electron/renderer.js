const wpm = document.getElementById('wpm');
const meta = document.getElementById('meta');
const bar = document.getElementById('bar');
const status = document.getElementById('status');
let socket;

function send(command) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(command));
  }
}

function apply(data) {
  wpm.textContent = data.display;
  wpm.style.color = data.zone.color;
  wpm.classList.toggle('idle', !data.active);
  meta.textContent = `${data.source === 'system' ? 'System' : 'Mic'} · ${data.zone.name} · ${data.mode}`;
  const level = Math.max(0, Math.min(1, data.level || 0));
  bar.style.width = `${Math.round(level * 100)}%`;
  bar.style.background = data.zone.color;
}

async function connect() {
  const token = await window.wpmchecker.getAuthToken();
  socket = new WebSocket(`ws://127.0.0.1:8765/?token=${encodeURIComponent(token)}`);
  socket.addEventListener('open', () => { status.classList.add('on'); meta.textContent = 'connected'; });
  socket.addEventListener('close', () => { status.classList.remove('on'); meta.textContent = 'backend offline'; setTimeout(connect, 1000); });
  socket.addEventListener('message', (event) => apply(JSON.parse(event.data)));
}

window.addEventListener('contextmenu', (event) => {
  event.preventDefault();
  window.wpmchecker.showContextMenu();
});

window.wpmchecker.onBackendCommand(send);
connect();
