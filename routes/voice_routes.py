"""
Voice and NLP API endpoints.
Provides endpoints for audio/text processing, confirmations, cancellations, and session context.
"""
from flask import Blueprint, request, jsonify, session
from nlp.processor import NLPProcessor
import uuid

voice_bp = Blueprint('voice', __name__, url_prefix='/api/voice')

def get_session_id() -> str:
    """Retrieve or initialize browser session ID."""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']

@voice_bp.route('/process', methods=['POST'])
def process_voice_input():
    """
    Process speech-to-text transcript or natural language text command.
    Request body: { "text": "...", "session_id": "optional-uuid" }
    """
    data = request.get_json(force=True, silent=True) or {}
    text = data.get('text', '').strip()
    session_id = data.get('session_id') or get_session_id()

    if not text:
        return jsonify({
            "success": False,
            "message": "Empty voice or text command received.",
            "confidence": 0.0,
            "confidence_status": "LOW",
            "confidence_factors": ["No input provided"]
        }), 400

    processor = NLPProcessor(session_id=session_id)
    response = processor.process_input(text)
    return jsonify(response)

@voice_bp.route('/confirm', methods=['POST'])
def confirm_pending():
    """Explicit endpoint to confirm a pending transaction."""
    data = request.get_json(force=True, silent=True) or {}
    session_id = data.get('session_id') or get_session_id()
    
    processor = NLPProcessor(session_id=session_id)
    response = processor.process_input("confirm")
    return jsonify(response)

@voice_bp.route('/cancel', methods=['POST'])
def cancel_pending():
    """Explicit endpoint to cancel and discard a pending transaction."""
    data = request.get_json(force=True, silent=True) or {}
    session_id = data.get('session_id') or get_session_id()
    
    processor = NLPProcessor(session_id=session_id)
    response = processor.process_input("cancel")
    return jsonify(response)

@voice_bp.route('/context', methods=['GET'])
def get_current_context():
    """Retrieve current pending context for session."""
    session_id = request.args.get('session_id') or get_session_id()
    processor = NLPProcessor(session_id=session_id)
    ctx = processor.context_mgr.get_context()
    return jsonify({
        "session_id": session_id,
        "context": ctx.to_dict()
    })

@voice_bp.route('/reset', methods=['POST'])
def reset_voice_context():
    """Reset session context to IDLE."""
    data = request.get_json(force=True, silent=True) or {}
    session_id = data.get('session_id') or get_session_id()
    processor = NLPProcessor(session_id=session_id)
    ctx = processor.context_mgr.reset_context()
    return jsonify({
        "success": True,
        "message": "Voice context has been reset to Idle.",
        "context": ctx.to_dict()
    })
