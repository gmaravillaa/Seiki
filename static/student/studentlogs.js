function updateCurrentDate() {
  const now = new Date();
  const options = { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' };
  const dateEl = document.getElementById('currentDate');
  if (dateEl) {
    dateEl.textContent = now.toLocaleDateString(undefined, options);
  }
}

function parseDate(value) {
  if (!value) {
    return null;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  parsed.setHours(0, 0, 0, 0);
  return parsed;
}

function formatDateRangeLabel(range) {
  if (!range) {
    return 'Select Date Range';
  }
  const start = range.start.toISOString().slice(0, 10);
  const end = range.end.toISOString().slice(0, 10);
  return `Range: ${start} → ${end}`;
}

document.addEventListener('DOMContentLoaded', function () {
  updateCurrentDate();

  const searchInput = document.getElementById('searchInput');
  const filterButtons = Array.from(document.querySelectorAll('.filter-btn'));
  const dateRangeBtn = document.getElementById('dateRangeBtn');
  const exportBtn = document.getElementById('exportBtn');
  const paginationButtonsContainer = document.querySelector('.pagination-buttons');
  const paginationText = document.querySelector('.pagination-text');
  const tableBody = document.querySelector('.data-table tbody');
  const noRecordsRow = tableBody ? tableBody.querySelector('.no-records-row') : null;

  if (!tableBody) {
    return;
  }

  const rowElements = Array.from(tableBody.querySelectorAll('tr')).filter(
    (row) => !row.classList.contains('no-records-row')
  );

  const state = {
    filter: 'all',
    page: 1,
    pageSize: 8,
    dateRange: null,
    searchTerm: ''
  };

  function getRowDate(row) {
    return parseDate(row.dataset.date);
  }

  function isRowVisible(row) {
    const rowDate = getRowDate(row);
    if (!rowDate) {
      return false;
    }

    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    if (state.filter === 'daily') {
      if (rowDate.getTime() !== today.getTime()) {
        return false;
      }
    }

    if (state.filter === 'weekly') {
      const earliest = new Date(today);
      earliest.setDate(today.getDate() - 6);
      if (rowDate < earliest || rowDate > today) {
        return false;
      }
    }

    if (state.dateRange) {
      if (rowDate < state.dateRange.start || rowDate > state.dateRange.end) {
        return false;
      }
    }

    if (state.searchTerm) {
      const searchValue = state.searchTerm.toLowerCase();
      const rowText = row.textContent.toLowerCase();
      return rowText.includes(searchValue);
    }

    return true;
  }

  function getFilteredRows() {
    return rowElements.filter(isRowVisible);
  }

  function updatePagination(filteredRows) {
    const totalRows = filteredRows.length;
    const pageCount = Math.max(1, Math.ceil(totalRows / state.pageSize));
    state.page = Math.min(state.page, pageCount);

    const startIndex = (state.page - 1) * state.pageSize;
    const endIndex = Math.min(startIndex + state.pageSize, totalRows);

    rowElements.forEach((row) => {
      row.style.display = 'none';
    });

    filteredRows.slice(startIndex, endIndex).forEach((row) => {
      row.style.display = '';
    });

    if (noRecordsRow) {
      noRecordsRow.style.display = totalRows === 0 ? 'table-row' : 'none';
    }

    if (paginationText) {
      const from = totalRows === 0 ? 0 : startIndex + 1;
      paginationText.innerHTML = `Showing <span class="font-semibold">${from}-${endIndex}</span> of <span class="font-semibold">${totalRows}</span> entries`;
    }

    if (paginationButtonsContainer) {
      paginationButtonsContainer.innerHTML = '';

      const createButton = (text, page, disabled, active) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'pagination-btn';
        if (active) {
          btn.classList.add('active');
        }
        if (disabled) {
          btn.disabled = true;
        }
        btn.textContent = text;
        btn.dataset.page = page;
        return btn;
      };

      paginationButtonsContainer.appendChild(
        createButton('Previous', Math.max(1, state.page - 1), state.page === 1, false)
      );

      for (let page = 1; page <= pageCount; page += 1) {
        paginationButtonsContainer.appendChild(
          createButton(page.toString(), page, false, page === state.page)
        );
      }

      paginationButtonsContainer.appendChild(
        createButton('Next', Math.min(pageCount, state.page + 1), state.page === pageCount, false)
      );
    }
  }

  function refreshTable() {
    const filteredRows = getFilteredRows();
    updatePagination(filteredRows);
  }

  function updateActiveFilter(selectedFilter) {
    state.filter = selectedFilter;
    state.page = 1;
    filterButtons.forEach((button) => {
      button.classList.toggle('active', button.dataset.filter === selectedFilter);
    });
    refreshTable();
  }

  function updateDateRangeLabel() {
    if (!dateRangeBtn) {
      return;
    }
    const label = dateRangeBtn.querySelector('span');
    if (label) {
      label.textContent = formatDateRangeLabel(state.dateRange);
    }
  }

  if (searchInput) {
    searchInput.addEventListener('input', (event) => {
      state.searchTerm = event.target.value.trim();
      state.page = 1;
      refreshTable();
    });
  }

  filterButtons.forEach((button) => {
    button.addEventListener('click', () => {
      updateActiveFilter(button.dataset.filter || 'all');
    });
  });

  if (dateRangeBtn) {
    dateRangeBtn.addEventListener('click', () => {
      const rawStart = prompt('Enter start date (YYYY-MM-DD). Leave blank to clear the current date range.');
      if (rawStart === null) {
        return;
      }

      if (!rawStart.trim()) {
        state.dateRange = null;
        state.page = 1;
        updateDateRangeLabel();
        refreshTable();
        return;
      }

      const rawEnd = prompt('Enter end date (YYYY-MM-DD). Leave blank to use the same start date.');
      if (rawEnd === null) {
        return;
      }

      const startDate = parseDate(rawStart.trim());
      const endDate = parseDate((rawEnd && rawEnd.trim()) || rawStart.trim());

      if (!startDate || !endDate) {
        alert('Please enter valid dates in YYYY-MM-DD format.');
        return;
      }

      endDate.setHours(23, 59, 59, 999);
      state.dateRange = { start: startDate, end: endDate };
      state.page = 1;
      updateDateRangeLabel();
      refreshTable();
    });
  }

  if (paginationButtonsContainer) {
    paginationButtonsContainer.addEventListener('click', (event) => {
      const button = event.target.closest('button');
      if (!button || button.disabled) {
        return;
      }
      const page = Number(button.dataset.page);
      if (Number.isNaN(page) || page === state.page) {
        return;
      }
      state.page = page;
      refreshTable();
    });
  }

  if (exportBtn) {
    exportBtn.addEventListener('click', () => {
      const filteredRows = getFilteredRows();
      if (filteredRows.length === 0) {
        alert('There are no entries to export.');
        return;
      }

      const rows = [ ['Date', 'Day', 'Time In', 'Time Out', 'Total Hours'] ];
      filteredRows.forEach((row) => {
        const cells = Array.from(row.querySelectorAll('td')).map((cell) => cell.textContent.trim());
        rows.push(cells);
      });

      const csvContent = rows
        .map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(','))
        .join('\r\n');

      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'student-logs.csv');
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    });
  }

  updateDateRangeLabel();
  refreshTable();
});
