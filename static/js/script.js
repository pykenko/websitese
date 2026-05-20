// State
let donationState = {
    amount: 0,
    donorName: '',
    paymentMethod: 'va'
};

// Format currency
const formatIDR = (num) => {
    return new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(num);
};

// Step 1: Amount Selection
function selectAmount(value, element) {
    donationState.amount = value;
    document.getElementById('custom-amount').value = ''; // Reset custom input

    // UI Updates
    document.querySelectorAll('.amount-btn').forEach(btn => btn.classList.remove('selected'));
    if (element) {
        element.classList.add('selected');
    }

    updateSummary();
}

function handleCustomAmount(input) {
    donationState.amount = parseInt(input.value) || 0;
    document.querySelectorAll('.amount-btn').forEach(btn => btn.classList.remove('selected'));
    updateSummary();
}

function updateSummary() {
    document.getElementById('summary-amount').textContent = formatIDR(donationState.amount);
    document.getElementById('summary-total').textContent = formatIDR(donationState.amount);

    // Update Donor Name in Summary
    const nameInput = document.getElementById('donor-name');
    const anonymousCheckbox = document.getElementById('anon');
    if (anonymousCheckbox && anonymousCheckbox.checked) {
        document.getElementById('summary-donor').textContent = 'Anonym';
    } else if (nameInput && nameInput.value) {
        document.getElementById('summary-donor').textContent = nameInput.value;
    } else {
        document.getElementById('summary-donor').textContent = '-';
    }
}

// Wizard Navigation
function nextStep(step) {
    // Validate Step 1
    if (step === 2 && donationState.amount < 10000) {
        alert("Minimal donasi Rp 10.000");
        return;
    }

    // Hide all steps
    document.querySelectorAll('.wizard-step').forEach(el => el.classList.add('hidden'));
    // Show new step
    document.getElementById(`step-${step}`).classList.remove('hidden');

    // Update Indicators
    updateIndicators(step);
}

function prevStep(step) {
    document.querySelectorAll('.wizard-step').forEach(el => el.classList.add('hidden'));
    document.getElementById(`step-${step}`).classList.remove('hidden');
    updateIndicators(step);
}

function updateIndicators(currentStep) {
    // Reset all
    for (let i = 1; i <= 3; i++) {
        const item = document.getElementById(`step-indicator-${i}`);
        const line = document.getElementById(`line-${i}`); // might be null for line-3

        if (i <= currentStep) {
            item.classList.add('active');
            if (line && i < currentStep) line.style.backgroundColor = 'var(--primary)';
        } else {
            item.classList.remove('active');
            if (line) line.style.backgroundColor = '#E5E7EB';
        }
    }
}

// Payment Selection
// Payment Selection
function selectPayment(type, element) {
    donationState.paymentMethod = type;

    document.querySelectorAll('.payment-method').forEach(el => el.classList.remove('selected'));
    element.classList.add('selected');

    // E-Wallet Logic
    const ewalletDesc = document.getElementById('ewallet-desc');
    const ewalletOptions = document.getElementById('ewallet-options');

    if (type === 'ewallet') {
        ewalletDesc.classList.add('hidden');
        ewalletOptions.classList.remove('hidden');
    } else {
        ewalletDesc.classList.remove('hidden');
        ewalletOptions.classList.add('hidden');
    }
}

function selectEWallet(provider, event) {
    event.stopPropagation();
    donationState.ewalletProvider = provider;

    document.querySelectorAll('.ewallet-btn').forEach(btn => btn.classList.remove('selected'));
    event.target.classList.add('selected');
}

async function finishDonation() {
    // Generate Transaction ID
    const trxId = 'TRX' + Math.floor(Math.random() * 10000000000);
    const date = new Date().toISOString().split('T')[0]; // YYYY-MM-DD

    // Get User info (if logged in)
    const user = auth.getUser();
    const anonymousCheckbox = document.getElementById('anon');
    const isAnonymous = Boolean(anonymousCheckbox && anonymousCheckbox.checked);
    const donorName = isAnonymous
        ? 'Anonym'
        : (user ? user.name : (document.getElementById('donor-name').value || 'Anonym'));
    const userEmail = user ? user.email : (document.querySelector('input[type="email"]').value || '');

    // Campaign Name (Dynamic based on selected campaign)
    const campaignName = window.activeCampaignTitle || "Donasi Program Pendidikan Anak";
    const campaignId = new URLSearchParams(window.location.search).get('campId') || '';

    // ✅ Field names disesuaikan dengan Flask models.py
    const donationPayload = {
        id:       trxId,           // Flask: payload.get("id")
        campaign_id: campaignId,
        campaign: campaignName,    // Flask: payload.get("campaign")
        amount:   donationState.amount, // Flask: payload.get("amount")
        date:     date,            // Flask: payload.get("date")
        status:   'Berhasil',      // Flask: payload.get("status")
        donor:    donorName,       // Flask: payload.get("donor")
        email:    userEmail,       // Flask: payload.get("email")
    };

    try {
        // ✅ Endpoint Flask (bukan PHP)
        const res = await fetch('/api/donations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',           // penting untuk session Flask
            body: JSON.stringify(donationPayload)
        });
        const data = await res.json();

        if (res.ok && data.success) {
            const invoiceUrl = (window.APP_ROUTES?.invoice || '/invoice') + `?amount=${donationState.amount}&trx=${trxId}`;
            window.location.href = invoiceUrl;
        } else {
            alert(data.message || 'Gagal memproses donasi.');
        }
    } catch (e) {
        console.error("Flask API tidak tersedia", e);
        alert('Gagal memproses donasi. Silakan coba lagi saat koneksi ke server tersedia.');
    }
}

/**
 * loadDonations() — dipakai oleh dashboard
 * Ambil riwayat donasi langsung dari Flask API / database
 * @returns {Promise<Array>} list donasi
 */
async function loadDonations() {
    try {
        const res = await fetch('/api/donations', {
            method: 'GET',
            credentials: 'include',
        });
        if (!res.ok) throw new Error('API error');
        const data = await res.json();
        return data.donations || [];
    } catch (e) {
        console.warn("Flask API tidak tersedia", e);
        return [];
    }
}

async function loadDonationSummary() {
    const user = auth.getUser();
    if (!user) {
        return {
            user_total_amount: 0,
            user_donation_count: 0,
            user_campaign_count: 0,
            platform_total_amount: 0,
            platform_donation_count: 0,
        };
    }

    try {
        const res = await fetch('/api/donations/summary', {
            method: 'GET',
            credentials: 'include',
        });
        if (!res.ok) throw new Error('Failed to fetch donation summary');
        const data = await res.json();
        return data.summary || {};
    } catch (e) {
        console.warn("Could not load donation summary:", e);
        return {
            user_total_amount: 0,
            user_donation_count: 0,
            user_campaign_count: 0,
            platform_total_amount: 0,
            platform_donation_count: 0,
        };
    }
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    updateSummary();

    const anonymousCheckbox = document.getElementById('anon');
    if (anonymousCheckbox) {
        anonymousCheckbox.addEventListener('change', updateSummary);
    }
});

// Load campaign total donations
async function loadCampaignTotal(campaignName) {
    try {
        const res = await fetch(`/api/campaigns/${encodeURIComponent(campaignName)}/total`, {
            method: 'GET',
            credentials: 'include',
        });
        if (!res.ok) throw new Error('Failed to fetch campaign total');
        const data = await res.json();
        return data.total || 0;
    } catch (e) {
        console.warn("Could not load campaign total:", e);
        return 0;
    }
}

// Update campaign progress display
async function updateCampaignProgress(campaignName, targetAmount) {
    const total = await loadCampaignTotal(campaignName);
    const percentage = targetAmount > 0 ? Math.min(100, Math.round((total / targetAmount) * 100)) : 0;
    
    // Update all elements with collected amount for this campaign
    document.querySelectorAll(`[data-campaign="${campaignName}"] .collected-amount`).forEach(el => {
        el.textContent = formatIDR(total);
    });
    
    // Update progress bar
    document.querySelectorAll(`[data-campaign="${campaignName}"] .premium-progress-fill`).forEach(el => {
        el.style.width = percentage + '%';
    });
    
    // Update percentage
    document.querySelectorAll(`[data-campaign="${campaignName}"] .campaign-percentage`).forEach(el => {
        el.textContent = percentage + '%';
    });
}
