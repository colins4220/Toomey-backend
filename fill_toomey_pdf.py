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

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib import colors
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfbase.pdfmetrics import stringWidth
    except ImportError:
        print("reportlab not available")
        sys.exit(1)

    # PDF page dimensions (from extraction: 612 x 792 points)
    PAGE_W = 612
    PAGE_H = 792

    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    def make_overlay(page_num, fields):
        """Create an overlay PDF page with text and rect fields."""
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=(PAGE_W, PAGE_H))
        c.setFont("Helvetica", 11)
        c.setFillColorRGB(0.1, 0.1, 0.5)  # Dark navy blue to match doc style

        for field in fields:
            # White rectangle (used to cover printed lines)
            if field.get('type') == 'rect':
                r, g, b = field.get('color', (1, 1, 1))
                c.setFillColorRGB(r, g, b)
                ry = PAGE_H - field['y'] - field['height']
                c.rect(field['x'], ry, field['width'], field['height'], fill=1, stroke=0)
                c.setFillColorRGB(0.1, 0.1, 0.5)
                continue
            text = field.get('text', '')
            if not text:
                continue
            x = field['x']
            y = PAGE_H - field['y']
            font_size = field.get('font_size', 11)
            bold = field.get('bold', False)
            c.setFont("Helvetica-Bold" if bold else "Helvetica", font_size)
            c.drawString(x, y, str(text))

        c.save()
        packet.seek(0)
        return PdfReader(packet).pages[0]

    # ---- PAGE 1 FIELDS (Cover page) ----

    customer_name    = data.get('customer_name', '')
    customer_address = data.get('customer_address', '')
    proposal_date    = data.get('date', '')

    # Split address into street + city/state
    addr_parts = [p.strip() for p in customer_address.split(',')]
    if len(addr_parts) >= 2:
        street = addr_parts[0]
        city_raw = ', '.join(addr_parts[1:]).strip()
        # Ensure MA is present
        if 'MA' not in city_raw and 'Massachusetts' not in city_raw:
            city_raw = city_raw + ', MA'
        city_state = city_raw
    else:
        street = customer_address
        city_state = 'MA'

    # Format price with comma: 1234 -> 1,234
    price_raw = data.get('price', '')
    try:
        price_formatted = '{:,.0f}'.format(float(str(price_raw).replace(',', '').replace('$', '')))
    except:
        price_formatted = str(price_raw)

    page1_fields = []

    # "Prepared For" — name, street, city/state all bold
    if customer_name:
        page1_fields.append({'text': customer_name, 'x': 328.5, 'y': 672, 'font_size': 11, 'bold': True})
    if street:
        page1_fields.append({'text': street,        'x': 328.5, 'y': 688, 'font_size': 11, 'bold': True})
    if city_state:
        page1_fields.append({'text': city_state,    'x': 328.5, 'y': 704, 'font_size': 11, 'bold': True})

    # Date — moved up to align with "DATE:" label
    if proposal_date:
        page1_fields.append({'text': proposal_date, 'x': 378, 'y': 750, 'font_size': 11, 'bold': True})

    # ---- PAGE 3 FIELDS (Estimate page) ----

    pgp_ultra      = data.get('hunter_pgp_ultra', '')
    mp_rotor       = data.get('mp_rotor_nozzle', '')
    pro4_spray     = data.get('hunter_pro4_spray', '')
    drip_zones     = data.get('drip_zones', '')
    num_zones      = data.get('number_of_zones', '')
    irritrol_valves= data.get('irritrol_valves', '')
    hydrawise_timer= data.get('hydrawise_timer', '')
    notes          = data.get('notes', '')
    sidewalk_strip = data.get('sidewalk_strip', '')
    other_addon    = data.get('other_addon', '')

    # Calculate total heads
    total_heads = 0
    for val in [pgp_ultra, mp_rotor, pro4_spray]:
        try:
            total_heads += int(val) if val and val != '0' else 0
        except:
            pass

    page3_fields = []

    # Head counts — bigger (14pt) and bold
    if pgp_ultra and pgp_ultra != '0':
        page3_fields.append({'text': str(pgp_ultra), 'x': 190, 'y': 207, 'font_size': 14, 'bold': True})
    if mp_rotor and mp_rotor != '0':
        page3_fields.append({'text': str(mp_rotor),  'x': 190, 'y': 233, 'font_size': 14, 'bold': True})
    if pro4_spray and pro4_spray != '0':
        page3_fields.append({'text': str(pro4_spray),'x': 190, 'y': 260, 'font_size': 14, 'bold': True})
    if total_heads > 0:
        page3_fields.append({'text': str(total_heads),'x': 190, 'y': 290, 'font_size': 14, 'bold': True})

    # Right side fields — bigger (14pt) and bold
    if drip_zones and drip_zones != '0':
        page3_fields.append({'text': str(drip_zones),     'x': 438, 'y': 207, 'font_size': 14, 'bold': True})
    if num_zones and num_zones != '0':
        page3_fields.append({'text': str(num_zones),      'x': 438, 'y': 233, 'font_size': 14, 'bold': True})
    if irritrol_valves and irritrol_valves != '0':
        page3_fields.append({'text': str(irritrol_valves),'x': 438, 'y': 260, 'font_size': 14, 'bold': True})
    if hydrawise_timer:
        page3_fields.append({'text': str(hydrawise_timer),'x': 415, 'y': 290, 'font_size': 14, 'bold': True})

    # Price — formatted with comma
    if price_formatted:
        page3_fields.append({'text': price_formatted, 'x': 320, 'y': 342, 'font_size': 18, 'bold': True})

    # Notes — white rect to cover printed lines, then word-wrapped text
    if notes:
        # Cover the printed note lines with a white rectangle
        page3_fields.append({'type': 'rect', 'x': 10, 'y': 398, 'width': 592, 'height': 145, 'color': (1, 1, 1)})

        note_font  = 'Helvetica'
        note_size  = 10
        max_width  = 582  # x=13 to ~x=595
        line_gap   = 14   # tight single-spacing for font size 10

        def wrap_line(text):
            words = text.split()
            lines = []
            current = ''
            for word in words:
                test = (current + ' ' + word).strip()
                if stringWidth(test, note_font, note_size) <= max_width:
                    current = test
                else:
                    if current:
                        lines.append(current)
                    current = word
            if current:
                lines.append(current)
            return lines

        all_lines = []
        for para in notes.split('\n'):
            if para.strip():
                all_lines.extend(wrap_line(para.strip()))
            else:
                all_lines.append('')

        note_start_y = 408
        for i, line in enumerate(all_lines[:9]):
            y_pos = note_start_y + i * line_gap
            if y_pos > 540:
                break
            if line:
                page3_fields.append({'text': line, 'x': 13, 'y': y_pos, 'font_size': note_size})

    # Add-ons
    if sidewalk_strip:
        page3_fields.append({'text': str(sidewalk_strip), 'x': 138, 'y': 578, 'font_size': 11})
    if other_addon:
        page3_fields.append({'text': str(other_addon),    'x': 80,  'y': 604, 'font_size': 11})

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

    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, 'WLToomeyIrrigationProposal.pdf')

    if not os.path.exists(input_path):
        print(f"ERROR: Template not found at {input_path}")
        print(f"Script directory: {script_dir}")
        print(f"Files in directory: {os.listdir(script_dir)}")
        sys.exit(1)

    print(f"Using template: {input_path}")
    fill_pdf(data, input_path, output_path)
