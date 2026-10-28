/**
 * ═══════════════════════════════════════════════════════════════════
 * JADWAL JABEZ — JavaScript
 * Handles: checkbox toggle, delete, search, filters, sidebar,
 *          toast notifications, confetti, dark mode, drag & drop,
 *          export/import, and notification reminders.
 * ═══════════════════════════════════════════════════════════════════
 */

document.addEventListener('DOMContentLoaded', () => {

    // ── Element references ─────────────────────────────────────────
    const sidebar         = document.getElementById('sidebar');
    const sidebarOverlay  = document.getElementById('sidebarOverlay');
    const sidebarClose    = document.getElementById('sidebarClose');
    const menuToggle      = document.getElementById('menuToggle');
    const searchInput     = document.getElementById('searchInput');
    const datePicker      = document.getElementById('datePicker');
    const deleteModal     = document.getElementById('deleteModal');
    const modalCancel     = document.getElementById('modalCancel');
    const modalConfirm    = document.getElementById('modalConfirm');
    const toastContainer  = document.getElementById('toastContainer');
    const progressBar     = document.getElementById('progressBar');
    const progressCount   = document.getElementById('progressCount');
    const progressPercent = document.getElementById('progressPercent');
    const timeline        = document.getElementById('timeline');
    const confettiCanvas  = document.getElementById('confettiCanvas');
    const themeToggle     = document.getElementById('themeToggle');
    const themeIcon       = document.getElementById('themeIcon');
    const themeLabel      = document.getElementById('themeLabel');
    const notifContainer  = document.getElementById('notificationContainer');

    // Export elements
    const exportBtn       = document.getElementById('exportBtn');
    const exportModal     = document.getElementById('exportModal');
    const exportCancel    = document.getElementById('exportCancel');
    const exportConfirm   = document.getElementById('exportConfirm');

    // Import elements
    const importBtn       = document.getElementById('importBtn');
    const importModal     = document.getElementById('importModal');
    const importCancel    = document.getElementById('importCancel');
    const importConfirm   = document.getElementById('importConfirm');
    const importDropZone  = document.getElementById('importDropZone');
    const importFileInput = document.getElementById('importFileInput');
    const importFileName  = document.getElementById('importFileName');

    // ID jadwal yang akan dihapus (diset saat user klik delete)
    let pendingDeleteId = null;
    let selectedImportFile = null;


    // ══════════════════════════════════════════════════════════════
    // DARK MODE
    // ══════════════════════════════════════════════════════════════

    function getStoredTheme() {
        return localStorage.getItem('jadwal-jabez-theme') || 'light';
    }

    function setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('jadwal-jabez-theme', theme);
        if (themeIcon) themeIcon.textContent = theme === 'dark' ? '☀️' : '🌙';
        if (themeLabel) themeLabel.textContent = theme === 'dark' ? 'Mode Terang' : 'Mode Gelap';
    }

    // Apply saved theme on load
    setTheme(getStoredTheme());

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const current = getStoredTheme();
            setTheme(current === 'dark' ? 'light' : 'dark');
        });
    }


    // ══════════════════════════════════════════════════════════════
    // SIDEBAR (mobile toggle)
    // ══════════════════════════════════════════════════════════════

    function openSidebar() {
        sidebar.classList.add('open');
        sidebarOverlay.classList.add('show');
        document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
        sidebar.classList.remove('open');
        sidebarOverlay.classList.remove('show');
        document.body.style.overflow = '';
    }

    if (menuToggle)    menuToggle.addEventListener('click', openSidebar);
    if (sidebarClose)  sidebarClose.addEventListener('click', closeSidebar);
    if (sidebarOverlay) sidebarOverlay.addEventListener('click', closeSidebar);


    // ══════════════════════════════════════════════════════════════
    // DATE PICKER — navigasi tanggal
    // ══════════════════════════════════════════════════════════════

    if (datePicker) {
        datePicker.addEventListener('change', () => {
            const chosenDate = datePicker.value;
            if (chosenDate) {
                const viewPath = datePicker.dataset.view === 'weekly' ? '/weekly' : '/';
                window.location.href = `${viewPath}?date=${encodeURIComponent(chosenDate)}`;
            }
        });
    }


    // ══════════════════════════════════════════════════════════════
    // CHECKBOX TOGGLE (via AJAX — tanpa reload)
    // ══════════════════════════════════════════════════════════════

    document.addEventListener('change', async (e) => {
        if (!e.target.classList.contains('schedule-checkbox')) return;

        const checkbox = e.target;
        const scheduleId = checkbox.dataset.id;
        const card = checkbox.closest('.schedule-card');

        try {
            const occurrenceDate = checkbox.dataset.date;
            const res = await fetch(
                `/api/toggle/${scheduleId}?date=${encodeURIComponent(occurrenceDate)}`,
                { method: 'POST' }
            );
            const data = await res.json();

            if (!res.ok || !data.success) {
                throw new Error(data.error || 'Gagal mengubah status jadwal.');
            }

            const title = card.querySelector('.schedule-title');

            if (data.is_completed) {
                // Jadwal selesai
                card.classList.add('completed', 'just-completed');
                card.dataset.status = 'completed';
                title.classList.add('line-through');
                showToast('🎉 Nice! Satu tugas selesai!');
            } else {
                // Jadwal dibatalkan
                card.classList.remove('completed', 'just-completed');
                card.classList.add('just-uncompleted');
                card.dataset.status = 'pending';
                title.classList.remove('line-through');
                showToast('↩️ Jadwal ditandai belum selesai.');
            }

            // Hapus animasi class setelah selesai
            setTimeout(() => {
                card.classList.remove('just-completed', 'just-uncompleted');
            }, 600);

            // Update progress
            updateProgress();

            // Update stat cards
            updateStatCards();

            // Cek apakah semua selesai
            checkAllCompleted();
        } catch (err) {
            console.error('Toggle error:', err);
            showToast('⚠️ Gagal mengubah status. Coba lagi.');
            // Revert checkbox
            checkbox.checked = !checkbox.checked;
        }
    });


    // ══════════════════════════════════════════════════════════════
    // DELETE — dengan modal konfirmasi
    // ══════════════════════════════════════════════════════════════

    document.addEventListener('click', (e) => {
        const deleteBtn = e.target.closest('.delete-btn');
        if (!deleteBtn) return;

        pendingDeleteId = deleteBtn.dataset.id;
        deleteModal.classList.add('show');
    });

    if (modalCancel) {
        modalCancel.addEventListener('click', () => {
            pendingDeleteId = null;
            deleteModal.classList.remove('show');
        });
    }

    // Klik di luar modal juga menutup
    if (deleteModal) {
        deleteModal.addEventListener('click', (e) => {
            if (e.target === deleteModal) {
                pendingDeleteId = null;
                deleteModal.classList.remove('show');
            }
        });
    }

    if (modalConfirm) {
        modalConfirm.addEventListener('click', async () => {
            if (!pendingDeleteId) return;

            try {
                const res = await fetch(`/api/delete/${pendingDeleteId}`, {
                    method: 'DELETE'
                });
                const data = await res.json();

                if (data.success) {
                    // Hapus card dari DOM dengan animasi
                    const card = document.querySelector(
                        `.schedule-card[data-id="${pendingDeleteId}"]`
                    );
                    if (card) {
                        card.style.transition = 'all .3s ease';
                        card.style.opacity = '0';
                        card.style.transform = 'translateX(40px) scale(.95)';
                        setTimeout(() => {
                            card.remove();
                            updateProgress();
                            updateStatCards();
                            checkEmptyState();
                        }, 300);
                    }
                    showToast('🗑️ Jadwal berhasil dihapus.');
                }
            } catch (err) {
                console.error('Delete error:', err);
                showToast('⚠️ Gagal menghapus. Coba lagi.');
            }

            pendingDeleteId = null;
            deleteModal.classList.remove('show');
        });
    }


    // ══════════════════════════════════════════════════════════════
    // SEARCH (filter client-side)
    // ══════════════════════════════════════════════════════════════

    if (searchInput) {
        searchInput.addEventListener('input', () => {
            const query = searchInput.value.toLowerCase().trim();
            const cards = document.querySelectorAll('.schedule-card');

            cards.forEach(card => {
                const title = card.querySelector('.schedule-title');
                if (!title) return;

                const match = title.textContent.toLowerCase().includes(query);
                card.classList.toggle('hidden-filter', !match && query !== '');
            });
        });
    }


    // ══════════════════════════════════════════════════════════════
    // FILTER BUTTONS (Semua / Belum selesai / Selesai)
    // ══════════════════════════════════════════════════════════════

    const filterBtns = document.querySelectorAll('.filter-btn');
    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Update active state
            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            applyFilters();
        });
    });

    // Category filter
    const categoryFilter = document.getElementById('categoryFilter');
    if (categoryFilter) {
        categoryFilter.addEventListener('change', applyFilters);
    }

    function applyFilters() {
        const activeFilter = document.querySelector('.filter-btn.active');
        const statusFilter = activeFilter ? activeFilter.dataset.filter : 'all';
        const catFilter = categoryFilter ? categoryFilter.value : 'all';
        const cards = document.querySelectorAll('.schedule-card');

        cards.forEach(card => {
            const status = card.dataset.status;
            const category = card.dataset.category;
            let show = true;

            // Status filter
            if (statusFilter === 'completed' && status !== 'completed') show = false;
            if (statusFilter === 'pending' && status !== 'pending') show = false;

            // Category filter
            if (catFilter !== 'all' && category !== catFilter) show = false;

            card.classList.toggle('hidden-filter', !show);
        });
    }


    // ══════════════════════════════════════════════════════════════
    // PROGRESS TRACKER
    // ══════════════════════════════════════════════════════════════

    function updateProgress() {
        const cards = document.querySelectorAll('.schedule-card');
        const total = cards.length;
        const completed = document.querySelectorAll(
            '.schedule-card .schedule-checkbox:checked'
        ).length;
        const percent = total > 0 ? Math.round((completed / total) * 100) : 0;

        if (progressBar)     progressBar.style.width = percent + '%';
        if (progressCount)   progressCount.textContent = `${completed} / ${total} selesai`;
        if (progressPercent) progressPercent.textContent = percent + '%';
    }

    function updateStatCards() {
        const cards = document.querySelectorAll('.schedule-card');
        const total = cards.length;
        const completed = document.querySelectorAll(
            '.schedule-card .schedule-checkbox:checked'
        ).length;
        const pending = total - completed;

        const statTotal = document.getElementById('statTodayTotal');
        const statCompleted = document.getElementById('statTodayCompleted');
        const statPending = document.getElementById('statTodayPending');

        if (statTotal) animateNumber(statTotal, total);
        if (statCompleted) animateNumber(statCompleted, completed);
        if (statPending) animateNumber(statPending, pending);
    }

    function animateNumber(element, target) {
        const current = parseInt(element.textContent) || 0;
        if (current === target) return;

        const duration = 400;
        const start = performance.now();

        function update(now) {
            const elapsed = now - start;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
            const value = Math.round(current + (target - current) * eased);
            element.textContent = value;

            if (progress < 1) {
                requestAnimationFrame(update);
            }
        }

        requestAnimationFrame(update);
    }


    // ══════════════════════════════════════════════════════════════
    // CHECK IF ALL COMPLETED → Confetti!
    // ══════════════════════════════════════════════════════════════

    function checkAllCompleted() {
        const cards = document.querySelectorAll('.schedule-card');
        if (cards.length === 0) return;

        const allDone = Array.from(cards).every(card =>
            card.classList.contains('completed')
        );

        if (allDone) {
            showToast('🔥 Semua jadwal hari ini selesai!');
            launchConfetti();
        }
    }

    function checkEmptyState() {
        if (!timeline) return;
        const cards = timeline.querySelectorAll('.schedule-card');
        if (cards.length === 0) {
            timeline.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">🎉</div>
                    <h3>Belum ada jadwal hari ini</h3>
                    <p>Gunakan waktu ini untuk beristirahat atau tambahkan jadwal baru.</p>
                    <a href="/add" class="btn btn-primary">+ Tambah Jadwal</a>
                </div>
            `;
            // Reset progress
            if (progressBar)     progressBar.style.width = '0%';
            if (progressCount)   progressCount.textContent = '0 / 0 selesai';
            if (progressPercent) progressPercent.textContent = '0%';
        }
    }


    // ══════════════════════════════════════════════════════════════
    // TOAST NOTIFICATION
    // ══════════════════════════════════════════════════════════════

    function showToast(message) {
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = message;
        toastContainer.appendChild(toast);

        // Hapus setelah animasi selesai
        setTimeout(() => {
            toast.remove();
        }, 3200);
    }


    // ══════════════════════════════════════════════════════════════
    // CONFETTI 🎊
    // ══════════════════════════════════════════════════════════════

    function launchConfetti() {
        if (!confettiCanvas) return;

        const ctx = confettiCanvas.getContext('2d');
        confettiCanvas.width = window.innerWidth;
        confettiCanvas.height = window.innerHeight;

        const particles = [];
        const colors = [
            '#6366f1', '#818cf8', '#a5b4fc',
            '#f97316', '#fb923c',
            '#22c55e', '#ef4444', '#eab308',
            '#ec4899', '#8b5cf6'
        ];

        // Buat 150 partikel confetti
        for (let i = 0; i < 150; i++) {
            particles.push({
                x: Math.random() * confettiCanvas.width,
                y: Math.random() * confettiCanvas.height - confettiCanvas.height,
                w: Math.random() * 10 + 5,
                h: Math.random() * 6 + 3,
                color: colors[Math.floor(Math.random() * colors.length)],
                speedY: Math.random() * 3 + 2,
                speedX: (Math.random() - 0.5) * 4,
                rotation: Math.random() * 360,
                rotationSpeed: (Math.random() - 0.5) * 10,
                opacity: 1,
            });
        }

        let frame = 0;
        const maxFrames = 180; // ~3 detik pada 60fps

        function animate() {
            ctx.clearRect(0, 0, confettiCanvas.width, confettiCanvas.height);
            frame++;

            particles.forEach(p => {
                p.y += p.speedY;
                p.x += p.speedX;
                p.rotation += p.rotationSpeed;

                // Fade out di akhir
                if (frame > maxFrames - 60) {
                    p.opacity -= 0.017;
                }

                ctx.save();
                ctx.translate(p.x, p.y);
                ctx.rotate((p.rotation * Math.PI) / 180);
                ctx.globalAlpha = Math.max(0, p.opacity);
                ctx.fillStyle = p.color;
                ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
                ctx.restore();
            });

            if (frame < maxFrames) {
                requestAnimationFrame(animate);
            } else {
                ctx.clearRect(0, 0, confettiCanvas.width, confettiCanvas.height);
            }
        }

        animate();
    }


    // ══════════════════════════════════════════════════════════════
    // DRAG & DROP — Reorder schedule cards
    // ══════════════════════════════════════════════════════════════

    let draggedCard = null;

    if (timeline) {
        timeline.addEventListener('dragstart', (e) => {
            const card = e.target.closest('.schedule-card');
            if (!card) return;

            draggedCard = card;
            card.classList.add('dragging');

            // Transparent drag image
            const ghost = card.cloneNode(true);
            ghost.style.opacity = '0.6';
            ghost.style.position = 'absolute';
            ghost.style.top = '-9999px';
            document.body.appendChild(ghost);
            e.dataTransfer.setDragImage(ghost, 50, 20);
            setTimeout(() => ghost.remove(), 0);

            e.dataTransfer.effectAllowed = 'move';
        });

        timeline.addEventListener('dragend', (e) => {
            if (draggedCard) {
                draggedCard.classList.remove('dragging');
                draggedCard = null;
            }

            // Remove all drag-over styles
            document.querySelectorAll('.schedule-card.drag-over').forEach(card => {
                card.classList.remove('drag-over');
            });

            // Save new order
            saveNewOrder();
        });

        timeline.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';

            const target = e.target.closest('.schedule-card');
            if (!target || target === draggedCard) return;

            // Remove previous drag-over
            document.querySelectorAll('.schedule-card.drag-over').forEach(card => {
                card.classList.remove('drag-over');
            });

            target.classList.add('drag-over');

            // Determine insert position
            const rect = target.getBoundingClientRect();
            const midY = rect.top + rect.height / 2;

            if (e.clientY < midY) {
                timeline.insertBefore(draggedCard, target);
            } else {
                timeline.insertBefore(draggedCard, target.nextSibling);
            }
        });

        timeline.addEventListener('drop', (e) => {
            e.preventDefault();
        });
    }

    async function saveNewOrder() {
        const cards = document.querySelectorAll('.schedule-card');
        const order = Array.from(cards).map(card => card.dataset.id);

        try {
            await fetch('/api/reorder', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ order }),
            });
        } catch (err) {
            console.error('Reorder error:', err);
        }
    }


    // ══════════════════════════════════════════════════════════════
    // EXPORT MODAL
    // ══════════════════════════════════════════════════════════════

    let exportRange = 'today';
    let exportFormat = 'json';

    if (exportBtn) {
        exportBtn.addEventListener('click', () => {
            if (exportModal) exportModal.classList.add('show');
        });
    }

    if (exportCancel) {
        exportCancel.addEventListener('click', () => {
            exportModal.classList.remove('show');
        });
    }

    if (exportModal) {
        exportModal.addEventListener('click', (e) => {
            if (e.target === exportModal) exportModal.classList.remove('show');
        });

        // Range buttons
        exportModal.querySelectorAll('.export-range-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                exportModal.querySelectorAll('.export-range-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                exportRange = btn.dataset.range;
            });
        });

        // Format buttons
        exportModal.querySelectorAll('.export-format-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                exportModal.querySelectorAll('.export-format-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                exportFormat = btn.dataset.format;
            });
        });
    }

    if (exportConfirm) {
        exportConfirm.addEventListener('click', () => {
            const dateParam = exportRange === 'today' ? (datePicker ? datePicker.value : '') : '';
            const url = `/api/export?format=${exportFormat}&date=${dateParam}`;

            // Trigger download
            const a = document.createElement('a');
            a.href = url;
            a.download = '';
            document.body.appendChild(a);
            a.click();
            a.remove();

            exportModal.classList.remove('show');
            showToast('📤 Export berhasil!');
        });
    }


    // ══════════════════════════════════════════════════════════════
    // IMPORT MODAL
    // ══════════════════════════════════════════════════════════════

    if (importBtn) {
        importBtn.addEventListener('click', () => {
            if (importModal) importModal.classList.add('show');
        });
    }

    if (importCancel) {
        importCancel.addEventListener('click', () => {
            importModal.classList.remove('show');
            resetImport();
        });
    }

    if (importModal) {
        importModal.addEventListener('click', (e) => {
            if (e.target === importModal) {
                importModal.classList.remove('show');
                resetImport();
            }
        });
    }

    // File input
    if (importFileInput) {
        importFileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                selectedImportFile = e.target.files[0];
                if (importFileName) importFileName.textContent = selectedImportFile.name;
                if (importConfirm) importConfirm.disabled = false;
            }
        });
    }

    // Drag & drop for import
    if (importDropZone) {
        ['dragenter', 'dragover'].forEach(event => {
            importDropZone.addEventListener(event, (e) => {
                e.preventDefault();
                importDropZone.classList.add('drag-active');
            });
        });

        ['dragleave', 'drop'].forEach(event => {
            importDropZone.addEventListener(event, (e) => {
                e.preventDefault();
                importDropZone.classList.remove('drag-active');
            });
        });

        importDropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            if (e.dataTransfer.files.length > 0) {
                selectedImportFile = e.dataTransfer.files[0];
                if (importFileName) importFileName.textContent = selectedImportFile.name;
                if (importConfirm) importConfirm.disabled = false;
            }
        });
    }

    if (importConfirm) {
        importConfirm.addEventListener('click', async () => {
            if (!selectedImportFile) return;

            const formData = new FormData();
            formData.append('file', selectedImportFile);

            importConfirm.disabled = true;
            importConfirm.textContent = '⏳ Mengimport...';

            try {
                const res = await fetch('/api/import', {
                    method: 'POST',
                    body: formData,
                });
                const data = await res.json();

                if (data.success) {
                    showToast(`📥 Berhasil mengimport ${data.imported} jadwal!`);
                    importModal.classList.remove('show');
                    resetImport();
                    // Reload page to show new data
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    showToast(`⚠️ ${data.error}`);
                    importConfirm.disabled = false;
                    importConfirm.textContent = '📥 Import';
                }
            } catch (err) {
                console.error('Import error:', err);
                showToast('⚠️ Gagal mengimport. Coba lagi.');
                importConfirm.disabled = false;
                importConfirm.textContent = '📥 Import';
            }
        });
    }

    function resetImport() {
        selectedImportFile = null;
        if (importFileName) importFileName.textContent = '';
        if (importConfirm) {
            importConfirm.disabled = true;
            importConfirm.textContent = '📥 Import';
        }
        if (importFileInput) importFileInput.value = '';
    }


    // ══════════════════════════════════════════════════════════════
    // NOTIFICATION REMINDERS
    // ══════════════════════════════════════════════════════════════

    function showNotification(title, text) {
        if (!notifContainer) return;

        const notif = document.createElement('div');
        notif.className = 'notification';
        notif.innerHTML = `
            <span class="notification-icon">🔔</span>
            <div class="notification-body">
                <div class="notification-title">${title}</div>
                <div class="notification-text">${text}</div>
            </div>
            <button class="notification-close" onclick="this.parentElement.remove()">✕</button>
        `;
        notifContainer.appendChild(notif);

        // Auto remove after animation
        setTimeout(() => {
            if (notif.parentElement) notif.remove();
        }, 8500);

        // Also try browser notification
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(title, { body: text, icon: '📅' });
        }
    }

    async function checkReminders() {
        try {
            const res = await fetch('/api/reminders?minutes=15');
            const data = await res.json();

            if (data.reminders && data.reminders.length > 0) {
                data.reminders.forEach(r => {
                    const key = `reminder-${r.id}-${new Date().toDateString()}`;
                    if (sessionStorage.getItem(key)) return; // Already shown

                    showNotification(
                        `⏰ ${r.title} dalam ${r.minutes_left} menit`,
                        `${r.start_time} - ${r.end_time}`
                    );
                    sessionStorage.setItem(key, '1');
                });
            }
        } catch (err) {
            // Silently fail
        }
    }

    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
        // Show a subtle prompt to ask
        setTimeout(() => {
            Notification.requestPermission();
        }, 5000);
    }

    // Check reminders every 60 seconds
    checkReminders();
    setInterval(checkReminders, 60000);


    // ══════════════════════════════════════════════════════════════
    // RECURRING DAYS TOGGLE (form pages)
    // ══════════════════════════════════════════════════════════════

    const isRecurring = document.getElementById('is_recurring');
    const recurringDaysGroup = document.getElementById('recurringDaysGroup');

    if (isRecurring && recurringDaysGroup) {
        const syncRecurringDaysVisibility = () => {
            recurringDaysGroup.hidden = !isRecurring.checked;
        };
        syncRecurringDaysVisibility();
        isRecurring.addEventListener('change', () => {
            syncRecurringDaysVisibility();
        });
    }


    // ══════════════════════════════════════════════════════════════
    // FORM VALIDATION (client-side)
    // ══════════════════════════════════════════════════════════════

    const scheduleForm = document.getElementById('scheduleForm');
    if (scheduleForm) {
        scheduleForm.addEventListener('submit', (e) => {
            const title = document.getElementById('title');
            const startTime = document.getElementById('start_time');
            const endTime = document.getElementById('end_time');
            let errors = [];

            if (!title.value.trim()) {
                errors.push('Nama kegiatan wajib diisi.');
            }

            if (startTime.value && endTime.value && startTime.value >= endTime.value) {
                errors.push('Waktu selesai harus lebih besar dari waktu mulai.');
            }

            const recurringCheckbox = document.getElementById('is_recurring');
            if (recurringCheckbox && recurringCheckbox.checked
                && !scheduleForm.querySelector('input[name="recurring_days"]:checked')) {
                errors.push('Pilih setidaknya satu hari untuk jadwal berulang.');
            }

            if (errors.length > 0) {
                e.preventDefault();
                errors.forEach(err => showToast('⚠️ ' + err));
            }
        });
    }


    // ══════════════════════════════════════════════════════════════
    // AUTO-DISMISS flash messages
    // ══════════════════════════════════════════════════════════════

    const flashes = document.querySelectorAll('.flash');
    flashes.forEach(flash => {
        setTimeout(() => {
            flash.style.transition = 'all .3s ease';
            flash.style.opacity = '0';
            flash.style.transform = 'translateY(-10px)';
            setTimeout(() => flash.remove(), 300);
        }, 4000);
    });

});
