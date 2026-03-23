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
import base64 as b64lib_smtp
import sendgrid
from sendgrid.helpers.mail import (
    Mail, Attachment, FileContent, FileName, FileType, Disposition, Cc, Bcc, ReplyTo
)

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

        # Read PDF as base64 so frontend can upload to Firebase Storage
        import base64 as b64resp
        with open(pdf_path, 'rb') as f:
            pdf_base64_resp = b64resp.b64encode(f.read()).decode()

        # Store metadata for later sending
        metadata = {
            "pdf_id": pdf_id,
            "pdf_path": pdf_path,
            "customer_name": data.get("customer_name"),
            "customer_email": data.get("customer_email"),
            "prepared_by_name": data.get("prepared_by_name", ""),
            "prepared_by_email": data.get("prepared_by_email", ""),
            "smtp_password": data.get("smtp_password", ""),
            "firebase_id": data.get("firebaseId", ""),
            "created_at": datetime.now().isoformat()
        }
        
        metadata_path = os.path.join(PDF_DIR, f"{pdf_id}_meta.json")
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f)
        
        return jsonify({
            "success": True,
            "pdf_id": pdf_id,
            "pdf_base64": pdf_base64_resp,
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
        
        # Get optional fields from request
        custom_message = request.json.get("message", "")
        accept_url     = request.json.get("accept_url", "")
        firebase_id    = metadata.get("firebase_id", "")

        # Send email via SendGrid
        send_email_with_pdf(
            to_email=customer_email,
            customer_name=customer_name,
            pdf_path=pdf_path,
            custom_message=custom_message,
            user_email=prepared_by_email,
            user_name=prepared_by_name,
            accept_url=accept_url
        )

        # Save to Google Drive
        filename = f'Toomey_New_Install_{customer_name.replace(" ", "_")}.pdf'
        drive_url = save_pdf_to_drive(pdf_path, 'new_installation', firebase_id, filename)

        return jsonify({
            "success": True,
            "message": f"PDF sent to {customer_email}",
            "driveUrl": drive_url
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


APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxzNihd63pA6DrwLyOzIDh4mWBba_hOLOjROwk54ZlFN_0CN0Rbm9wGUciMV-4KlVd5oQ/exec"

def save_pdf_to_drive(pdf_path, job_type, firebase_id, filename):
    """Save PDF to Google Drive via Apps Script doPost. Returns Drive URL or ''."""
    try:
        import base64 as b64drive
        with open(pdf_path, 'rb') as f:
            pdf_b64 = b64drive.b64encode(f.read()).decode()
        resp = req_lib.post(APPS_SCRIPT_URL, json={
            'action':     'save_pdf',
            'jobType':    job_type,
            'firebaseId': firebase_id,
            'filename':   filename,
            'pdf_base64': pdf_b64
        }, timeout=30)
        result = resp.json()
        return result.get('driveUrl', '')
    except Exception as e:
        print(f'Drive save failed (non-fatal): {e}')
        return ''


def send_email_with_pdf(to_email, customer_name, pdf_path, custom_message="", user_email="", user_name="", user_smtp_password="", subject_override=None, extra_cc=None, attachment_name=None, accept_url=None, job_type=""):
    """Send PDF via email using SendGrid API."""
    api_key = os.environ.get('SENDGRID_API_KEY')
    if not api_key:
        raise Exception("SENDGRID_API_KEY not configured in Railway environment variables.")

    from_email = user_email if user_email else os.environ.get('FROM_EMAIL', 'info@toomeyirrigation.com')
    from_name  = user_name  if user_name  else 'W.L. Toomey Irrigation'
    bcc_email  = os.environ.get('BCC_EMAIL')

    subject = subject_override if subject_override else f"W.L. Toomey Irrigation - Proposal for {customer_name}"

    prepared_by_line_txt  = f"\nPrepared by: {user_name} | {user_email}" if user_name else ""
    prepared_by_line_html = f"<br><em>Prepared by: {user_name} | {user_email}</em>" if user_name else ""
    custom_block_txt  = f"\n{custom_message}\n" if custom_message.strip() else ""
    custom_block_html = f"<p>{custom_message}</p>" if custom_message.strip() else ""

    # New install proposals get a fuller email body; other job types (subject_override set) get a shorter one
    if not subject_override:
        plain_body = f"""Hi {customer_name},

Thank you for the opportunity to provide a proposal for your irrigation system — we appreciate your interest in W.L. Toomey Irrigation!

Please find your personalized proposal attached. It includes a full overview of the recommended system design for your property.
{custom_block_txt}
Here's what to expect next:
  - Review the attached proposal at your convenience
  - If you have any questions or would like to make any adjustments, don't hesitate to reach out
  - When you're ready to move forward, simply reply to this email and we'll get your installation scheduled

We take pride in every system we install and look forward to the opportunity to work with you. Our team is happy to answer any questions along the way.

TO ACCEPT THIS PROPOSAL OR IF YOU HAVE ANY QUESTIONS, PLEASE REPLY DIRECTLY TO THIS EMAIL.

Best regards,
W.L. Toomey Irrigation
(781) 937-0552
www.ToomeyIrrigation.com{prepared_by_line_txt}""".strip()

        html_body = f"""<div style="font-family:Arial,sans-serif;font-size:15px;color:#222;max-width:560px;">
<p>Hi {customer_name},</p>
<p>Thank you for the opportunity to provide a proposal for your irrigation system — we appreciate your interest in W.L. Toomey Irrigation!</p>
<p>Please find your personalized proposal attached. It includes a full overview of the recommended system design for your property.</p>
{custom_block_html}
<p><strong>Here's what to expect next:</strong></p>
<ul style="margin:0 0 16px 0;padding-left:20px;line-height:1.8;">
  <li>Review the attached proposal at your convenience</li>
  <li>If you have any questions or would like to make any adjustments, don't hesitate to reach out</li>
  <li>When you're ready to move forward, simply reply to this email and we'll get your installation scheduled</li>
</ul>
<p>We take pride in every system we install and look forward to the opportunity to work with you. Our team is happy to answer any questions along the way.</p>
<p><strong>To accept this proposal or if you have any questions, please reply directly to this email.</strong></p>
<p>Best regards,<br>
<strong>W.L. Toomey Irrigation</strong><br>
(781) 937-0552<br>
<a href="https://www.ToomeyIrrigation.com">www.ToomeyIrrigation.com</a><br>
{prepared_by_line_html}
</p>
</div>"""

    elif job_type == 'system_recommendations':
        plain_body = f"""Hi {customer_name},

During our recent visit to your property, our technician noticed a few things with your irrigation system worth bringing to your attention.

We've put together a quick proposal outlining our recommendations — these may be improvements, upgrades, or repairs that could help your system run more efficiently or prevent problems down the road. We wanted to make sure you had the information so you can decide what makes sense for you.
{custom_block_txt}
Please find the attached proposal for your review. There's no obligation — if you'd like to move forward with any of the recommendations, or if you have any questions, just reply to this email and we'll take it from there.

Thank you for your continued trust in W.L. Toomey Irrigation.

Best regards,
W.L. Toomey Irrigation
(781) 937-0552
www.ToomeyIrrigation.com{prepared_by_line_txt}""".strip()

        html_body = f"""<div style="font-family:Arial,sans-serif;font-size:15px;color:#222;max-width:560px;">
<p>Hi {customer_name},</p>
<p>During our recent visit to your property, our technician noticed a few things with your irrigation system worth bringing to your attention.</p>
<p>We've put together a quick proposal outlining our recommendations — these may be improvements, upgrades, or repairs that could help your system run more efficiently or prevent problems down the road. We wanted to make sure you had the information so you can decide what makes sense for you.</p>
{custom_block_html}
<p>Please find the attached proposal for your review. There's no obligation — if you'd like to move forward with any of the recommendations, or if you have any questions, just reply to this email and we'll take it from there.</p>
<p>Thank you for your continued trust in W.L. Toomey Irrigation.</p>
<p>Best regards,<br>
<strong>W.L. Toomey Irrigation</strong><br>
(781) 937-0552<br>
<a href="https://www.ToomeyIrrigation.com">www.ToomeyIrrigation.com</a><br>
{prepared_by_line_html}
</p>
</div>"""

    else:
        plain_body = f"""Hi {customer_name},

Please find your W.L. Toomey Irrigation proposal attached.
{custom_block_txt}
TO ACCEPT THIS PROPOSAL OR IF YOU HAVE ANY ADDITIONAL QUESTIONS, PLEASE REPLY DIRECTLY TO THIS EMAIL.

Best regards,
W.L. Toomey Irrigation
(781) 937-0552
www.ToomeyIrrigation.com{prepared_by_line_txt}""".strip()

        html_body = f"""<div style="font-family:Arial,sans-serif;font-size:15px;color:#222;max-width:560px;">
<p>Hi {customer_name},</p>
<p>Please find your W.L. Toomey Irrigation proposal attached.</p>
{custom_block_html}
<p><strong>To accept this proposal or if you have any additional questions, please reply directly to this email.</strong></p>
<p>Best regards,<br>
<strong>W.L. Toomey Irrigation</strong><br>
(781) 937-0552<br>
<a href="https://www.ToomeyIrrigation.com">www.ToomeyIrrigation.com</a><br>
{prepared_by_line_html}
</p>
</div>"""

    message = Mail(
        from_email=(from_email, from_name),
        to_emails=to_email,
        subject=subject,
        plain_text_content=plain_body,
        html_content=html_body
    )

    # Reply-to: both the estimator and the office so customer replies reach both
    office_email_addr = 'info@toomeyirrigation.com'
    reply_to_list = []
    if user_email and user_email != office_email_addr:
        reply_to_list.append(ReplyTo(user_email, user_name or 'W.L. Toomey Irrigation'))
    reply_to_list.append(ReplyTo(office_email_addr, 'W.L. Toomey Irrigation'))
    if len(reply_to_list) == 1:
        message.reply_to = reply_to_list[0]
    else:
        message.reply_to_list = reply_to_list

    if extra_cc and extra_cc != to_email and extra_cc != from_email:
        message.cc = Cc(extra_cc)
    if bcc_email and bcc_email != from_email and bcc_email != to_email and bcc_email != extra_cc:
        message.bcc = Bcc(bcc_email)

    # Attach PDF
    attach_filename = attachment_name or f'Toomey_Irrigation_Proposal_{customer_name.replace(" ", "_")}.pdf'
    with open(pdf_path, 'rb') as f:
        pdf_b64 = b64lib_smtp.b64encode(f.read()).decode()

    message.attachment = Attachment(
        FileContent(pdf_b64),
        FileName(attach_filename),
        FileType('application/pdf'),
        Disposition('attachment')
    )

    sg = sendgrid.SendGridAPIClient(api_key)
    try:
        response = sg.send(message)
        if response.status_code not in [200, 202]:
            raise Exception(f"SendGrid error {response.status_code}: {response.body}")
    except Exception as e:
        # Capture detailed SendGrid error body if available
        if hasattr(e, 'body'):
            raise Exception(f"SendGrid {getattr(e, 'status_code', 'error')}: {e.body}")
        raise


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
        job_type        = data.get('job_type', '')
        job_type_label  = data.get('job_type_label', 'Proposal')
        firebase_id     = data.get('firebase_id', '')
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
            accept_url=accept_url,
            job_type=job_type
        )

        # Save to Google Drive
        drive_url = save_pdf_to_drive(pdf_path, job_type, firebase_id, filename)

        # Clean up temp file
        try:
            os.remove(pdf_path)
        except Exception:
            pass

        return jsonify({"success": True, "message": f"PDF sent to {to_email}", "driveUrl": drive_url})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
