from flask import Blueprint, request, jsonify
from services.gmail_scanner import scan_emails

scanner = Blueprint('scanner', __name__)

@scanner.route('/scan', methods=['POST'])
def scan():

    data = request.json

    emails = data.get('emails')

    results = scan_emails(emails)

    return jsonify(results)