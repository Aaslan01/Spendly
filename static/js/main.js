// main.js — students will add JavaScript here as features are built

document.addEventListener('DOMContentLoaded', () => {
    if (typeof lucide !== 'undefined') lucide.createIcons();

    // Remove toasts from DOM after their animation finishes (2.3s in + 0.4s out)
    document.querySelectorAll('.toast').forEach(toast => {
        setTimeout(() => toast.remove(), 2700);
    });
});
