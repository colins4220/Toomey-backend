#!/usr/bin/env python3
"""
Fill the W.L. Toomey Irrigation proposal PDF with estimate data.
Usage: python fill_toomey_pdf.py '<json_data>' <output_path>
"""
import sys
import json
import os
from pypdf import PdfReader, PdfWriter

import io

def fill_pdf(data: dict, input_pdf: str, output_pdf: str):
    """Fill the Toomey PDF with the provided data."""
    
    # Use reportlab to create overlay pages with text annotations
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        print("reportlab not available")
        sys.exit(1)
    
    # PDF page dimensions (from extraction: 612 x 792 points)
    PAGE_W = 612
    PAGE_H = 792
    
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    
    def make_overlay(page_num, fields):
        """Create an overlay PDF page with text fields."""
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(PAGE_W, PAGE_H))
        c.setFont("Helvetica", 11)
        c.setFillColorRGB(0.1, 0.1, 0.5)  # Dark navy blue to match doc style
        
        for field in fields:
            text = field.get('text', '')
            if not text:
                continue
            x = field['x']
            # Convert from top-based to bottom-based (reportlab uses bottom-origin)
            y = PAGE_H - field['y']
            font_size = field.get('font_size', 11)
            bold = field.get('bold', False)
            c.setFont("Helvetica-Bold" if bold else "Helvetica", font_size)
            c.drawString(x, y, str(text))
        
        c.save()
        packet.seek(0)
        return PdfReader(packet).pages[0]
    
    # ---- PAGE 1 FIELDS (Cover page) ----
    # "PREPARED FOR:" label is at top=638.3
    # Customer name should appear after "PREPARED FOR:" 
    # Date label is at top=746.3, x0=328.5
    
    customer_name = data.get('customer_name', '')
    customer_address = data.get('customer_address', '')
    customer_email = data.get('customer_email', '')
    proposal_date = data.get('date', '')
    
    # Build prepared_for text
    prepared_for_parts = []
    if customer_name:
        prepared_for_parts.append(customer_name)
    if customer_address:
        prepared_for_parts.append(customer_address)
    
    page1_fields = []
    
    # "Prepared For" - customer name and address below the "PREPARED FOR:" label
    if customer_name:
        page1_fields.append({'text': customer_name, 'x': 328.5, 'y': 672, 'font_size': 11, 'bold': True})
    if customer_address:
        page1_fields.append({'text': customer_address, 'x': 328.5, 'y': 688, 'font_size': 10})

    # "DATE:" label at top=746.3 → place date to the right of it, bold
    if proposal_date:
        page1_fields.append({'text': proposal_date, 'x': 378, 'y': 758, 'font_size': 11, 'bold': True})
    
    # ---- PAGE 3 FIELDS (Estimate page) ----
    # From structure:
    # Hunter PGP-Ultra: label ends ~x1=167.3, top=198.2
    # MP-Rotor Nozzle: label ends ~x1=165.7, top=224.6
    # Hunter Pro-4 Spray: label ends ~x1=166.1, top=251.1
    # Total Heads: label ends ~x1=169.3, top=281.7
    # Drip Zones: label ends ~x1=411.8, top=198.2
    # Number of Zones: label ends ~x1=412.6, top=224.7
    # Irritrol 2400T Valves: label ends ~x1=416.7, top=251.2
    # HydraWise WiFi Timer: label ends ~x1=418.7, top=281.7
    # Price: $ label at top=326.9 ~x1=292.8
    # Notes: lines starting around top=406-500
    # Sidewalk Strip: label ends ~x1=131.6, top=576.5
    # Other: label ends ~x1=72.5, top=601.8
    
    pgp_ultra = data.get('hunter_pgp_ultra', '')
    mp_rotor = data.get('mp_rotor_nozzle', '')
    pro4_spray = data.get('hunter_pro4_spray', '')
    drip_zones = data.get('drip_zones', '')
    num_zones = data.get('number_of_zones', '')
    irritrol_valves = data.get('irritrol_valves', '')
    hydrawise_timer = data.get('hydrawise_timer', '')
    price = data.get('price', '')
    notes = data.get('notes', '')
    sidewalk_strip = data.get('sidewalk_strip', '')
    other_addon = data.get('other_addon', '')
    
    # Calculate total heads
    total_heads = 0
    try:
        total_heads += int(pgp_ultra) if pgp_ultra and pgp_ultra != '0' else 0
    except:
        pass
    try:
        total_heads += int(mp_rotor) if mp_rotor and mp_rotor != '0' else 0
    except:
        pass
    try:
        total_heads += int(pro4_spray) if pro4_spray and pro4_spray != '0' else 0
    except:
        pass
    
    page3_fields = []
    
    # Head counts - only show non-zero values, aligned to label baselines
    if pgp_ultra and pgp_ultra != '0':
        page3_fields.append({'text': str(pgp_ultra), 'x': 190, 'y': 207, 'font_size': 11})
    if mp_rotor and mp_rotor != '0':
        page3_fields.append({'text': str(mp_rotor), 'x': 190, 'y': 233, 'font_size': 11})
    if pro4_spray and pro4_spray != '0':
        page3_fields.append({'text': str(pro4_spray), 'x': 190, 'y': 260, 'font_size': 11})
    if total_heads > 0:
        page3_fields.append({'text': str(total_heads), 'x': 190, 'y': 290, 'font_size': 11, 'bold': True})

    # Right side fields - only show non-zero values
    if drip_zones and drip_zones != '0':
        page3_fields.append({'text': str(drip_zones), 'x': 438, 'y': 207, 'font_size': 11})
    if num_zones and num_zones != '0':
        page3_fields.append({'text': str(num_zones), 'x': 438, 'y': 233, 'font_size': 11})
    if irritrol_valves and irritrol_valves != '0':
        page3_fields.append({'text': str(irritrol_valves), 'x': 438, 'y': 260, 'font_size': 11})
    if hydrawise_timer:
        page3_fields.append({'text': str(hydrawise_timer), 'x': 438, 'y': 290, 'font_size': 11})

    # Price - larger, bold, on the line
    if price:
        page3_fields.append({'text': str(price), 'x': 320, 'y': 350, 'font_size': 18, 'bold': True})
    
    # Notes - can be multi-line, placed on note lines
    if notes:
        # Notes lines start around top=406, 450, 480, 510
        note_lines = notes.split('\n') if '\n' in notes else [notes[i:i+80] for i in range(0, len(notes), 80)]
        note_y_positions = [410, 460, 490, 520]
        for i, line in enumerate(note_lines[:4]):
            if line.strip():
                page3_fields.append({'text': line.strip(), 'x': 13, 'y': note_y_positions[i], 'font_size': 10})
    
    # Add-ons
    if sidewalk_strip:
        page3_fields.append({'text': str(sidewalk_strip), 'x': 138, 'y': 578, 'font_size': 11})
    if other_addon:
        page3_fields.append({'text': str(other_addon), 'x': 80, 'y': 604, 'font_size': 11})
    
    # Build the output PDF
    for i, page in enumerate(reader.pages):
        page_num = i + 1
        
        if page_num == 1 and page1_fields:
            overlay = make_overlay(page_num, page1_fields)
            page.merge_page(overlay)
        elif page_num == 3 and page3_fields:
            overlay = make_overlay(page_num, page3_fields)
            page.merge_page(overlay)
        
        writer.add_page(page)
    
    with open(output_pdf, 'wb') as f:
        writer.write(f)
    
    print(f"PDF saved to {output_pdf}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python fill_toomey_pdf.py '<json>' <output.pdf>")
        sys.exit(1)
    
    data = json.loads(sys.argv[1])
    output_path = sys.argv[2]
    
    # Find the PDF template in the same directory as this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, 'WLToomeyIrrigationProposal.pdf')
    
    # Check if template exists
    if not os.path.exists(input_path):
        print(f"ERROR: Template not found at {input_path}")
        print(f"Script directory: {script_dir}")
        print(f"Files in directory: {os.listdir(script_dir)}")
        sys.exit(1)
    
    print(f"Using template: {input_path}")
    fill_pdf(data, input_path, output_path)
