function showLogoutModal() {
  const modal = document.getElementById('logoutModal');
  if (modal) {
    modal.style.display = 'flex';
  }
}

function hideLogoutModal() {
  const modal = document.getElementById('logoutModal');
  if (modal) {
    modal.style.display = 'none';
  }
}

function updateCurrentDate() {
  const now = new Date();
  const options = { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' };
  const dateEl = document.getElementById('currentDate');
  if (dateEl) {
    dateEl.textContent = now.toLocaleDateString(undefined, options);
  }
}

function logout() {
  window.location.href = '/logout/';
}

function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  if (sidebar) {
    sidebar.classList.toggle('open');
  }
}

document.addEventListener('DOMContentLoaded', function () {
  updateCurrentDate();

  const modal = document.getElementById('logoutModal');
  if (!modal) {
    return;
  }

  modal.addEventListener('click', function (event) {
    if (event.target === modal) {
      hideLogoutModal();
    }
  });
});
