import os
import json
import gspread
import pandas as pd
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import smtplib
import sys
from email.message import EmailMessage

# --- 1. CONFIGURATIE VIA GITHUB SECRETS ---
def get_gspread_client():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    creds_dict = json.loads(creds_json)
    return gspread.service_account_from_dict(creds_dict)

GOOGLE_SHEET_ID = '1oNNkeY5Uzgna7F3D2ZDIMbdEWwZL7mTxwPt9kR-p6Ow'
TABBLAD_NAAM = 'Seizoen 25 - 26'

EMAIL_AFZENDER = os.environ.get("GMAIL_USER")
EMAIL_WACHTWOORD = os.environ.get("GMAIL_PASSWORD")
# Enkel Johan voor de testfase
EMAIL_ONTVANGERS = ["johan.jouck@hotmail.com"]

LOGO_PAD = "logo.png" 
MAANDEN_NL = {1: "JANUARI", 2: "FEBRUARI", 3: "MAART", 4: "APRIL", 5: "MEI", 6: "JUNI", 7: "JULI", 8: "AUGUSTUS", 9: "SEPTEMBER", 10: "OKTOBER", 11: "NOVEMBER", 12: "DECEMBER"}

# Kleuren
CLR_BG = (15, 23, 42)      
CLR_CARD = (30, 41, 59)    
CLR_ACCENT = (250, 204, 21) 
CLR_W = (34, 197, 94)      
CLR_G = (249, 115, 22)     
CLR_V = (239, 68, 68)      
CLR_TEXT = (241, 245, 249)

def verstuur_mail(bestandsnaam, pad, maand_naam):
    print(f">>> Versturen naar {EMAIL_ONTVANGERS}...")
    msg = EmailMessage()
    msg['Subject'] = f"📊 Maandrapport FC Ambras: {maand_naam}"
    msg['From'] = EMAIL_AFZENDER
    msg['To'] = ", ".join(EMAIL_ONTVANGERS)
    
    msg.set_content(f"Dag Johan,\n\nHierbij het volledige grafische maandrapport van {maand_naam}.\n\nFC Ambras is wereldklas!\n\nMet sportieve groet,\nAmbrasbot")

    with open(pad, 'rb') as f:
        msg.add_attachment(f.read(), maintype='image', subtype='png', filename=bestandsnaam)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_AFZENDER, EMAIL_WACHTWOORD)
            smtp.send_message(msg)
        print(">>> E-MAIL SUCCESVOL VERZONDEN! 🚀")
    except Exception as e:
        print(f"!!! FOUT BIJ MAILEN: {e}")

def genereer_maandrapport():
    print(">>> Start genereren volledig rapport...")
    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(GOOGLE_SHEET_ID)
        worksheet = sh.worksheet(TABBLAD_NAAM)
        data = worksheet.get_all_values()
        df = pd.DataFrame(data[1:], columns=data[0])
    except Exception as e:
        print(f"!!! DATA-FOUT: {e}"); return

    # Tijdslogica
    nu = datetime.now()
    vorige_maand_datum = nu.replace(day=1) - timedelta(days=1)
    rapport_maand_getal = vorige_maand_datum.month
    rapport_jaar = vorige_maand_datum.year
    rapport_maand_naam = MAANDEN_NL[rapport_maand_getal]

    start_rapport = vorige_maand_datum.replace(day=1, hour=0, minute=0, second=0)
    eind_rapport = vorige_maand_datum.replace(hour=23, minute=59, second=59)
    
    start_programma = nu.replace(day=1, hour=0, minute=0, second=0)
    eind_programma = (start_programma + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)

    # Data Verwerken
    df['Datum'] = pd.to_datetime(df['Datum'], dayfirst=True, errors='coerce')
    df['goals'] = pd.to_numeric(df['goals'], errors='coerce')
    df['goals tegen'] = pd.to_numeric(df['goals tegen'], errors='coerce')

    df_nu = df[(df['Datum'] >= start_rapport) & (df['Datum'] <= eind_rapport)].dropna(subset=['goals']).copy()
    
    winst, gelijk, verlies, voor, tegen = 0, 0, 0, 0, 0
    matchen = []
    for _, row in df_nu.iterrows():
        g, gt = int(row['goals']), int(row['goals tegen'])
        if g > gt: winst += 1
        elif g == gt: gelijk += 1
        else: verlies += 1
        voor += g; tegen += gt
        score = f"{g} - {gt}" if "Ambras" in str(row['Thuisploeg']) else f"{gt} - {g}"
        matchen.append(f"{row['Datum'].strftime('%d/%m')} | {row['Thuisploeg']}  {score}  {row['Uitploeg']}")

    df_volg = df[(df['Datum'] >= start_programma) & (df['Datum'] <= eind_programma)]
    prog = [f"{r['Datum'].strftime('%d/%m')} - {r['Thuisploeg']} vs {r['Uitploeg']}" for _, r in df_volg.iterrows() if pd.notnull(r['Datum'])]

    # --- TEKENEN ---
    w, h = 1000, 1600 
    img = Image.new('RGB', (w, h), color=CLR_BG)
    draw = ImageDraw.Draw(img)
    
    # Font pad voor Linux (GitHub Actions)
    f_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    try:
        title_f, head_f, stat_f, text_f, prog_f = ImageFont.truetype(f_path, 60), ImageFont.truetype(f_path, 38), ImageFont.truetype(f_path, 90), ImageFont.truetype(f_path, 28), ImageFont.truetype(f_path, 25)
    except:
        title_f = head_f = stat_f = text_f = prog_f = ImageFont.load_default()

    # Header
    draw.rectangle([0, 0, w, 210], fill=CLR_CARD)
    if os.path.exists(LOGO_PAD):
        logo = Image.open(LOGO_PAD).convert("RGBA")
        logo.thumbnail((130, 130))
        img.paste(logo, (50, 40), logo)
    draw.text((w/2 + 60, 80), "MAANDRAPPORT", fill=CLR_ACCENT, font=title_f, anchor="mm")
    draw.text((w/2 + 60, 150), f"{rapport_maand_naam} {rapport_jaar}", fill=CLR_TEXT, font=head_f, anchor="mm")

    # Stats Boxen
    y_s = 260
    def stat_box(x, val, label, color):
        draw.rounded_rectangle([x-140, y_s, x+140, y_s+160], radius=15, fill=CLR_CARD)
        draw.text((x, y_s+60), str(val), fill=color, font=stat_f, anchor="mm")
        draw.text((x, y_s+125), label, fill=CLR_TEXT, font=text_f, anchor="mm")

    stat_box(200, winst, "WINST", CLR_W)
    stat_box(500, gelijk, "GELIJK", CLR_G)
    stat_box(800, verlies, "VERLIES", CLR_V)

    # Doelpunten Balken
    y_g = 470
    draw.text((100, y_g), f"DOELPUNTEN VOOR: {voor}", fill=CLR_W, font=text_f)
    draw.rounded_rectangle([100, y_g+35, 900, y_g+60], radius=10, fill=CLR_CARD)
    draw.rounded_rectangle([100, y_g+35, 100+min(voor*20, 800), y_g+60], radius=10, fill=CLR_W)
    
    draw.text((100, y_g+90), f"DOELPUNTEN TEGEN: {tegen}", fill=CLR_V, font=text_f)
    draw.rounded_rectangle([100, y_g+125, 900, y_g+150], radius=10, fill=CLR_CARD)
    draw.rounded_rectangle([100, y_g+125, 100+min(tegen*20, 800), y_g+150], radius=10, fill=CLR_V)

    # Wedstrijden Lijst
    y_r = 680
    draw.text((100, y_r), "GESPEELDE WEDSTRIJDEN", fill=CLR_ACCENT, font=head_f)
    y_r += 60
    for m in matchen[:5]:
        draw.rounded_rectangle([100, y_r, 900, y_r+45], radius=8, fill=CLR_CARD)
        draw.text((120, y_r+8), m, fill=CLR_TEXT, font=text_f)
        y_r += 60

    # Programma Volgende Maand
    y_p = 1050
    draw.rectangle([50, y_p, w-50, y_p+3], fill=CLR_ACCENT)
    y_p += 40
    draw.text((100, y_p), f"PROGRAMMA {MAANDEN_NL[nu.month]}", fill=CLR_ACCENT, font=head_f)
    y_p += 65
    if not prog:
        draw.text((120, y_p), "Geen wedstrijden gepland", fill=(120, 120, 130), font=text_f)
    else:
        for p in prog[:6]:
            draw.text((120, y_p), f"📅  {p}", fill=CLR_TEXT, font=prog_f)
            y_p += 48

    # Footer
    draw.rectangle([0, h-90, w, h], fill=CLR_ACCENT)
    draw.text((w/2, h-45), "FC AMBRAS IS WERELDKLAS!", fill=CLR_BG, font=head_f, anchor="mm")

    # Opslaan en verzenden
    bestandsnaam = "rapport_compleet.png"
    img.save(bestandsnaam)
    verstuur_mail(bestandsnaam, bestandsnaam, rapport_maand_naam)

if __name__ == "__main__":
    genereer_maandrapport()
