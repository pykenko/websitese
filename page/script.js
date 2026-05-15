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
function selectAmount(value) {
    donationState.amount = value;
    document.getElementById('custom-amount').value = ''; // Reset custom input

    // UI Updates
    document.querySelectorAll('.amount-btn').forEach(btn => btn.classList.remove('selected'));
    // Find button with this value (simple text match for demo)
    const formatted = 'Rp ' + value.toLocaleString('id-ID'); // rough match
    // More robust: add data-value attributes to buttons usually
    event.target.classList.add('selected');

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
    if (nameInput && nameInput.value) {
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
    const donorName = user ? user.name : (document.getElementById('donor-name').value || 'Hamba Allah');
    const userEmail = user ? user.email : (document.querySelector('input[type="email"]').value || '');

    // Campaign Name (Dynamic based on selected campaign)
    const campaignName = window.activeCampaignTitle || "Donasi Program Pendidikan Anak";

    // ✅ Field names disesuaikan dengan Flask models.py
    const donationPayload = {
        id:       trxId,           // Flask: payload.get("id")
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
            window.location.href = `invoice.html?amount=${donationState.amount}&trx=${trxId}`;
        } else {
            alert(data.message || 'Gagal memproses donasi.');
        }
    } catch (e) {
        // Fallback: simpan ke localStorage jika server tidak tersedia
        console.warn("Flask API tidak tersedia, simpan ke localStorage", e);
        const localData = { ...donationPayload, campaign_id: new URLSearchParams(window.location.search).get('campId') };
        let donations = JSON.parse(localStorage.getItem('binakasih_donations') || '[]');
        donations.unshift(localData);
        localStorage.setItem('binakasih_donations', JSON.stringify(donations));
        window.location.href = `invoice.html?amount=${donationState.amount}&trx=${trxId}`;
    }
}

/**
 * loadDonations() — dipakai oleh dashboard.html
 * Ambil riwayat donasi dari Flask API, fallback ke localStorage
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
        // Sinkronkan ke localStorage sebagai cache
        if (data.donations) {
            localStorage.setItem('binakasih_donations', JSON.stringify(data.donations));
        }
        return data.donations || [];
    } catch (e) {
        console.warn("Flask API tidak tersedia, pakai localStorage", e);
        return JSON.parse(localStorage.getItem('binakasih_donations') || '[]');
    }
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    updateSummary();
});

