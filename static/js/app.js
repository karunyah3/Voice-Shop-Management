/**
 * Main Application Frontend Logic
 * Orchestrates NLP responses, conversation feed, confidence visualizer, and UI state.
 */

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

function initApp() {
    // 1. Setup Global Demo Reset Button
    const btnResetDemo = document.getElementById('btn-reset-demo');
    if (btnResetDemo) {
        btnResetDemo.addEventListener('click', async () => {
            if (!confirm("Reset shop database to initial sample products & transactions?")) return;
            try {
                const res = await fetch('/api/system/reset-demo', { method: 'POST' });
                const data = await res.json();
                if (data.success) {
                    showToast(data.message, 'success');
                    setTimeout(() => window.location.reload(), 800);
                }
            } catch (err) {
                showToast("Failed to reset demo database", 'error');
            }
        });
    }

    // 2. Setup Voice & Assistant Console (if on Home / Voice Page)
    if (document.getElementById('mic-btn')) {
        setupVoiceConsole();
    }
}

function setupVoiceConsole() {
    const micBtn = document.getElementById('mic-btn');
    const visualizer = document.getElementById('visualizer-container');
    const micStatus = document.getElementById('mic-status-text');
    const globalVoiceStatus = document.getElementById('global-voice-status');
    const liveTranscript = document.getElementById('live-transcript');
    const textForm = document.getElementById('text-command-form');
    const textInput = document.getElementById('command-text-input');
    const ttsToggle = document.getElementById('btn-toggle-tts');
    const ttsLabel = document.getElementById('tts-label');
    const ttsIcon = document.getElementById('tts-icon');
    const btnClearChat = document.getElementById('btn-clear-chat');
    const btnResetCtx = document.getElementById('btn-reset-context');
    const btnConfirm = document.getElementById('btn-confirm-action');
    const btnCancel = document.getElementById('btn-cancel-action');

    // Voice status callback
    window.voiceCtrl.onStatusChangeCallback = (status, errorMsg) => {
        if (status === 'listening') {
            visualizer.classList.add('listening');
            micStatus.textContent = "Listening... Speak your command clearly";
            micStatus.classList.add('text-danger');
            if (globalVoiceStatus) {
                globalVoiceStatus.classList.add('listening');
                globalVoiceStatus.querySelector('.status-text').textContent = "Listening...";
            }
        } else if (status === 'idle') {
            visualizer.classList.remove('listening');
            micStatus.textContent = "Click microphone or use text input below";
            micStatus.classList.remove('text-danger');
            if (globalVoiceStatus) {
                globalVoiceStatus.classList.remove('listening');
                globalVoiceStatus.querySelector('.status-text').textContent = "Voice Ready";
            }
        } else if (status === 'error') {
            visualizer.classList.remove('listening');
            micStatus.textContent = `Mic Error: ${errorMsg || 'Permission denied'}`;
            showToast(`Voice Error: ${errorMsg || 'Speech recognition unavailable'}`, 'error');
        }
    };

    // Live speech transcript stream
    window.voiceCtrl.onTranscriptCallback = (text, isFinal) => {
        liveTranscript.innerHTML = `<strong>"${text}"</strong>`;
    };

    // Final speech captured
    window.voiceCtrl.onFinalSpeechCallback = (finalText) => {
        if (finalText) {
            handleUserCommand(finalText);
        }
    };

    // Mic button click
    micBtn.addEventListener('click', () => {
        window.voiceCtrl.toggleListening();
    });

    // Form text input submit
    textForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const cmd = textInput.value.trim();
        if (cmd) {
            textInput.value = '';
            liveTranscript.innerHTML = `<strong>"${cmd}"</strong>`;
            handleUserCommand(cmd);
        }
    });

    // Quick chips
    document.querySelectorAll('.chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const cmd = chip.dataset.cmd;
            liveTranscript.innerHTML = `<strong>"${cmd}"</strong>`;
            handleUserCommand(cmd);
        });
    });

    // TTS Toggle
    ttsToggle.addEventListener('click', () => {
        window.voiceCtrl.ttsEnabled = !window.voiceCtrl.ttsEnabled;
        if (window.voiceCtrl.ttsEnabled) {
            ttsLabel.textContent = "Voice Speech: Enabled";
            ttsIcon.className = "fa-solid fa-volume-high";
            showToast("Voice speech feedback enabled", "info");
        } else {
            ttsLabel.textContent = "Voice Speech: Muted";
            ttsIcon.className = "fa-solid fa-volume-xmark";
            showToast("Voice speech feedback muted", "info");
        }
    });

    // Clear history
    btnClearChat.addEventListener('click', () => {
        const feed = document.getElementById('dialogue-feed');
        feed.innerHTML = `
            <div class="dialogue-message assistant-message">
                <div class="message-avatar"><i class="fa-solid fa-robot"></i></div>
                <div class="message-bubble">
                    <div class="message-sender">Shop Assistant</div>
                    <div class="message-text">Chat stream cleared. Ready for your next command!</div>
                    <div class="message-time">Just now</div>
                </div>
            </div>
        `;
        showToast("Conversation stream cleared", "info");
    });

    // Reset Context State
    btnResetCtx.addEventListener('click', async () => {
        try {
            const res = await fetch('/api/voice/reset', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                updateNLPTrace({
                    intent: "UNKNOWN",
                    confidence: 0,
                    confidence_status: "LOW",
                    confidence_factors: ["Context reset to Idle state"],
                    state: "IDLE",
                    context: null,
                    requires_confirmation: false
                });
                addDialogueMessage('assistant', 'Dialogue state machine reset to IDLE.');
                showToast("Context state reset", "info");
            }
        } catch (err) {
            showToast("Error resetting context", "error");
        }
    });

    // Confirmation Buttons
    btnConfirm.addEventListener('click', () => {
        handleUserCommand("confirm");
    });

    btnCancel.addEventListener('click', () => {
        handleUserCommand("cancel");
    });
}

/**
 * Send user command to Flask NLP processor and update the interface
 */
async function handleUserCommand(text) {
    // 1. Add user message to conversation feed
    addDialogueMessage('user', text);

    try {
        const res = await fetch('/api/voice/process', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text })
        });

        const data = await res.json();

        // 2. Add assistant response to feed
        addDialogueMessage('assistant', data.message || "Processed");

        // 3. Spoken Audio Feedback (TTS)
        if (data.message) {
            window.voiceCtrl.speak(data.message);
        }

        // 4. Update Explainable NLP Inspection Panel
        updateNLPTrace(data);

        // 5. Toast notification on successful commit
        if (data.transaction_data) {
            showToast(`Transaction saved! New stock: ${data.transaction_data.new_stock}`, 'success');
        }

    } catch (err) {
        console.error("API error:", err);
        addDialogueMessage('assistant', 'Sorry, an error occurred while connecting to the NLP server.');
        showToast("Server connection error", "error");
    }
}

/**
 * Append message bubble to conversation stream
 */
function addDialogueMessage(sender, text) {
    const feed = document.getElementById('dialogue-feed');
    if (!feed) return;

    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const isUser = sender === 'user';

    const msgDiv = document.createElement('div');
    msgDiv.className = `dialogue-message ${isUser ? 'user-message' : 'assistant-message'}`;
    
    msgDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fa-solid ${isUser ? 'fa-user' : 'fa-robot'}"></i>
        </div>
        <div class="message-bubble">
            <div class="message-sender">${isUser ? 'You (Shopkeeper)' : 'Shop Assistant'}</div>
            <div class="message-text">${text.replace(/\n/g, '<br>')}</div>
            <div class="message-time">${timeStr}</div>
        </div>
    `;

    feed.appendChild(msgDiv);
    feed.scrollTop = feed.scrollHeight;
}

/**
 * Update the Right NLP Inspection Panel with Explainable Data
 */
function updateNLPTrace(data) {
    // 1. Intent Badge
    const intentEl = document.getElementById('trace-intent');
    const intent = data.intent || (data.context ? data.context.intent : 'UNKNOWN') || 'UNKNOWN';
    let intentClass = 'intent-unknown';
    
    if (intent === 'PURCHASE') intentClass = 'intent-purchase';
    else if (intent === 'SALE') intentClass = 'intent-sale';
    else if (intent === 'EXPENSE') intentClass = 'intent-expense';
    else if (intent.includes('QUERY')) intentClass = 'intent-query';

    intentEl.innerHTML = `<span class="intent-badge ${intentClass}">${intent}</span>`;

    // 2. Dialogue State Pill
    const statePill = document.getElementById('current-state-pill');
    const state = data.state || 'IDLE';
    statePill.textContent = `State: ${state}`;
    statePill.className = 'state-pill';
    if (state === 'IDLE') statePill.classList.add('state-idle');
    else if (state === 'AWAITING_CONFIRMATION') statePill.classList.add('state-ready');
    else statePill.classList.add('state-awaiting');

    // 3. Explainable Confidence Meter
    const score = data.confidence || 0.0;
    const percent = Math.round(score * 100);
    const meterFill = document.getElementById('confidence-meter-fill');
    const percentText = document.getElementById('confidence-percentage');
    const factorsBox = document.getElementById('confidence-factors-box');

    percentText.textContent = `${percent}% (${data.confidence_status || 'LOW'})`;
    meterFill.style.width = `${percent}%`;

    if (score >= 0.80) {
        meterFill.style.background = 'var(--success-gradient)';
    } else if (score >= 0.50) {
        meterFill.style.background = 'var(--warning-gradient)';
    } else {
        meterFill.style.background = 'var(--danger-gradient)';
    }

    // Factors list
    const factors = data.confidence_factors || [];
    if (factors.length) {
        factorsBox.innerHTML = factors.map(f => `<div class="factor-item">${f}</div>`).join('');
    } else {
        factorsBox.innerHTML = `<div class="factor-item text-muted">Awaiting input...</div>`;
    }

    // 4. Extracted Entities
    const ctx = data.context || {};
    document.getElementById('slot-product').textContent = ctx.product || '--';
    document.getElementById('slot-quantity').textContent = ctx.quantity != null ? ctx.quantity : '--';
    document.getElementById('slot-unit').textContent = ctx.unit || '--';
    document.getElementById('slot-amount').textContent = ctx.amount != null ? `₹${ctx.amount}` : '--';
    document.getElementById('slot-party').textContent = ctx.party_name || '--';
    document.getElementById('slot-category').textContent = ctx.category || '--';

    // 5. Context Memory
    const missingEl = document.getElementById('ctx-missing-slots');
    const missing = ctx.missing_slots || [];
    if (missing.length > 0) {
        missingEl.textContent = missing.join(', ');
        missingEl.className = 'context-val text-warning';
    } else {
        missingEl.textContent = 'None (Complete)';
        missingEl.className = 'context-val text-success';
    }

    document.getElementById('ctx-last-prompt').textContent = ctx.last_prompt || 'None';
    document.getElementById('ctx-raw-text').textContent = ctx.raw_input || '--';

    // 6. Smart Confirmation Card Toggle
    const confirmCard = document.getElementById('confirmation-card');
    const confirmPrompt = document.getElementById('confirmation-prompt-text');
    const confirmSummary = document.getElementById('confirmation-summary-box');

    if (data.requires_confirmation && data.state === 'AWAITING_CONFIRMATION') {
        confirmCard.style.display = 'block';
        confirmPrompt.textContent = data.message;
        
        let summaryHtml = `<strong>Type:</strong> ${ctx.intent} | `;
        if (ctx.product) summaryHtml += `<strong>Product:</strong> ${ctx.product} | `;
        if (ctx.quantity) summaryHtml += `<strong>Qty:</strong> ${ctx.quantity} ${ctx.unit || ''} | `;
        if (ctx.amount) summaryHtml += `<strong>Amount:</strong> ₹${ctx.amount} | `;
        if (ctx.party_name) summaryHtml += `<strong>Party:</strong> ${ctx.party_name} | `;
        if (ctx.category) summaryHtml += `<strong>Category:</strong> ${ctx.category}`;
        
        confirmSummary.innerHTML = summaryHtml;
    } else {
        confirmCard.style.display = 'none';
    }
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

    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}
