// main.js — students will add JavaScript here as features are built

document.addEventListener('DOMContentLoaded', () => {
    if (typeof lucide !== 'undefined') lucide.createIcons();

    // Remove toasts from DOM after their animation finishes (2.3s in + 0.4s out)
    document.querySelectorAll('.toast').forEach(toast => {
        setTimeout(() => toast.remove(), 2700);
    });
});

// Currency Modal Functions
function openCurrencyModal() {
    const modal = document.getElementById('currency-modal');
    if (modal) {
        modal.style.display = 'flex';
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }
}

function closeCurrencyModal() {
    const modal = document.getElementById('currency-modal');
    if (modal) {
        modal.style.display = 'none';
        const result = document.getElementById('detection-result');
        if (result) result.style.display = 'none';
    }
}

// Close modal when clicking outside
document.addEventListener('click', (e) => {
    const modal = document.getElementById('currency-modal');
    if (modal && e.target === modal) {
        closeCurrencyModal();
    }
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeCurrencyModal();
    }
});

// Detect currency from location
async function detectCurrency() {
    const resultDiv = document.getElementById('detection-result');
    if (!resultDiv) return;

    resultDiv.style.display = 'block';
    resultDiv.textContent = 'Detecting your location...';
    resultDiv.className = 'detection-result';

    try {
        const response = await fetch('/profile/detect-currency');
        const data = await response.json();

        if (data.success && data.currency) {
            // Find and check the radio button for the detected currency
            const radio = document.querySelector(`input[name="currency"][value="${data.currency}"]`);
            if (radio) {
                radio.checked = true;
                resultDiv.textContent = `Detected: ${data.currency} — ${data.currencyName}. Click "Save Currency" to apply.`;
                resultDiv.className = 'detection-result detection-result--success';
            } else {
                resultDiv.textContent = `Location detected, but ${data.currency} is not in the available options.`;
            }
        } else {
            resultDiv.textContent = data.error || 'Could not detect your location.';
            resultDiv.className = 'detection-result detection-result--error';
        }
    } catch (error) {
        resultDiv.textContent = 'Failed to detect location. Please select manually.';
        resultDiv.className = 'detection-result detection-result--error';
    }
}
