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

function logout() {
  window.location.href = '/logout/';
}

document.addEventListener('DOMContentLoaded', function () {
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
