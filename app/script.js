let donationState = {
    amount: 0,
    donorName: '',
    paymentMethod: 'va'
};

const formatIDR = (num) => {
    return new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(num);
};

function selectAmount(value) {
    donationState.amount = value;
    document.getElementById('custom-amount').value = '';

    document.querySelectorAll('.amount-btn').forEach(btn => btn.classList.remove('selected'));
    const formatted = 'Rp ' + value.toLocaleString('id-ID');
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

    const nameInput = document.getElementById('donor-name');
    if (nameInput && nameInput.value) {
        document.getElementById('summary-donor').textContent = nameInput.value;
    } else {
        document.getElementById('summary-donor').textContent = '-';
    }
}

function nextStep(step) {
    if (step === 2 && donationState.amount < 10000) {
        alert("Minimal donasi Rp 10.000");
        return;
    }

    document.querySelectorAll('.wizard-step').forEach(el => el.classList.add('hidden'));
    document.getElementById(`step-${step}`).classList.remove('hidden');

    updateIndicators(step);
}

function prevStep(step) {
    document.querySelectorAll('.wizard-step').forEach(el => el.classList.add('hidden'));
    document.getElementById(`step-${step}`).classList.remove('hidden');
    updateIndicators(step);
}

function updateIndicators(currentStep) {
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

function selectPayment(type, element) {
    donationState.paymentMethod = type;

    document.querySelectorAll('.payment-method').forEach(el => el.classList.remove('selected'));
    element.classList.add('selected');

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
    const trxId = 'TRX' + Math.floor(Math.random() * 10000000000);
    const date = new Date().toISOString().split('T')[0];

    const user = auth.getUser();
    const donorName = user ? user.name : (document.getElementById('donor-name').value || 'Hamba Allah');
    const emailInput = document.querySelector('input[type="email"]');
    const userEmail = user ? user.email : (emailInput ? emailInput.value : '');

    const campaignName = "Bantu Operasi Jantung untuk Bayi Aisyah";

    const donationData = {
        id: trxId,
        campaign: campaignName,
        amount: donationState.amount,
        date: date,
        status: 'Berhasil',
        donor: donorName,
        email: userEmail
    };

    try {
        const response = await fetch('/api/donations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(donationData)
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.message || 'Gagal menyimpan donasi');
        }
    } catch (error) {
        alert(error.message || 'Gagal menyimpan donasi');
        return;
    }

    window.location.href = `invoice.html?amount=${donationState.amount}&trx=${trxId}`;
}

document.addEventListener('DOMContentLoaded', () => {
    updateSummary();
});
