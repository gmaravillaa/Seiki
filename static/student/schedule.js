function enableEdit() {
  const editBtn = document.getElementById('editBtn');
  const editActionButtons = document.getElementById('editActionButtons');
  const editBanner = document.getElementById('editBanner');
  const dayInputs = document.querySelectorAll('.time-input');

  if (editBtn) {
    editBtn.style.display = 'none';
  }
  if (editActionButtons) {
    editActionButtons.style.display = 'flex';
  }
  if (editBanner) {
    editBanner.style.display = 'block';
  }
  dayInputs.forEach((input) => {
    input.disabled = false;
  });
}

function cancelEdit() {
  const editBtn = document.getElementById('editBtn');
  const editActionButtons = document.getElementById('editActionButtons');
  const editBanner = document.getElementById('editBanner');
  const dayInputs = document.querySelectorAll('.time-input');

  if (editBtn) {
    editBtn.style.display = 'inline-flex';
  }
  if (editActionButtons) {
    editActionButtons.style.display = 'none';
  }
  if (editBanner) {
    editBanner.style.display = 'none';
  }
  dayInputs.forEach((input) => {
    input.disabled = true;
  });
}

function saveSchedule() {
  cancelEdit();
  const saveMessage = document.getElementById('saveMessage');
  if (saveMessage) {
    saveMessage.textContent = 'Schedule changes saved.';
    saveMessage.style.display = 'block';
    setTimeout(() => {
      saveMessage.style.display = 'none';
    }, 3000);
  }
}

document.addEventListener('DOMContentLoaded', function () {
  const dayButtons = document.querySelectorAll('.day-toggle');
  dayButtons.forEach((button) => {
    button.addEventListener('click', function () {
      const dayItem = button.closest('.day-item');
      if (!dayItem) {
        return;
      }
      const isAvailable = dayItem.classList.toggle('available');
      const statusText = dayItem.querySelector('.day-status');
      if (statusText) {
        statusText.textContent = isAvailable ? 'Available' : 'Unavailable';
      }
    });
  });
});
