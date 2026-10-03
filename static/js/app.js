/**
 * Main Application Frontend Logic
 * Simple, clean, practical shop-management voice & UI interactions.
 */

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

function initApp() {
    // Global Demo Reset Button
    const btnResetDemo = document.getElementById('btn-reset-demo');
    if (btnResetDemo) {
        btnResetDemo.addEventListener('click', async () => {
            if (!confirm("Reset database to initial sample products & transactions?")) return;
            try {
                const res = await fetch('/api/system/reset-demo', { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    showToast(data.message, 'success');
                    setTimeout(() => window.location.reload(), 800);
                }
            } catch (err) {
                showToast("Failed to reset database", 'error');
            }
        });
    }

    // Voice Console Setup
    if (document.getElementById('mic-btn')) {
        setupVoiceConsole();
    }
}

function setupVoiceConsole() {
    const micBtn = document.getElementById('mic-btn');
    const micStatus = document.getElementById('mic-status-text');
    const globalVoiceStatus = document.getElementById('global-voice-status');
    const liveTranscript = document.getElementById('live-transcript');
    const textForm = document.getElementById('text-command-form');
    const textInput = document.getElementById('command-text-input');
    const btnClearChat = document.getElementById('btn-clear-chat');
    const btnConfirm = document.getElementById('btn-confirm-action');
    const btnCancel = document.getElementById('btn-cancel-action');

    // Voice recognition event callbacks
    window.voiceCtrl.onStatusChangeCallback = (status, errorMsg) => {
        if (status === 'listening') {
            micBtn.classList.add('listening');
            micStatus.textContent = "Listening...";
            micStatus.classList.add('status-listening');
            if (globalVoiceStatus) {
                globalVoiceStatus.classList.add('listening');
                globalVoiceStatus.querySelector('.status-text').textContent = "Listening...";
            }
        } else if (status === 'idle') {
            micBtn.classList.remove('listening');
            micStatus.textContent = "Click microphone to speak";
            micStatus.classList.remove('status-listening');
            if (globalVoiceStatus) {
                globalVoiceStatus.classList.remove('listening');
                globalVoiceStatus.querySelector('.status-text').textContent = "Voice Ready";
            }
        } else if (status === 'error') {
            micBtn.classList.remove('listening');
            micStatus.textContent = errorMsg ? `Mic: ${errorMsg}` : "Microphone unavailable";
            micStatus.classList.remove('status-listening');
            if (globalVoiceStatus) {
                globalVoiceStatus.classList.remove('listening');
                globalVoiceStatus.querySelector('.status-text').textContent = "Mic Error";
            }
        }
    };

    // Live speech transcript stream
    window.voiceCtrl.onTranscriptCallback = (text, isFinal) => {
        if (text) {
            liveTranscript.innerHTML = `<span class="transcript-text">"${escapeHtml(text)}"</span>`;
        }
    };

    // Final speech captured -> process NLP
    window.voiceCtrl.onFinalSpeechCallback = (finalText) => {
        if (finalText && finalText.trim()) {
            handleUserCommand(finalText.trim());
        }
    };

    // Mic button click
    micBtn.addEventListener('click', () => {
        window.voiceCtrl.toggleListening();
    });

    // Text form submit
    textForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const cmd = textInput.value.trim();
        if (cmd) {
            textInput.value = '';
            liveTranscript.innerHTML = `<span class="transcript-text">"${escapeHtml(cmd)}"</span>`;
            handleUserCommand(cmd);
        }
    });

    // Clear history
    if (btnClearChat) {
        btnClearChat.addEventListener('click', () => {
            const feed = document.getElementById('dialogue-feed');
            if (feed) {
                feed.innerHTML = `
                    <div class="dialogue-message assistant-message">
                        <div class="message-bubble">
                            <div class="message-text">Activity cleared. Ready for next command.</div>
                        </div>
                    </div>
                `;
            }
            showToast("Activity cleared", "info");
        });
    }

    // Confirmation Buttons
    if (btnConfirm) {
        btnConfirm.addEventListener('click', () => {
            handleUserCommand("confirm");
        });
    }

    if (btnCancel) {
        btnCancel.addEventListener('click', () => {
            handleUserCommand("cancel");
        });
    }
}

/**
 * Send natural language input to backend and update UI
 */
async function handleUserCommand(text) {
    addActivityItem('user', text);

    try {
        const res = await fetch('/api/voice/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text })
        });

        const data = await res.json();

        // 1. Display assistant message in activity feed
        if (data.message) {
            addActivityItem('assistant', data.message);
        }

        // 2. Speak concisely only when needed (clarifications, confirmations, errors)
        if (data.message && window.voiceCtrl) {
            // Keep spoken message clean and short
            window.voiceCtrl.speak(data.message);
        }

        // 3. Update Extracted Information & Confirmation Card
        updateExtractedCard(data);

        // 4. Toast on successful transaction save
        if (data.transaction_data) {
            showToast(`Saved! Stock: ${data.transaction_data.new_stock} ${data.transaction_data.unit || ''}`, 'success');
        }

    } catch (err) {
        console.error("NLP processing error:", err);
        addActivityItem('assistant', 'Error connecting to server.');
        showToast("Server communication error", "error");
    }
}

/**
 * Update the concise Extracted Information & Confirmation Box
 */
function updateExtractedCard(data) {
    const card = document.getElementById('extracted-info-card');
    const summaryBox = document.getElementById('concise-summary-text');
    const responseBox = document.getElementById('assistant-response-box');
    const responseText = document.getElementById('assistant-response-text');
    const actionsRow = document.getElementById('confirmation-actions-row');

    if (!card) return;

    const ctx = data.context || {};
    const intent = data.intent || ctx.intent;

    // Handle assistant response box (for clarifications or info)
    if (data.message && (data.state !== 'AWAITING_CONFIRMATION' || !data.requires_confirmation)) {
        if (responseBox && responseText) {
            responseText.textContent = data.message;
            responseBox.style.display = 'flex';
        }
    } else if (responseBox) {
        responseBox.style.display = 'none';
    }

    // If we have extracted transaction fields or awaiting confirmation
    if (ctx && (ctx.product || ctx.quantity || ctx.amount || ctx.party_name || ctx.category)) {
        card.style.display = 'block';

        // Format concise summary: e.g. "Rice — 2 kg — ₹200 — Supplier: Arun"
        const parts = [];
        if (ctx.product) parts.push(`<strong>${escapeHtml(ctx.product)}</strong>`);
        if (ctx.quantity != null) {
            const unit = ctx.unit ? ` ${ctx.unit}` : '';
            parts.push(`${ctx.quantity}${unit}`);
        }
        if (ctx.amount != null) parts.push(`₹${ctx.amount}`);
        if (ctx.party_name) {
            const role = (intent === 'PURCHASE') ? 'Supplier' : 'Customer';
            parts.push(`${role}: ${escapeHtml(ctx.party_name)}`);
        }
        if (ctx.category && !ctx.product) parts.push(`Expense: ${escapeHtml(ctx.category)}`);

        summaryBox.innerHTML = parts.join(' <span class="sep">&bull;</span> ');

        // Fill detail fields
        document.getElementById('val-type').textContent = intent || '--';
        document.getElementById('val-product').textContent = ctx.product || (ctx.category ? `[${ctx.category}]` : '--');
        document.getElementById('val-quantity').textContent = ctx.quantity != null ? `${ctx.quantity} ${ctx.unit || ''}`.trim() : '--';
        document.getElementById('val-amount').textContent = ctx.amount != null ? `₹${ctx.amount}` : '--';
        document.getElementById('val-party').textContent = ctx.party_name || '--';

        // Show/hide Confirm | Edit buttons
        if (actionsRow) {
            actionsRow.style.display = (data.requires_confirmation && data.state === 'AWAITING_CONFIRMATION') ? 'flex' : 'none';
        }
    } else {
        // If transaction completed (IDLE) or reset
        card.style.display = 'none';
    }
}

/**
 * Append item to recent activity feed
 */
function addActivityItem(sender, text) {
    const feed = document.getElementById('dialogue-feed');
    if (!feed) return;

    const isUser = sender === 'user';
    const msgDiv = document.createElement('div');
    msgDiv.className = `dialogue-message ${isUser ? 'user-message' : 'assistant-message'}`;

    msgDiv.innerHTML = `
        <div class="message-bubble">
            <div class="message-sender">${isUser ? 'You' : 'Assistant'}</div>
            <div class="message-text">${escapeHtml(text)}</div>
        </div>
    `;

    feed.appendChild(msgDiv);
    feed.scrollTop = feed.scrollHeight;
}

/**
 * Toast Notification Utility
 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let icon = 'fa-circle-info';
    if (type === 'success') icon = 'fa-circle-check';
    else if (type === 'error') icon = 'fa-triangle-exclamation';

    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(6px)';
        toast.style.transition = 'all 0.25s ease';
        setTimeout(() => toast.remove(), 250);
    }, 3000);
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
