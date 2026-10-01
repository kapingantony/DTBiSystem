/* ManagedTBI — Script */

document.addEventListener('DOMContentLoaded', function () {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const menuToggle = document.getElementById('menuToggle');

    if (menuToggle) {
        menuToggle.addEventListener('click', function () {
            sidebar.classList.toggle('open');
            overlay.classList.toggle('active');
        });
    }

    if (overlay) {
        overlay.addEventListener('click', function () {
            sidebar.classList.remove('open');
            overlay.classList.remove('active');
        });
    }

    // Close sidebar on Escape
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            if (sidebar) {
                sidebar.classList.remove('open');
            }
            if (overlay) {
                overlay.classList.remove('active');
            }
        }
    });

    // Table row click highlight (optional)
    document.querySelectorAll('table tbody tr[data-href]').forEach(function (row) {
        row.style.cursor = 'pointer';
        row.addEventListener('click', function () {
            window.location.href = this.dataset.href;
        });
    });

    // Mentor page functionality
    const mentorPage = document.querySelector('.mentors-page');
    if (mentorPage) {
        const mentorSearch = document.getElementById('mentorSearch');
        const mentorSpecialization = document.getElementById('mentorSpecialization');
        const mentorGrid = document.getElementById('mentorGrid');
        const mentorCards = Array.from(document.querySelectorAll('.person-card'));
        const tabs = Array.from(document.querySelectorAll('.tab-btn'));
        const addMentorBtn = document.getElementById('addMentorBtn');
        const mentorModal = document.getElementById('mentorModal');
        const closeMentorModal = document.getElementById('closeMentorModal');
        const cancelMentorBtn = document.getElementById('cancelMentorBtn');
        const mentorForm = document.getElementById('mentorForm');

        let activeTab = 'all';

        function applyMentorFilters() {
            if (!mentorGrid) {
                return;
            }

            const searchValue = mentorSearch ? mentorSearch.value.trim().toLowerCase() : '';
            const specializationValue = mentorSpecialization ? mentorSpecialization.value : 'all';

            mentorCards.forEach(function (card) {
                const name = (card.dataset.name || '').toLowerCase();
                const specialization = (card.dataset.specialization || '').toLowerCase();
                const status = (card.dataset.status || '').toLowerCase();
                const matchesSearch = !searchValue || name.includes(searchValue);
                const matchesSpecialization = specializationValue === 'all' || specialization === specializationValue;
                const matchesTab = activeTab === 'all' || status === activeTab;

                card.style.display = matchesSearch && matchesSpecialization && matchesTab ? 'block' : 'none';
            });
        }

        if (mentorSearch) {
            mentorSearch.addEventListener('input', applyMentorFilters);
        }

        if (mentorSpecialization) {
            mentorSpecialization.addEventListener('change', applyMentorFilters);
        }

        tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                tabs.forEach(function (item) {
                    item.classList.toggle('active', item === tab);
                });
                activeTab = tab.dataset.filter || 'all';
                applyMentorFilters();
            });
        });

        function openMentorModal() {
            if (mentorModal) {
                mentorModal.style.display = 'flex';
            }
        }

        function closeMentorModalDialog() {
            if (mentorModal) {
                mentorModal.style.display = 'none';
            }
            if (mentorForm) {
                mentorForm.reset();
            }
        }

        if (addMentorBtn) {
            addMentorBtn.addEventListener('click', openMentorModal);
        }

        if (closeMentorModal) {
            closeMentorModal.addEventListener('click', closeMentorModalDialog);
        }

        if (cancelMentorBtn) {
            cancelMentorBtn.addEventListener('click', closeMentorModalDialog);
        }

        if (mentorModal) {
            mentorModal.addEventListener('click', function (event) {
                if (event.target === mentorModal) {
                    closeMentorModalDialog();
                }
            });
        }

        if (mentorForm) {
            mentorForm.addEventListener('submit', function (event) {
                event.preventDefault();

                const nameInput = document.getElementById('mentorName');
                const roleInput = document.getElementById('mentorRole');
                const statusInput = document.getElementById('mentorStatus');
                const sessionInput = document.getElementById('mentorSession');

                const name = nameInput.value.trim();
                if (!name) {
                    nameInput.focus();
                    return;
                }

                const initials = name.split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase() || 'MN';
                const role = roleInput.value;
                const status = statusInput.value;
                const session = sessionInput.value.trim() || 'Next session: TBA';

                const card = document.createElement('div');
                card.className = 'person-card';
                card.dataset.name = name;
                card.dataset.specialization = role;
                card.dataset.status = status;
                card.innerHTML = `
                    <div class="person-card-top">
                        <div class="person-avatar ${initials.length > 1 ? 'gold' : 'blue'}">${initials}</div>
                        <div>
                            <div class="person-name">${name}</div>
                            <div class="person-role">${role.charAt(0).toUpperCase() + role.slice(1)} &amp; Expertise</div>
                        </div>
                    </div>
                    <div class="person-details">
                        <div class="person-detail"><i class="fas fa-briefcase"></i> New mentor</div>
                        <div class="person-detail"><i class="fas fa-users"></i> 0 startups mentored</div>
                        <div class="person-detail"><i class="fas fa-calendar"></i> ${session}</div>
                    </div>
                    <div class="person-tags">
                        <span class="tag">${role.charAt(0).toUpperCase() + role.slice(1)}</span>
                        <span class="tag gold">Support</span>
                    </div>
                `;

                mentorGrid.appendChild(card);
                mentorCards.push(card);
                closeMentorModalDialog();
                applyMentorFilters();
            });
        }

        applyMentorFilters();
    }

    // Investor page functionality
    const investorPage = document.querySelector('.investors-page');
    if (investorPage) {
        const investorSearch = document.getElementById('investorSearch');
        const investorType = document.getElementById('investorType');
        const investorInterest = document.getElementById('investorInterest');
        const investorGrid = document.getElementById('investorGrid');
        const investorCards = Array.from(document.querySelectorAll('.person-card'));
        const investorTabs = Array.from(document.querySelectorAll('.tab-btn'));
        const addInvestorBtn = document.getElementById('addInvestorBtn');
        const investorModal = document.getElementById('investorModal');
        const closeInvestorModal = document.getElementById('closeInvestorModal');
        const cancelInvestorBtn = document.getElementById('cancelInvestorBtn');
        const investorForm = document.getElementById('investorForm');

        let activeInvestorTab = 'all';

        function applyInvestorFilters() {
            if (!investorGrid) {
                return;
            }

            const searchValue = investorSearch ? investorSearch.value.trim().toLowerCase() : '';
            const typeValue = investorType ? investorType.value : 'all';
            const interestValue = investorInterest ? investorInterest.value : 'all';

            investorCards.forEach(function (card) {
                const name = (card.dataset.name || '').toLowerCase();
                const type = (card.dataset.type || '').toLowerCase();
                const interest = (card.dataset.interest || '').toLowerCase();
                const status = (card.dataset.status || '').toLowerCase();
                const matchesSearch = !searchValue || name.includes(searchValue);
                const matchesType = typeValue === 'all' || type === typeValue;
                const matchesInterest = interestValue === 'all' || interest === interestValue;
                const matchesTab = activeInvestorTab === 'all' || status === activeInvestorTab;

                card.style.display = matchesSearch && matchesType && matchesInterest && matchesTab ? 'block' : 'none';
            });
        }

        if (investorSearch) {
            investorSearch.addEventListener('input', applyInvestorFilters);
        }

        if (investorType) {
            investorType.addEventListener('change', applyInvestorFilters);
        }

        if (investorInterest) {
            investorInterest.addEventListener('change', applyInvestorFilters);
        }

        investorTabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                investorTabs.forEach(function (item) {
                    item.classList.toggle('active', item === tab);
                });
                activeInvestorTab = tab.dataset.filter || 'all';
                applyInvestorFilters();
            });
        });

        function openInvestorModal() {
            if (investorModal) {
                investorModal.style.display = 'flex';
            }
        }

        function closeInvestorModalDialog() {
            if (investorModal) {
                investorModal.style.display = 'none';
            }
            if (investorForm) {
                investorForm.reset();
            }
        }

        if (addInvestorBtn) {
            addInvestorBtn.addEventListener('click', openInvestorModal);
        }

        if (closeInvestorModal) {
            closeInvestorModal.addEventListener('click', closeInvestorModalDialog);
        }

        if (cancelInvestorBtn) {
            cancelInvestorBtn.addEventListener('click', closeInvestorModalDialog);
        }

        if (investorModal) {
            investorModal.addEventListener('click', function (event) {
                if (event.target === investorModal) {
                    closeInvestorModalDialog();
                }
            });
        }

        if (investorForm) {
            investorForm.addEventListener('submit', function (event) {
                event.preventDefault();

                const nameInput = document.getElementById('investorName');
                const typeInput = document.getElementById('investorTypeSelect');
                const interestInput = document.getElementById('investorInterestSelect');
                const statusInput = document.getElementById('investorStatusSelect');

                const name = nameInput.value.trim();
                if (!name) {
                    nameInput.focus();
                    return;
                }

                const initials = name.split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase() || 'IN';
                const type = typeInput.value;
                const interest = interestInput.value;
                const status = statusInput.value;

                const card = document.createElement('div');
                card.className = 'person-card';
                card.dataset.name = name;
                card.dataset.type = type;
                card.dataset.interest = interest;
                card.dataset.status = status;
                card.innerHTML = `
                    <div class="person-card-top">
                        <div class="person-avatar ${initials.length > 1 ? 'gold' : 'blue'}">${initials}</div>
                        <div>
                            <div class="person-name">${name}</div>
                            <div class="person-role">${type.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</div>
                        </div>
                    </div>
                    <div class="person-details">
                        <div class="person-detail"><i class="fas fa-map-marker-alt"></i> New location</div>
                        <div class="person-detail"><i class="fas fa-coins"></i> $0 committed</div>
                        <div class="person-detail"><i class="fas fa-handshake"></i> 0 deals closed</div>
                    </div>
                    <div class="person-tags">
                        <span class="tag">${interest.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</span>
                        <span class="tag gold">New</span>
                    </div>
                `;

                investorGrid.appendChild(card);
                investorCards.push(card);
                closeInvestorModalDialog();
                applyInvestorFilters();
            });
        }

        applyInvestorFilters();
    }

    // Staff page functionality
    const staffPage = document.querySelector('.staff-page');
    if (staffPage) {
        const staffSearch = document.getElementById('staffSearch');
        const staffRoleFilter = document.getElementById('staffRoleFilter');
        const staffTableBody = document.getElementById('staffTableBody');
        const staffRows = Array.from(document.querySelectorAll('#staffTableBody tr'));
        const addStaffBtn = document.getElementById('addStaffBtn');
        const staffModal = document.getElementById('staffModal');
        const closeStaffModal = document.getElementById('closeStaffModal');
        const cancelStaffBtn = document.getElementById('cancelStaffBtn');
        const staffForm = document.getElementById('staffForm');

        function applyStaffFilters() {
            if (!staffTableBody) {
                return;
            }

            const searchValue = staffSearch ? staffSearch.value.trim().toLowerCase() : '';
            const roleValue = staffRoleFilter ? staffRoleFilter.value : 'all';

            staffRows.forEach(function (row) {
                const name = (row.dataset.name || '').toLowerCase();
                const role = (row.dataset.role || '').toLowerCase();
                const department = (row.dataset.department || '').toLowerCase();
                const email = (row.dataset.email || '').toLowerCase();
                const matchesSearch = !searchValue || name.includes(searchValue) || role.includes(searchValue) || department.includes(searchValue) || email.includes(searchValue);
                const matchesRole = roleValue === 'all' || role === roleValue;

                row.style.display = matchesSearch && matchesRole ? '' : 'none';
            });
        }

        if (staffSearch) {
            staffSearch.addEventListener('input', applyStaffFilters);
        }

        if (staffRoleFilter) {
            staffRoleFilter.addEventListener('change', applyStaffFilters);
        }

        function openStaffModal() {
            if (staffModal) {
                staffModal.style.display = 'flex';
            }
        }

        function closeStaffModalDialog() {
            if (staffModal) {
                staffModal.style.display = 'none';
            }
            if (staffForm) {
                staffForm.reset();
            }
            const title = document.getElementById('staffModalTitle');
            if (title) {
                title.textContent = 'Add Staff';
            }
        }

        if (addStaffBtn) {
            addStaffBtn.addEventListener('click', openStaffModal);
        }

        if (closeStaffModal) {
            closeStaffModal.addEventListener('click', closeStaffModalDialog);
        }

        if (cancelStaffBtn) {
            cancelStaffBtn.addEventListener('click', closeStaffModalDialog);
        }

        if (staffModal) {
            staffModal.addEventListener('click', function (event) {
                if (event.target === staffModal) {
                    closeStaffModalDialog();
                }
            });
        }

        document.querySelectorAll('.edit-staff-btn').forEach(function (button) {
            button.addEventListener('click', function () {
                const row = button.closest('tr');
                const name = row.dataset.name || '';
                const role = row.dataset.role || 'manager';
                const department = row.dataset.department || '';
                const email = row.dataset.email || '';
                const status = row.dataset.status || 'active';

                const nameInput = document.getElementById('staffName');
                const roleInput = document.getElementById('staffRole');
                const departmentInput = document.getElementById('staffDepartment');
                const emailInput = document.getElementById('staffEmail');
                const statusInput = document.getElementById('staffStatus');
                const title = document.getElementById('staffModalTitle');

                if (nameInput) nameInput.value = name;
                if (roleInput) roleInput.value = role;
                if (departmentInput) departmentInput.value = department.charAt(0).toUpperCase() + department.slice(1);
                if (emailInput) emailInput.value = email;
                if (statusInput) statusInput.value = status;
                if (title) title.textContent = 'Edit Staff';

                openStaffModal();
            });
        });

        if (staffForm) {
            staffForm.addEventListener('submit', function (event) {
                event.preventDefault();

                const name = document.getElementById('staffName').value.trim();
                const role = document.getElementById('staffRole').value;
                const department = document.getElementById('staffDepartment').value.trim();
                const email = document.getElementById('staffEmail').value.trim();
                const status = document.getElementById('staffStatus').value;

                if (!name || !email) {
                    return;
                }

                const displayRole = {
                    admin: 'System Admin',
                    manager: 'Program Manager',
                    coordinator: 'Mentor Coordinator',
                    analyst: 'Investment Analyst',
                    lead: 'Operations Lead'
                }[role] || 'Staff';

                const row = document.createElement('tr');
                row.dataset.name = name;
                row.dataset.role = role;
                row.dataset.department = department.toLowerCase() || 'general';
                row.dataset.email = email;
                row.dataset.status = status;
                row.innerHTML = `
                    <td class="fw-600">${name}</td>
                    <td>${displayRole}</td>
                    <td>${department || 'General'}</td>
                    <td>${email}</td>
                    <td><span class="badge-status active"><span class="dot-sm"></span> ${status === 'active' ? 'Active' : 'Inactive'}</span></td>
                    <td><button class="btn btn-sm btn-outline edit-staff-btn" type="button">Edit</button></td>
                `;

                const editButton = row.querySelector('.edit-staff-btn');
                editButton.addEventListener('click', function () {
                    const editRow = this.closest('tr');
                    const nameInput = document.getElementById('staffName');
                    const roleInput = document.getElementById('staffRole');
                    const departmentInput = document.getElementById('staffDepartment');
                    const emailInput = document.getElementById('staffEmail');
                    const statusInput = document.getElementById('staffStatus');
                    const title = document.getElementById('staffModalTitle');

                    nameInput.value = editRow.dataset.name || '';
                    roleInput.value = editRow.dataset.role || 'manager';
                    departmentInput.value = editRow.dataset.department ? editRow.dataset.department.charAt(0).toUpperCase() + editRow.dataset.department.slice(1) : '';
                    emailInput.value = editRow.dataset.email || '';
                    statusInput.value = editRow.dataset.status || 'active';
                    title.textContent = 'Edit Staff';
                    openStaffModal();
                });

                const currentTitle = document.getElementById('staffModalTitle');
                const editingExisting = currentTitle && currentTitle.textContent === 'Edit Staff';

                if (editingExisting) {
                    const activeRow = document.querySelector('.edit-staff-btn:focus')?.closest('tr');
                    if (activeRow) {
                        activeRow.replaceWith(row);
                    }
                } else {
                    staffTableBody.appendChild(row);
                }

                closeStaffModalDialog();
                applyStaffFilters();
            });
        }

        applyStaffFilters();
    }
});
