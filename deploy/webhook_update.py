"""
GitHub Webhook handler for automatic deployments
"""
import hashlib
import hmac
import json
import subprocess
import logging
from flask import Flask, request, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
WEBHOOK_SECRET = "your-webhook-secret"  # Set this in GitHub webhook settings
UPDATE_SCRIPT = "/home/ubuntu/expanse-telegram-bot/deploy/auto_update.sh"


def verify_webhook_signature(payload_body, signature_header):
    """Verify that the webhook is from GitHub"""
    if not signature_header:
        return False
    
    hash_object = hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        msg=payload_body,
        digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)


@app.route('/webhook', methods=['POST'])
def github_webhook():
    """Handle GitHub webhook for auto-deployment"""
    # Verify signature
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_webhook_signature(request.data, signature):
        logger.warning("Invalid webhook signature")
        return jsonify({'error': 'Invalid signature'}), 401
    
    # Parse event
    event = request.headers.get('X-GitHub-Event')
    payload = request.json
    
    # Handle push events to main branch
    if event == 'push' and payload.get('ref') == 'refs/heads/main':
        logger.info("Received push to main branch. Starting update...")
        
        # Run update script
        try:
            result = subprocess.run(
                ['/bin/bash', UPDATE_SCRIPT],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode == 0:
                logger.info("Update completed successfully")
                return jsonify({
                    'status': 'success',
                    'message': 'Update completed',
                    'output': result.stdout
                }), 200
            else:
                logger.error(f"Update failed: {result.stderr}")
                return jsonify({
                    'status': 'error',
                    'message': 'Update failed',
                    'error': result.stderr
                }), 500
                
        except subprocess.TimeoutExpired:
            logger.error("Update script timeout")
            return jsonify({
                'status': 'error',
                'message': 'Update timeout'
            }), 500
        except Exception as e:
            logger.error(f"Update error: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500
    
    return jsonify({'status': 'ignored'}), 200


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000)