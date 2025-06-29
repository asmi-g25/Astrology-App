// Main JavaScript for Astrology Web App

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Form validation
    const forms = document.querySelectorAll('.needs-validation');
    Array.prototype.slice.call(forms).forEach(function (form) {
        form.addEventListener('submit', function (event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });

    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function(alert) {
        if (!alert.classList.contains('alert-danger')) {
            setTimeout(function() {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }, 5000);
        }
    });

    // Add loading states to form submissions
    const submitButtons = document.querySelectorAll('form button[type="submit"]');
    submitButtons.forEach(function(button) {
        const form = button.closest('form');
        if (form) {
            form.addEventListener('submit', function(event) {
                // Only show loading state if form is valid
                if (form.checkValidity()) {
                    button.disabled = true;
                    const originalText = button.innerHTML;
                    button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Processing...';
                    
                    // Store original text for potential restoration
                    button.setAttribute('data-original-text', originalText);
                }
            });
        }
    });

    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Add fade-in animation to cards
    const cards = document.querySelectorAll('.card');
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    cards.forEach(card => {
        observer.observe(card);
    });

    // Highlight today's date in calendar
    const today = new Date();
    const todayString = today.toISOString().split('T')[0];
    const todayElements = document.querySelectorAll(`[data-date="${todayString}"]`);
    todayElements.forEach(element => {
        element.classList.add('border-warning', 'bg-warning', 'bg-opacity-10');
    });

    // Copy to clipboard functionality
    function copyToClipboard(text) {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text).then(function() {
                showToast('Copied to clipboard!', 'success');
            });
        } else {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            try {
                document.execCommand('copy');
                showToast('Copied to clipboard!', 'success');
            } catch (err) {
                showToast('Failed to copy to clipboard', 'error');
            }
            document.body.removeChild(textArea);
        }
    }

    // Toast notifications
    function showToast(message, type = 'info') {
        const toastContainer = getOrCreateToastContainer();
        const toastId = 'toast-' + Date.now();
        const bgClass = type === 'success' ? 'bg-success' : type === 'error' ? 'bg-danger' : 'bg-info';
        
        const toastHTML = `
            <div id="${toastId}" class="toast ${bgClass} text-white" role="alert">
                <div class="toast-header ${bgClass} text-white border-0">
                    <strong class="me-auto">
                        <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'} me-2"></i>
                        Notification
                    </strong>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
                </div>
                <div class="toast-body">
                    ${message}
                </div>
            </div>
        `;
        
        toastContainer.insertAdjacentHTML('beforeend', toastHTML);
        const toastElement = document.getElementById(toastId);
        const toast = new bootstrap.Toast(toastElement, { autohide: true, delay: 3000 });
        toast.show();
        
        // Remove toast element after it's hidden
        toastElement.addEventListener('hidden.bs.toast', function() {
            toastElement.remove();
        });
    }

    function getOrCreateToastContainer() {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            container.style.zIndex = '9999';
            document.body.appendChild(container);
        }
        return container;
    }

    // Add copy buttons to longitude values
    const longitudeValues = document.querySelectorAll('[data-longitude]');
    longitudeValues.forEach(element => {
        element.style.cursor = 'pointer';
        element.title = 'Click to copy';
        element.addEventListener('click', function() {
            copyToClipboard(this.textContent);
        });
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl/Cmd + H for home
        if ((e.ctrlKey || e.metaKey) && e.key === 'h') {
            e.preventDefault();
            window.location.href = '/';
        }
        
        // Escape to close modals/alerts
        if (e.key === 'Escape') {
            const modals = document.querySelectorAll('.modal.show');
            modals.forEach(modal => {
                const bsModal = bootstrap.Modal.getInstance(modal);
                if (bsModal) bsModal.hide();
            });
        }
    });

    // Form auto-save (for longer forms)
    const autoSaveForms = document.querySelectorAll('[data-autosave]');
    autoSaveForms.forEach(form => {
        const formId = form.id || 'anonymous-form';
        
        // Load saved data
        const savedData = localStorage.getItem('form-' + formId);
        if (savedData) {
            try {
                const data = JSON.parse(savedData);
                Object.keys(data).forEach(key => {
                    const field = form.querySelector(`[name="${key}"]`);
                    if (field) field.value = data[key];
                });
            } catch (e) {
                console.warn('Failed to load saved form data:', e);
            }
        }
        
        // Save on change
        form.addEventListener('input', function() {
            const formData = new FormData(form);
            const data = {};
            for (let [key, value] of formData.entries()) {
                data[key] = value;
            }
            localStorage.setItem('form-' + formId, JSON.stringify(data));
        });
        
        // Clear on submit
        form.addEventListener('submit', function() {
            localStorage.removeItem('form-' + formId);
        });
    });

    // Print functionality
    window.printPage = function() {
        window.print();
    };

    // PDF download progress indication
    const pdfDownloadLinks = document.querySelectorAll('a[href*="download"]');
    pdfDownloadLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            const originalText = this.innerHTML;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Generating PDF...';
            this.classList.add('disabled');
            
            // Reset after 5 seconds
            setTimeout(() => {
                this.innerHTML = originalText;
                this.classList.remove('disabled');
            }, 5000);
        });
    });

    console.log('Vedic Astrology Calculator initialized successfully! 🌟');
});

// Utility functions
window.AstroUtils = {
    formatDegrees: function(degrees) {
        const sign = Math.floor(degrees / 30);
        const degInSign = degrees % 30;
        const signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
                      'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'];
        return `${degInSign.toFixed(2)}° ${signs[sign]}`;
    },
    
    getTaraColor: function(taraName) {
        const auspicious = ['Sadhaka Tara', 'Sampat Tara', 'Atimitra Tara'];
        const caution = ['Vipat Tara', 'Pratyari Tara', 'Vadha Tara'];
        
        if (auspicious.includes(taraName)) return 'success';
        if (caution.includes(taraName)) return 'danger';
        return 'secondary';
    },
    
    formatTime: function(dateString) {
        const date = new Date(dateString);
        return date.toLocaleTimeString('en-US', { 
            hour: 'numeric', 
            minute: '2-digit',
            hour12: true 
        });
    }
};

// Add to your existing main.js file

// Raahu Kaal specific functionality
document.addEventListener('DOMContentLoaded', function() {
    // Highlight current Raahu Kaal if it's happening now
    highlightCurrentRaahuKaal();
    
    // Update Raahu Kaal highlighting every minute
    setInterval(highlightCurrentRaahuKaal, 60000);
});

function highlightCurrentRaahuKaal() {
    const now = new Date();
    const raahuKaalElements = document.querySelectorAll('.raahu-kaal-section');
    
    raahuKaalElements.forEach(element => {
        const timeText = element.querySelector('.item-name');
        if (timeText) {
            const timeMatch = timeText.textContent.match(/(\d{1,2}:\d{2} [AP]M) – (\d{1,2}:\d{2} [AP]M)/);
            if (timeMatch) {
                const startTime = parseTime(timeMatch[1]);
                const endTime = parseTime(timeMatch[2]);
                
                if (isCurrentTime(now, startTime, endTime)) {
                    element.classList.add('current-raahu-kaal');
                    element.style.border = '3px solid #DC3545';
                    element.style.animation = 'pulse 2s infinite';
                } else {
                    element.classList.remove('current-raahu-kaal');
                    element.style.border = '';
                    element.style.animation = '';
                }
            }
        }
    });
}

function parseTime(timeString) {
    const [time, meridiem] = timeString.split(' ');
    const [hours, minutes] = time.split(':').map(Number);
    let hour24 = hours;
    
    if (meridiem === 'PM' && hours !== 12) {
        hour24 += 12;
    } else if (meridiem === 'AM' && hours === 12) {
        hour24 = 0;
    }
    
    const today = new Date();
    return new Date(today.getFullYear(), today.getMonth(), today.getDate(), hour24, minutes);
}

function isCurrentTime(now, startTime, endTime) {
    const nowTime = new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours(), now.getMinutes());
    return nowTime >= startTime && nowTime <= endTime;
}

// Add CSS animation for pulsing effect
const style = document.createElement('style');
style.textContent = `
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(220, 53, 69, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(220, 53, 69, 0); }
        100% { box-shadow: 0 0 0 0 rgba(220, 53, 69, 0); }
    }
    
    .current-raahu-kaal {
        background: linear-gradient(135deg, #FFB6C1 0%, #FFE4B5 100%) !important;
    }
`;
document.head.appendChild(style);

// Enhanced navigation functionality
window.AstroNavigation = {
    // Quick navigation to today's panchang
    goToTodaysPanchang: function() {
        window.location.href = '/panchang';
    },
    
    // Quick profile selection
    selectProfile: function(userId) {
        const currentPath = window.location.pathname;
        if (currentPath.includes('panchang')) {
            window.location.href = `/panchang/${userId}`;
        } else if (currentPath.includes('calendar')) {
            window.location.href = `/calendar/${userId}`;
        } else {
            window.location.href = `/profile/${userId}`;
        }
    },
    
    // Format Raahu Kaal times for display
    formatRaahuKaal: function(startTime, endTime) {
        const start = new Date(startTime);
        const end = new Date(endTime);
        const formatter = new Intl.DateTimeFormat('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });
        return `${formatter.format(start)} - ${formatter.format(end)}`;
    }
};

// Add keyboard shortcuts for better navigation
document.addEventListener('keydown', function(e) {
    // Alt + P for Panchang
    if (e.altKey && e.key === 'p') {
        e.preventDefault();
        AstroNavigation.goToTodaysPanchang();
    }
    
    // Alt + H for Home
    if (e.altKey && e.key === 'h') {
        e.preventDefault();
        window.location.href = '/';
    }
});

console.log('Enhanced Vedic Astrology Calculator with Raahu Kaal functionality loaded! 🕉️');