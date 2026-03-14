"""
W.L. Toomey Irrigation - Backend Server
Generates PDFs from iPad estimates with preview + approval flow
"""
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
import os
import subprocess
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

import requests as req_lib

app = Flask(__name__)
CORS(app)  # Allow requests from iPad

# Directory for temporary PDFs
PDF_DIR = "/tmp/toomey_pdfs"
os.makedirs(PDF_DIR, exist_ok=True)

SHEETS_URL = "https://script.google.com/macros/s/AKfycbxzNihd63pA6DrwLyOzIDh4mWBba_hOLOjROwk54ZlFN_0CN0Rbm9wGUciMV-4KlVd5oQ/exec"

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "toomey-pdf-generator"})

@app.route('/generate-pdf', methods=['POST'])
def generate_pdf():
    """
    Generate PDF from estimate data
    Returns PDF ID for preview/approval flow
    """
    try:
        data = request.json
        
        # Generate unique PDF filename
        pdf_id = f"estimate_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        pdf_path = os.path.join(PDF_DIR, f"{pdf_id}.pdf")
        
        # Check if template exists
        template_path = os.path.join(os.path.dirname(__file__), "WLToomeyIrrigationProposal.pdf")
        if not os.path.exists(template_path):
            print(f"ERROR: Template not found at {template_path}")
            print(f"Current directory: {os.getcwd()}")
            print(f"Files in directory: {os.listdir(os.path.dirname(__file__))}")
            return jsonify({"error": f"PDF template not found at {template_path}"}), 500
        
        print(f"Template found at: {template_path}")
        print(f"Generating PDF with data: {json.dumps(data, indent=2)}")
        
        # Call the fill_toomey_pdf.py script
        result = subprocess.run(
            ['python3', 'fill_toomey_pdf.py', json.dumps(data), pdf_path],
            cwd=os.path.dirname(__file__),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print(f"Script exit code: {result.returncode}")
        print(f"Script stdout: {result.stdout}")
        print(f"Script stderr: {result.stderr}")
        
        if result.returncode != 0:
            error_msg = f"PDF generation failed. Exit code: {result.returncode}. Error: {result.stderr}"
            print(f"ERROR: {error_msg}")
            return jsonify({"error": error_msg, "details": result.stderr}), 500
        
        # Check if PDF was actually created
        if not os.path.exists(pdf_path):
            print(f"ERROR: PDF was not created at {pdf_path}")
            return jsonify({"error": "PDF file was not created"}), 500
        
        print(f"PDF successfully created at: {pdf_path}")
        
        # Store metadata for later sending
        metadata = {
            "pdf_id": pdf_id,
            "pdf_path": pdf_path,
            "customer_name": data.get("customer_name"),
            "customer_email": data.get("customer_email"),
            "prepared_by_name": data.get("prepared_by_name", ""),
            "prepared_by_email": data.get("prepared_by_email", ""),
            "smtp_password": data.get("smtp_password", ""),
            "created_at": datetime.now().isoformat()
        }
        
        metadata_path = os.path.join(PDF_DIR, f"{pdf_id}_meta.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)
        
        return jsonify({
            "success": True,
            "pdf_id": pdf_id,
            "download_url": f"/download-pdf/{pdf_id}",
            "preview_url": f"/preview-pdf/{pdf_id}",
            "customer_name": data.get("customer_name"),
            "customer_email": data.get("customer_email")
        })
        
    except subprocess.TimeoutExpired:
        print("ERROR: PDF generation timed out after 30 seconds")
        return jsonify({"error": "PDF generation timed out"}), 500
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"ERROR: {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": error_msg}), 500

@app.route('/download-pdf/<pdf_id>', methods=['GET'])
def download_pdf(pdf_id):
    """
    Download the generated PDF (for preview on iPad)
    """
    try:
        pdf_path = os.path.join(PDF_DIR, f"{pdf_id}.pdf")
        
        if not os.path.exists(pdf_path):
            return jsonify({"error": "PDF not found"}), 404
        
        return send_file(
            pdf_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"Toomey_Proposal_{pdf_id}.pdf"
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/preview-pdf/<pdf_id>', methods=['GET'])
def preview_pdf(pdf_id):
    """
    Preview PDF in browser (opens in new tab on iPad)
    """
    try:
        pdf_path = os.path.join(PDF_DIR, f"{pdf_id}.pdf")
        
        if not os.path.exists(pdf_path):
            return jsonify({"error": "PDF not found"}), 404
        
        return send_file(pdf_path, mimetype='application/pdf')
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/send-pdf/<pdf_id>', methods=['POST'])
def send_pdf(pdf_id):
    """
    Send approved PDF to client via email
    """
    try:
        pdf_path = os.path.join(PDF_DIR, f"{pdf_id}.pdf")
        metadata_path = os.path.join(PDF_DIR, f"{pdf_id}_meta.json")
        
        if not os.path.exists(pdf_path):
            return jsonify({"error": "PDF not found"}), 404
        
        # Load metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        customer_email = metadata.get("customer_email")
        customer_name = metadata.get("customer_name")
        prepared_by_name = metadata.get("prepared_by_name", "")
        prepared_by_email = metadata.get("prepared_by_email", "")
        smtp_password = metadata.get("smtp_password", "")
        
        if not customer_email:
            return jsonify({"error": "No customer email provided"}), 400
        
        # Get optional custom message from request
        custom_message = request.json.get("message", "")
        
        # Send email with user credentials if provided
        send_email_with_pdf(
            to_email=customer_email,
            customer_name=customer_name,
            pdf_path=pdf_path,
            custom_message=custom_message,
            user_email=prepared_by_email,
            user_name=prepared_by_name,
            user_smtp_password=smtp_password
        )
        
        return jsonify({
            "success": True,
            "message": f"PDF sent to {customer_email}"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/sync-to-sheets', methods=['POST'])
def sync_to_sheets():
    """Forward proposal data to Google Sheets via Apps Script"""
    try:
        data = request.json
        data['action'] = 'submit_proposal'
        resp = req_lib.post(SHEETS_URL, json=data, timeout=15)
        result = resp.json()
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def send_email_with_pdf(to_email, customer_name, pdf_path, custom_message="", user_email="", user_name="", user_smtp_password="", subject_override=None, extra_cc=None, attachment_name=None, accept_url=None):
    """
    Send PDF via email using SMTP.
    If user credentials are provided, use those. Otherwise fall back to environment variables.
    """
    smtp_user = user_email if user_email else os.environ.get('SMTP_USER')
    smtp_password = user_smtp_password if user_smtp_password else os.environ.get('SMTP_PASSWORD')
    from_email = user_email if user_email else os.environ.get('FROM_EMAIL', smtp_user)

    smtp_host = os.environ.get('SMTP_HOST', 'smtp.office365.com')
    smtp_port = int(os.environ.get('SMTP_PORT', 587))
    bcc_email = os.environ.get('BCC_EMAIL')  # Optional BCC to company email

    if not smtp_user or not smtp_password:
        raise Exception("Email credentials not configured. Set SMTP_USER and SMTP_PASSWORD environment variables or provide user credentials.")

    # Create message
    msg = MIMEMultipart()
    msg['From'] = f"{user_name} <{from_email}>" if user_name else from_email
    msg['To'] = to_email
    msg['Subject'] = subject_override if subject_override else f"W.L. Toomey Irrigation - Proposal for {customer_name}"

    if bcc_email and bcc_email != from_email:
        msg['Bcc'] = bcc_email

    if extra_cc and extra_cc != from_email and extra_cc != to_email:
        msg['Cc'] = extra_cc

    prepared_by_line = f"\n\nPrepared by: {user_name}\n{user_email}" if user_name else ""
    custom_block = f"\n{custom_message}\n" if custom_message.strip() else ""
    accept_block = f"\n\nTo accept this proposal, click here:\n{accept_url}\n" if accept_url else ""

    body = f"""Hi {customer_name},

Please find your W.L. Toomey Irrigation proposal attached.
{custom_block}{accept_block}
If you have any questions, please don't hesitate to reach out.

Best regards,
W.L. Toomey Irrigation
(781) 937-0552
www.ToomeyIrrigation.com{prepared_by_line}""".strip()

    msg.attach(MIMEText(body, 'plain'))

    # Attach PDF
    attach_filename = attachment_name or f'Toomey_Irrigation_Proposal_{customer_name.replace(" ", "_")}.pdf'
    with open(pdf_path, 'rb') as f:
        pdf_attachment = MIMEApplication(f.read(), _subtype='pdf')
        pdf_attachment.add_header('Content-Disposition', 'attachment', filename=attach_filename)
        msg.attach(pdf_attachment)

    # Send email (10s timeout so Railway doesn't hang and 502)
    with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        recipients = [to_email]
        if bcc_email and bcc_email != from_email:
            recipients.append(bcc_email)
        if extra_cc and extra_cc not in recipients:
            recipients.append(extra_cc)
        server.sendmail(from_email, recipients, msg.as_string())


@app.route('/send-job-pdf', methods=['POST'])
def send_job_pdf():
    """
    Receive a client-generated PDF (base64 encoded) and send it via email.
    Used for Re-Vamp, Service Call, and System Recommendations job types.
    """
    try:
        import base64 as b64lib
        data = request.json
        pdf_base64      = data.get('pdf_base64', '')
        filename        = data.get('filename', 'Toomey_Proposal.pdf')
        to_email        = data.get('to_email', '')
        customer_name   = data.get('customer_name', 'Customer')
        job_type_label  = data.get('job_type_label', 'Proposal')
        prepared_by_name  = data.get('prepared_by_name', '')
        prepared_by_email = data.get('prepared_by_email', '')
        smtp_password   = data.get('smtp_password', '')
        message         = data.get('message', '')
        cc_office       = data.get('cc_office', True)
        accept_url      = data.get('accept_url', None)

        if not to_email:
            return jsonify({"error": "No customer email provided"}), 400
        if not pdf_base64:
            return jsonify({"error": "No PDF data provided"}), 400

        # Decode base64 PDF and write to temp file
        pdf_bytes = b64lib.b64decode(pdf_base64)
        pdf_id    = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        pdf_path  = os.path.join(PDF_DIR, f"{pdf_id}.pdf")
        with open(pdf_path, 'wb') as f:
            f.write(pdf_bytes)

        subject = f"W.L. Toomey Irrigation - {job_type_label} for {customer_name}"
        office_email = "info@toomeyirrigation.com" if cc_office else None

        send_email_with_pdf(
            to_email=to_email,
            customer_name=customer_name,
            pdf_path=pdf_path,
            custom_message=message,
            user_email=prepared_by_email,
            user_name=prepared_by_name,
            user_smtp_password=smtp_password,
            subject_override=subject,
            extra_cc=office_email,
            attachment_name=filename,
            accept_url=accept_url
        )

        # Clean up temp file
        try:
            os.remove(pdf_path)
        except Exception:
            pass

        return jsonify({"success": True, "message": f"PDF sent to {to_email}"})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
